from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

import boto3
from boto3.dynamodb.conditions import Key
from jsonschema import ValidationError, validate

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# DynamoDB setup
_TABLE_NAME = os.environ.get("LINEAGE_TABLE_NAME", "ModelLineage")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)


# ---------- JSON Schemas for query params ----------

ADJACENCY_REQUEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "entityId": {"type": "string", "minLength": 1},
    },
    "required": ["entityId"],
    "additionalProperties": False,
}

LINEAGE_REQUEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "entityId": {"type": "string", "minLength": 1},
        "direction": {
            "type": "string",
            "enum": ["upstream", "downstream"],
        },
        "depth": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
        },
    },
    "required": ["entityId"],
    "additionalProperties": False,
}


# ---------- Helpers ----------


def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_path(event: Dict[str, Any]) -> str:
    # HttpApi uses rawPath; REST API uses path
    return event.get("rawPath") or event.get("path") or ""


def _get_query_params(event: Dict[str, Any]) -> Dict[str, str]:
    return event.get("queryStringParameters") or {}


def _pk(entity_id: str) -> str:
    # Must match the write-side format in lineage_store.py
    return f"NODE#{entity_id}"


def _query_all_adjacency(entity_id: str) -> List[Dict[str, Any]]:
    """Fetch all adjacency edges (IN + OUT) for a node."""
    resp = _table.query(
        KeyConditionExpression=Key("PK").eq(_pk(entity_id)),
    )
    return resp.get("Items", [])


def _get_validated_adjacency_params(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = _get_query_params(event)
    obj: Dict[str, Any] = {
        "entityId": raw.get("entityId"),
    }

    try:
        validate(instance=obj, schema=ADJACENCY_REQUEST_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Invalid adjacency request: {e.message}") from e

    return obj


def _get_validated_lineage_params(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = _get_query_params(event)

    # Apply defaults for direction/depth before validation
    direction = raw.get("direction") or "downstream"
    depth_str = raw.get("depth") or "2"

    try:
        depth = int(depth_str)
    except ValueError:
        raise ValueError("depth must be an integer")  # will be turned into 400

    obj: Dict[str, Any] = {
        "entityId": raw.get("entityId"),
        "direction": direction,
        "depth": depth,
    }

    try:
        validate(instance=obj, schema=LINEAGE_REQUEST_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Invalid lineage request: {e.message}") from e

    return obj


# ---------- Handlers ----------


def _handle_adjacency(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = _get_validated_adjacency_params(event)
    except ValueError as e:
        return _response(
            400,
            {"error": "BadRequest", "message": str(e)},
        )

    entity_id = params["entityId"]

    try:
        items = _query_all_adjacency(entity_id)
    except Exception as e:
        logger.exception("Failed to query adjacency for %s", entity_id)
        return _response(
            500,
            {"error": "InternalError", "message": "Failed to query adjacency."},
        )

    upstream: List[Dict[str, Any]] = []
    downstream: List[Dict[str, Any]] = []

    for item in items:
        direction = item.get("direction")
        edge_type = item.get("edge_type")
        from_id = item.get("from_id")
        to_id = item.get("to_id")

        if direction == "OUT":
            downstream.append({"id": to_id, "edge_type": edge_type})
        elif direction == "IN":
            upstream.append({"id": from_id, "edge_type": edge_type})

    body = {
        "entityId": entity_id,
        "upstream": upstream,
        "downstream": downstream,
    }
    return _response(200, body)


def _neighbors_for_direction(
    entity_id: str, direction: str
) -> List[Dict[str, Any]]:
    """
    Return neighbors for a node in a single direction.

    direction:
      - "downstream" => use OUT edges (from_id -> to_id)
      - "upstream"   => use IN  edges (from_id -> to_id, but we walk to from_id)
    """
    items = _query_all_adjacency(entity_id)
    result: List[Dict[str, Any]] = []

    if direction == "downstream":
        for item in items:
            if item.get("direction") == "OUT":
                result.append(item)
    else:  # upstream
        for item in items:
            if item.get("direction") == "IN":
                result.append(item)

    return result


def _compute_lineage(
    root_id: str, direction: str, depth: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    BFS lineage traversal up to 'depth' levels.

    Returns:
      nodes: list of {"id": ..., "level": ...}
      edges: list of {"from": ..., "to": ..., "edge_type": ...}
    """
    visited = set([root_id])
    nodes: List[Dict[str, Any]] = [{"id": root_id, "level": 0}]
    edges: List[Dict[str, Any]] = []

    # Queue of (node_id, level)
    queue: List[Tuple[str, int]] = [(root_id, 0)]

    while queue:
        current_id, level = queue.pop(0)
        if level >= depth:
            continue

        neighbors = _neighbors_for_direction(current_id, direction)

        for item in neighbors:
            edge_type = item.get("edge_type")
            from_id = item.get("from_id")
            to_id = item.get("to_id")

            if direction == "downstream":
                next_id = to_id
            else:  # upstream
                next_id = from_id

            if next_id is None:
                continue

            edges.append(
                {
                    "from": from_id,
                    "to": to_id,
                    "edge_type": edge_type,
                }
            )

            if next_id not in visited:
                visited.add(next_id)
                nodes.append({"id": next_id, "level": level + 1})
                queue.append((next_id, level + 1))

    return nodes, edges


def _handle_lineage(event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        params = _get_validated_lineage_params(event)
    except ValueError as e:
        return _response(
            400,
            {"error": "BadRequest", "message": str(e)},
        )

    entity_id = params["entityId"]
    direction = params["direction"]
    depth = params["depth"]

    try:
        nodes, edges = _compute_lineage(entity_id, direction, depth)
    except Exception as e:
        logger.exception("Failed to compute lineage for %s", entity_id)
        return _response(
            500,
            {"error": "InternalError", "message": "Failed to compute lineage."},
        )

    body = {
        "root": entity_id,
        "direction": direction,
        "depth": depth,
        "nodes": nodes,
        "edges": edges,
    }
    return _response(200, body)


# ---------- Lambda entrypoint ----------


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Entry point for AWS Lambda via API Gateway / HttpApi.

    Supports:
      GET /adjacency?entityId=...
      GET /lineage?entityId=...&direction=upstream|downstream&depth=N
    """
    logger.info("Received event: %s", json.dumps(event))

    path = _get_path(event)
    http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")

    if http_method != "GET":
        return _response(
            405,
            {"error": "MethodNotAllowed", "message": "Only GET is supported."},
        )

    if path.endswith("/adjacency"):
        return _handle_adjacency(event)
    if path.endswith("/lineage"):
        return _handle_lineage(event)

    return _response(
        404,
        {"error": "NotFound", "message": f"Unknown path: {path}"},
    )
