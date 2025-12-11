"""
DynamoDB-backed artifact store for the Phase 2 API.

Uses the RatingTable to persist artifacts across Lambda invocations.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

ArtifactRecord = Dict[str, object]

# Get table name from environment, with fallback
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "RatingTable")

# Initialize DynamoDB resource
_dynamodb = None


def _get_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(TABLE_NAME)


def _now_ts() -> int:
    return int(time.time())


def _make_id() -> str:
    # Generate a 10-digit-ish numeric-looking ID to match examples
    return str(uuid.uuid4().int % 10_000_000_000)


def _normalize_type(t: str) -> Optional[str]:
    if not isinstance(t, str):
        return None
    t = t.strip().lower()
    if t in {"model", "dataset", "code"}:
        return t
    return None


def _infer_name_from_url(url: str) -> str:
    # Take the last non-empty path segment as the name fallback
    parts = [p for p in url.rstrip("/").split("/") if p]
    return parts[-1] if parts else "artifact"


def _artifact_to_dynamo(rec: ArtifactRecord) -> Dict:
    """Convert artifact record to DynamoDB item format."""
    return {
        "modelId": f"artifact#{rec['metadata']['id']}",
        "artifact_id": rec["metadata"]["id"],
        "artifact_type": rec["metadata"]["type"],
        "artifact_name": rec["metadata"]["name"],
        "artifact_url": rec["data"]["url"],
        "download_url": rec["data"].get("download_url", ""),
        "created_at": rec.get("created_at", _now_ts()),
        "updated_at": rec.get("updated_at", _now_ts()),
        "record_type": "artifact",
    }


def _dynamo_to_artifact(item: Dict) -> ArtifactRecord:
    """Convert DynamoDB item to artifact record format."""
    return {
        "metadata": {
            "id": item.get("artifact_id", item.get("modelId", "").replace("artifact#", "")),
            "name": item.get("artifact_name", ""),
            "type": item.get("artifact_type", ""),
        },
        "data": {
            "url": item.get("artifact_url", ""),
            "download_url": item.get("download_url", ""),
        },
        "created_at": int(item.get("created_at", 0)),
        "updated_at": int(item.get("updated_at", 0)),
    }


class ArtifactStore:
    def reset(self) -> None:
        """Delete all artifacts from DynamoDB."""
        table = _get_table()
        try:
            # Scan for all artifacts and delete them
            response = table.scan(
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={":rt": "artifact"}
            )
            for item in response.get("Items", []):
                table.delete_item(Key={"modelId": item["modelId"]})
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression="record_type = :rt",
                    ExpressionAttributeValues={":rt": "artifact"},
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                for item in response.get("Items", []):
                    table.delete_item(Key={"modelId": item["modelId"]})
        except ClientError:
            pass  # Table might not exist yet

    def create(self, artifact_type: str, url: str, name: Optional[str] = None) -> ArtifactRecord:
        atype = _normalize_type(artifact_type)
        if atype is None:
            raise ValueError("invalid artifact type")
        if not url or not isinstance(url, str):
            raise ValueError("invalid url")

        table = _get_table()
        
        # Check for duplicate (same type + url)
        try:
            response = table.scan(
                FilterExpression="record_type = :rt AND artifact_type = :at AND artifact_url = :url",
                ExpressionAttributeValues={
                    ":rt": "artifact",
                    ":at": atype,
                    ":url": url,
                }
            )
            if response.get("Items"):
                raise FileExistsError("artifact exists")
        except ClientError:
            pass

        _id = _make_id()
        _name = name or _infer_name_from_url(url)
        now = _now_ts()
        
        record: ArtifactRecord = {
            "metadata": {"name": _name, "id": _id, "type": atype},
            "data": {
                "url": url,
                "download_url": f"https://example.com/download/{_id}",
            },
            "created_at": now,
            "updated_at": now,
        }
        
        # Store in DynamoDB
        table.put_item(Item=_artifact_to_dynamo(record))
        return record

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        table = _get_table()
        try:
            # Use strongly consistent read to avoid eventual consistency issues
            response = table.get_item(
                Key={"modelId": f"artifact#{artifact_id}"},
                ConsistentRead=True
            )
            item = response.get("Item")
            if item and item.get("record_type") == "artifact":
                return _dynamo_to_artifact(item)
        except ClientError:
            pass
        return None

    def update(self, artifact_type: str, artifact_id: str, artifact: ArtifactRecord) -> bool:
        atype = _normalize_type(artifact_type)
        if atype is None:
            return False
        md = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
        data = artifact.get("data", {}) if isinstance(artifact, dict) else {}
        if (
            md.get("id") != artifact_id
            or _normalize_type(md.get("type", "")) != atype
            or not md.get("name")
            or not data.get("url")
        ):
            return False

        table = _get_table()
        
        # Get existing record
        existing = self.get(artifact_id)
        if not existing:
            return False
        
        now = _now_ts()
        download_url = data.get("download_url") or existing["data"].get("download_url")
        
        updated_record: ArtifactRecord = {
            "metadata": {"name": md["name"], "id": artifact_id, "type": atype},
            "data": {"url": data["url"], "download_url": download_url},
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        
        table.put_item(Item=_artifact_to_dynamo(updated_record))
        return True

    def delete(self, artifact_type: str, artifact_id: str) -> bool:
        atype = _normalize_type(artifact_type)
        if atype is None:
            return False
        
        table = _get_table()
        
        # Get existing record to verify type
        existing = self.get(artifact_id)
        if not existing or existing["metadata"]["type"] != atype:
            return False
        
        try:
            table.delete_item(Key={"modelId": f"artifact#{artifact_id}"})
            return True
        except ClientError:
            return False

    def delete_by_id(self, artifact_id: str) -> bool:
        """Delete artifact by ID without type validation."""
        table = _get_table()
        
        try:
            table.delete_item(Key={"modelId": f"artifact#{artifact_id}"})
            return True
        except ClientError:
            return False

    def list_by_queries(self, queries: List[Dict], offset: Optional[str] = None) -> List[ArtifactRecord]:
        """
        queries: list of {"name": "...", "types": ["model", ...]?}
        If name == "*", treat as wildcard for all names.
        """
        table = _get_table()
        
        try:
            response = table.scan(
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={":rt": "artifact"},
                ConsistentRead=True
            )
            items = response.get("Items", [])
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression="record_type = :rt",
                    ExpressionAttributeValues={":rt": "artifact"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    ConsistentRead=True
                )
                items.extend(response.get("Items", []))
        except ClientError:
            items = []
        
        records = [_dynamo_to_artifact(item) for item in items]
        
        matches: List[ArtifactRecord] = []
        for q in queries:
            name = q.get("name")
            types = q.get("types")
            allowed_types = None
            if isinstance(types, list):
                allowed_types = set([_normalize_type(t) for t in types if _normalize_type(t)])

            for rec in records:
                md = rec.get("metadata", {})
                if not name or name == "*":
                    pass  # wildcard
                else:
                    if md.get("name") != name:
                        continue
                if allowed_types:
                    if _normalize_type(md.get("type", "")) not in allowed_types:
                        continue
                matches.append(rec)
        
        # simple de-dupe if multiple queries overlapped
        seen = set()
        out = []
        for rec in matches:
            rid = rec["metadata"]["id"]
            if rid in seen:
                continue
            seen.add(rid)
            out.append(rec)
        return out

    def list_by_name(self, name: str) -> List[ArtifactRecord]:
        table = _get_table()
        
        try:
            response = table.scan(
                FilterExpression="record_type = :rt AND artifact_name = :name",
                ExpressionAttributeValues={":rt": "artifact", ":name": name},
                ConsistentRead=True
            )
            items = response.get("Items", [])
        except ClientError:
            items = []
        
        return [_dynamo_to_artifact(item) for item in items]

    def list_by_regex(self, pattern: str) -> List[ArtifactRecord]:
        regex = re.compile(pattern, re.IGNORECASE)
        table = _get_table()
        
        try:
            response = table.scan(
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={":rt": "artifact"},
                ConsistentRead=True
            )
            items = response.get("Items", [])
        except ClientError:
            items = []
        
        records = [_dynamo_to_artifact(item) for item in items]
        return [rec for rec in records if (regex.search(rec["metadata"].get("name", "")) or regex.search(rec["data"].get("url", "")))]


STORE = ArtifactStore()
