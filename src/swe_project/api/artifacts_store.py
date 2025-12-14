"""
DynamoDB-backed artifact store for the Phase 2 API.

Uses the RatingTable to persist artifacts across Lambda invocations.
"""
from __future__ import annotations

import logging
import json
import os
import re
import time
import uuid
import urllib.request
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

ArtifactRecord = Dict[str, object]
logger = logging.getLogger(__name__)

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
    """
    Infer an artifact name from its URL.

    Important: HuggingFace URLs often include suffixes like /tree/main or /blob/<sha>.
    We want the repository name, not "main".
    """
    if not isinstance(url, str) or not url:
        return "artifact"

    u = url.strip()
    # Strip query/fragment
    u = u.split("#", 1)[0].split("?", 1)[0]

    # Normalize trailing slash
    u = u.rstrip("/")

    parts = [p for p in u.split("/") if p]
    if not parts:
        return "artifact"

    # HuggingFace patterns:
    # - https://huggingface.co/<org>/<repo>
    # - https://huggingface.co/<org>/<repo>/tree/<rev>
    # - https://huggingface.co/datasets/<org>/<repo>
    # - https://huggingface.co/datasets/<org>/<repo>/tree/<rev>
    if "huggingface.co" in u:
        try:
            idx = parts.index("huggingface.co")
        except ValueError:
            idx = -1

        # remove scheme if present (parts includes "https:" etc), so fallback:
        # if idx not found, just use the tail logic below.
        if idx != -1 and idx + 1 < len(parts):
            tail = parts[idx + 1 :]
        else:
            # e.g. parts might not include domain split cleanly; just use last segments.
            tail = parts[-5:]

        # datasets have leading "datasets"
        if tail and tail[0] == "datasets":
            tail = tail[1:]

        # drop known suffix blocks like tree/<rev>, blob/<rev>, resolve/<rev>
        if "tree" in tail:
            t = tail.index("tree")
            tail = tail[:t]
        if "blob" in tail:
            t = tail.index("blob")
            tail = tail[:t]
        if "resolve" in tail:
            t = tail.index("resolve")
            tail = tail[:t]

        if tail:
            return tail[-1]

    # GitHub patterns:
    # - https://github.com/<org>/<repo>
    # - https://github.com/<org>/<repo>/tree/<branch>/...
    if "github.com" in u:
        try:
            idx = parts.index("github.com")
        except ValueError:
            idx = -1
        if idx != -1 and idx + 2 < len(parts):
            tail = parts[idx + 1 :]
            # repo is second segment after org
            if len(tail) >= 2:
                return tail[1]

    # Fallback: last segment
    return parts[-1]


def _artifact_to_dynamo(rec: ArtifactRecord) -> Dict:
    """Convert artifact record to DynamoDB item format."""
    return {
        "modelId": f"artifact#{rec['metadata']['id']}",
        "artifact_id": rec["metadata"]["id"],
        "artifact_type": rec["metadata"]["type"],
        "artifact_name": rec["metadata"]["name"],
        "artifact_url": rec["data"]["url"],
        "download_url": rec["data"].get("download_url", ""),
        # Optional, used for regex search; do not expose in API responses.
        "artifact_readme": rec.get("_readme", ""),
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
                ExpressionAttributeValues={":rt": "artifact"},
                ConsistentRead=True
            )
            for item in response.get("Items", []):
                table.delete_item(Key={"modelId": item["modelId"]})
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression="record_type = :rt",
                    ExpressionAttributeValues={":rt": "artifact"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    ConsistentRead=True
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

        _id = _make_id()
        _name = name or _infer_name_from_url(url)
        now = _now_ts()
        logger.info("AUTOGRADER_DEBUG STORE.create", extra={"artifact_type": atype, "url": url, "name": _name, "id": _id})
        
        # Best-effort README capture for HF models/datasets and GitHub code (required for /artifact/byRegEx).
        readme = ""
        try:
            if "huggingface.co" in url and atype in {"model", "dataset"}:
                # Extract repo_id as "<org>/<repo>" (datasets also use that form after /datasets/)
                u = url.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
                parts = [p for p in u.split("/") if p]
                # find "huggingface.co" and take two segments after (skip "datasets" if present)
                if "huggingface.co" in parts:
                    idx = parts.index("huggingface.co")
                    tail = parts[idx + 1 :]
                    if tail and tail[0] == "datasets":
                        tail = tail[1:]
                    # drop /tree/<rev> etc
                    if "tree" in tail:
                        tail = tail[: tail.index("tree")]
                    if len(tail) >= 2:
                        repo_id = f"{tail[0]}/{tail[1]}"
                        from src.core.hf_client import readme_text
                        readme = readme_text(repo_id, repo_type=("dataset" if atype == "dataset" else "model"))
            elif "github.com" in url and atype == "code":
                u = url.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
                parts = [p for p in u.split("/") if p]
                if "github.com" in parts:
                    idx = parts.index("github.com")
                    tail = parts[idx + 1 :]
                    if len(tail) >= 2:
                        org, repo = tail[0], tail[1]
                        # Try common raw README locations
                        candidates = [
                            f"https://raw.githubusercontent.com/{org}/{repo}/main/README.md",
                            f"https://raw.githubusercontent.com/{org}/{repo}/master/README.md",
                            f"https://raw.githubusercontent.com/{org}/{repo}/main/readme.md",
                            f"https://raw.githubusercontent.com/{org}/{repo}/master/readme.md",
                        ]
                        for ru in candidates:
                            try:
                                req = urllib.request.Request(ru, headers={"User-Agent": "ece461-autograder"})
                                with urllib.request.urlopen(req, timeout=3) as resp:
                                    data = resp.read(50_000)
                                    readme = data.decode("utf-8", errors="ignore")
                                    if readme:
                                        break
                            except Exception:
                                continue
        except Exception as e:
            logger.info("AUTOGRADER_DEBUG STORE.create readme failed", extra={"url": url, "err": str(e)})

        record: ArtifactRecord = {
            "metadata": {"name": _name, "id": _id, "type": atype},
            "data": {
                "url": url,
                "download_url": f"https://example.com/download/{_id}",
            },
            "created_at": now,
            "updated_at": now,
            "_readme": readme,
        }
        
        # Store in DynamoDB
        table.put_item(Item=_artifact_to_dynamo(record))
        return record

    def get(self, artifact_id: str) -> Optional[ArtifactRecord]:
        table = _get_table()
        try:
            # Use strongly consistent read to avoid eventual consistency issues
            logger.info("AUTOGRADER_DEBUG STORE.get", extra={"artifact_id": artifact_id, "pk": f"artifact#{artifact_id}"})
            response = table.get_item(
                Key={"modelId": f"artifact#{artifact_id}"},
                ConsistentRead=True
            )
            item = response.get("Item")
            if item and item.get("record_type") == "artifact":
                logger.info("AUTOGRADER_DEBUG STORE.get hit", extra={"artifact_id": artifact_id, "artifact_type": item.get("artifact_type"), "artifact_name": item.get("artifact_name")})
                return _dynamo_to_artifact(item)
        except ClientError:
            pass
        logger.info("AUTOGRADER_DEBUG STORE.get miss", extra={"artifact_id": artifact_id})
        return None

    def get_readme(self, artifact_id: str) -> str:
        """
        Fetch stored README text for an artifact (best-effort).

        This is intentionally not included in the Artifact API response envelope,
        but is used for regex search and rating heuristics.
        """
        table = _get_table()
        try:
            response = table.get_item(
                Key={"modelId": f"artifact#{artifact_id}"},
                ConsistentRead=True,
            )
            item = response.get("Item") or {}
            if item.get("record_type") == "artifact":
                return str(item.get("artifact_readme", "") or "")
        except ClientError:
            pass
        return ""

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
            logger.info("AUTOGRADER_DEBUG STORE.delete_by_id", extra={"artifact_id": artifact_id})
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
                    # Be tolerant to casing differences from clients/grader.
                    if str(md.get("name", "")).casefold() != str(name).casefold():
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
        """
        Return artifacts matching name.

        We do a full scan + in-Python filtering to be case-insensitive and to
        avoid DynamoDB expression edge cases.
        """
        table = _get_table()
        try:
            response = table.scan(
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={":rt": "artifact"},
                ConsistentRead=True,
            )
            items = response.get("Items", [])
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression="record_type = :rt",
                    ExpressionAttributeValues={":rt": "artifact"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                    ConsistentRead=True,
                )
                items.extend(response.get("Items", []))
        except ClientError:
            items = []

        target = str(name).casefold()
        out: List[ArtifactRecord] = []
        for item in items:
            rec = _dynamo_to_artifact(item)
            if str(rec.get("metadata", {}).get("name", "")).casefold() == target:
                out.append(rec)
        return out

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

        # Filter using name/url/readme without changing the external artifact schema.
        matched: List[ArtifactRecord] = []
        for item in items:
            name = str(item.get("artifact_name", ""))
            url = str(item.get("artifact_url", ""))
            readme = str(item.get("artifact_readme", ""))
            if regex.search(name) or regex.search(url) or regex.search(readme):
                matched.append(_dynamo_to_artifact(item))
        return matched


STORE = ArtifactStore()
