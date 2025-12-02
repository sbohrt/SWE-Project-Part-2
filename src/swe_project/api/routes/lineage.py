from __future__ import annotations

import os
from typing import List, Tuple

import boto3
from boto3.dynamodb.conditions import Key
from flask import Blueprint, jsonify, request
from jsonschema import ValidationError, validate

bp = Blueprint("lineage", __name__)

# --- DynamoDB wiring ---

LINEAGE_TABLE_NAME = os.getenv("LINEAGE_TABLE_NAME", "ModelLineage")
_dynamodb = boto3.resource("dynamodb")
_lineage_table = _dynamodb.Table(LINEAGE_TABLE_NAME)


def _pk(entity_id: str) -> str:
    """
    Partition key format must match the write side (lineage_store._pk):
      PK = "NODE#" + internal_id
    where internal_id is something like "hf:model/google-bert/bert-base-uncased".
    """
    return f"NODE#{entity_id}"


def _fetch_adjacency_items(entity_id: str) -> List[dict]:
    """Fetch all adjacency items (IN + OUT) for a given entity."""
    resp = _lineage_table.query(
        KeyConditionExpression=Key("PK").eq(_pk(entity_id))
    )
    return resp.get("Items", [])


# --- JSON Schemas for query params ---


ADJACENCY_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "entityId": {"type": "string", "minLength": 1},
    },
    "required": ["entityId"],
    "additionalProperties": False,
}

LINEAGE_QUERY_SCHEMA = {
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


def _validate_adjacency_query(args: dict) -> dict:
    obj = {"entityId": args.get("entityId")}
    validate(instance=obj, schema=ADJACENCY_QUERY_SCHEMA)
    return obj


def _validate_lineage_query(args: dict) -> dict:
    direction = args.get("direction") or "downstream"
    depth_raw = args.get("depth") or "2"
    try:
        depth = int(depth_raw)
    except ValueError:
        raise ValidationError("depth must be an integer")

    obj = {
        "entityId": args.get("entityId"),
        "direction": direction,
        "depth": depth,
    }
    validate(instance=obj, schema=LINEAGE_QUERY_SCHEMA)
    return obj


# --- Graph helpers ---


def _neighbors_for_direction(entity_id: str, direction: str) -> List[dict]:
    """
    Return neighbor edge items for a node in a given direction.

    direction:
      - "downstream" => OUT edges (from_id -> to_id)
      - "upstream"   => IN  edges (from_id -> to_id, but we walk to from_id)
    """
    items = _fetch_adjacency_items(entity_id)
    if direction == "downstream":
        return [item for item in items if item.get("direction") == "OUT"]
    else:
        return [item for item in items if item.get("direction") == "IN"]


def _compute_lineage(
    root_id: str, direction: str, depth: int
) -> Tuple[List[dict], List[dict]]:
    """
    BFS traversal over the lineage graph up to 'depth' levels.

    Returns:
      nodes: list of {"id": ..., "level": ...}
      edges: list of {"from": ..., "to": ..., "edge_type": ...}
    """
    visited = {root_id}
    nodes: List[dict] = [{"id": root_id, "level": 0}]
    edges: List[dict] = []

    queue: List[Tuple[str, int]] = [(root_id, 0)]

    while queue:
        current_id, level = queue.pop(0)
        if level >= depth:
            continue

        neighbors = _neighbors_for_direction(current_id, direction)

        for item in neighbors:
            from_id = item.get("from_id")
            to_id = item.get("to_id")
            edge_type = item.get("edge_type")

            if direction == "downstream":
                next_id = to_id
            else:  # upstream
                next_id = from_id

            if not next_id:
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


# --- Routes ---


@bp.get("/adjacency")
def adjacency():
    """
    GET /api/v1/adjacency?entityId=hf:model/...
    Returns direct upstream and downstream neighbors for the given entity.
    """
    try:
        params = _validate_adjacency_query(request.args.to_dict())
    except ValidationError as e:
        return (
            jsonify({"error": "BadRequest", "message": str(e)}),
            400,
        )

    entity_id = params["entityId"]

    try:
        items = _fetch_adjacency_items(entity_id)
    except Exception:
        return (
            jsonify(
                {
                    "error": "InternalError",
                    "message": "Failed to query adjacency.",
                }
            ),
            500,
        )

    upstream: List[dict] = []
    downstream: List[dict] = []

    for item in items:
        direction = item.get("direction")
        edge_type = item.get("edge_type")
        from_id = item.get("from_id")
        to_id = item.get("to_id")

        if direction == "OUT" and to_id:
            downstream.append({"id": to_id, "edge_type": edge_type})
        elif direction == "IN" and from_id:
            upstream.append({"id": from_id, "edge_type": edge_type})

    return jsonify(
        {
            "entityId": entity_id,
            "upstream": upstream,
            "downstream": downstream,
        }
    )


@bp.get("/lineage")
def lineage():
    """
    GET /api/v1/lineage?entityId=...&direction=upstream|downstream&depth=N
    Returns a lineage graph (nodes + edges) rooted at entityId.
    """
    try:
        params = _validate_lineage_query(request.args.to_dict())
    except ValidationError as e:
        return (
            jsonify({"error": "BadRequest", "message": str(e)}),
            400,
        )

    entity_id = params["entityId"]
    direction = params["direction"]
    depth = params["depth"]

    try:
        nodes, edges = _compute_lineage(entity_id, direction, depth)
    except Exception:
        return (
            jsonify(
                {
                    "error": "InternalError",
                    "message": "Failed to compute lineage.",
                }
            ),
            500,
        )

    return jsonify(
        {
            "root": entity_id,
            "direction": direction,
            "depth": depth,
            "nodes": nodes,
            "edges": edges,
        }
    )
