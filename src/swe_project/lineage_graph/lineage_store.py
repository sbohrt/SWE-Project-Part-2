# src/swe_project/lineage_store.py
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable, TypedDict

import boto3


logger = logging.getLogger(__name__)


class Edge(TypedDict):
    """
    A directed edge in the lineage graph.

    from_id and to_id should be INTERNAL IDs, e.g.:
      "hf:model/google-bert/bert-base-uncased"
    edge_type examples:
      - "DERIVED_FROM"
      - "USES_DATASET" (if you add that later)
    """
    from_id: str
    to_id: str
    edge_type: str


# Table name can be overridden via env var; default for your project:
_TABLE_NAME = os.environ.get("LINEAGE_TABLE_NAME", "ModelLineage")

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pk(entity_id: str) -> str:
    """
    Partition key format for nodes in the graph.
    We prefix to keep room for future entity types if needed.
    """
    return f"NODE#{entity_id}"


def _sk(direction: str, other_id: str) -> str:
    """
    Sort key format for adjacency edges.

    direction:
      - "OUT": this node -> other
      - "IN":  other -> this node
    """
    return f"EDGE#{direction}#{other_id}"


def put_edges(edges: Iterable[Edge]) -> None:
    """
    Store edges in DynamoDB as adjacency records.

    For each logical edge (from_id -> to_id), we write TWO items:
      - OUT item under from_id's partition (downstream adjacency)
      - IN  item under to_id's partition (upstream adjacency)

    This makes it efficient to query:
      - "what models are downstream of X?"
      - "what models are upstream of X?"
    """
    # Materialize the iterable once, so we can bail out early if empty.
    edge_list = list(edges)
    if not edge_list:
        return

    ts = _iso_now()

    try:
        with _table.batch_writer() as batch:
            for edge in edge_list:
                from_id = edge["from_id"]
                to_id = edge["to_id"]
                edge_type = edge["edge_type"]

                # OUT: from_id -> to_id
                batch.put_item(
                    Item={
                        "PK": _pk(from_id),
                        "SK": _sk("OUT", to_id),
                        "direction": "OUT",
                        "edge_type": edge_type,
                        "from_id": from_id,
                        "to_id": to_id,
                        "created_at": ts,
                    }
                )

                # IN: to_id <- from_id
                batch.put_item(
                    Item={
                        "PK": _pk(to_id),
                        "SK": _sk("IN", from_id),
                        "direction": "IN",
                        "edge_type": edge_type,
                        "from_id": from_id,
                        "to_id": to_id,
                        "created_at": ts,
                    }
                )
    except Exception as e:
        # Do NOT crash the scoring run just because lineage writing failed.
        logger.warning("Failed to write lineage edges (%d) to DynamoDB: %s",
                       len(edge_list), e)
