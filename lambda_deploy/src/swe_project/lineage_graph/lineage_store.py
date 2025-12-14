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


def get_lineage(entity_id: str) -> dict:
    """
    Retrieve the lineage graph for a given entity.
    
    Returns a dict with:
      - nodes: list of node objects
      - edges: list of edge objects
      
    Args:
        entity_id: The internal ID format, e.g. "hf:model/google-bert/bert-base-uncased"
                   or just the artifact_id from the artifacts store
    """
    # Normalize the entity_id if needed
    # If it's just an artifact_id (UUID), we need to find its internal ID
    # For now, assume entity_id is already in the correct format
    
    visited_nodes = set()
    edges_list = []
    nodes_list = []
    
    def _traverse(node_id: str):
        """Recursively traverse the graph to collect all nodes and edges."""
        if node_id in visited_nodes:
            return
        visited_nodes.add(node_id)
        
        # Add this node
        nodes_list.append({
            "artifact_id": node_id,
            "name": node_id.split("/")[-1] if "/" in node_id else node_id,
            "source": "config_json"
        })
        
        try:
            # Query for all edges where this node is involved (OUT edges)
            response = _table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": _pk(node_id),
                    ":sk_prefix": "EDGE#OUT#"
                }
            )
            
            for item in response.get("Items", []):
                from_id = item.get("from_id")
                to_id = item.get("to_id")
                edge_type = item.get("edge_type", "DERIVED_FROM")
                
                edges_list.append({
                    "from_node_artifact_id": from_id,
                    "to_node_artifact_id": to_id,
                    "relationship": edge_type.lower().replace("_", " ")
                })
                
                # Recursively traverse the target node
                _traverse(to_id)
            
            # Also query for IN edges to get upstream dependencies
            response_in = _table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": _pk(node_id),
                    ":sk_prefix": "EDGE#IN#"
                }
            )
            
            for item in response_in.get("Items", []):
                from_id = item.get("from_id")
                to_id = item.get("to_id")
                edge_type = item.get("edge_type", "DERIVED_FROM")
                
                # Check if we already have this edge
                edge_dict = {
                    "from_node_artifact_id": from_id,
                    "to_node_artifact_id": to_id,
                    "relationship": edge_type.lower().replace("_", " ")
                }
                if edge_dict not in edges_list:
                    edges_list.append(edge_dict)
                
                # Recursively traverse the source node
                _traverse(from_id)
                
        except Exception as e:
            logger.warning("Failed to query lineage for node %s: %s", node_id, e)
    
    try:
        _traverse(entity_id)
    except Exception as e:
        logger.error("Failed to build lineage graph for %s: %s", entity_id, e)
        # Return minimal graph with just the requested node
        return {
            "nodes": [{
                "artifact_id": entity_id,
                "name": entity_id.split("/")[-1] if "/" in entity_id else entity_id,
                "source": "config_json"
            }],
            "edges": []
        }
    
    return {
        "nodes": nodes_list,
        "edges": edges_list
    }
