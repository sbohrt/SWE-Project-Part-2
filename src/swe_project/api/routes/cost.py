# src/swe_project/api/routes/cost.py
"""
Cost calculation endpoint for artifacts.

Calculates download size costs for artifacts and their dependencies.
"""
import os
from typing import Dict

import boto3
from flask import Blueprint, request, jsonify

bp = Blueprint("cost", __name__)

# DynamoDB setup
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "swe-project-model-ratings")

# Support local DynamoDB for development
dynamodb_config = {}
endpoint_url = os.getenv("AWS_ENDPOINT_URL")
if endpoint_url:
    dynamodb_config = {
        "endpoint_url": endpoint_url,
        "region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    }

_dynamodb = boto3.resource("dynamodb", **dynamodb_config)
_table = _dynamodb.Table(DYNAMODB_TABLE_NAME)


def _calculate_artifact_size(artifact_data: dict) -> float:
    """
    Calculate the size of an artifact in MB.

    For now, we estimate based on size_score data if available,
    or use a placeholder value. In production, this would query
    the actual file size from S3 or HuggingFace.

    Args:
        artifact_data: The artifact data from DynamoDB

    Returns:
        Size in MB
    """
    # Try to get actual size from artifact metadata
    if 'size_mb' in artifact_data:
        return float(artifact_data['size_mb'])

    # Fallback: estimate from size_score if available
    size_score = artifact_data.get('size_score', {})
    if isinstance(size_score, dict):
        # Average of device scores as rough estimate (0-1 scale)
        # Larger models typically range from 100MB to 10GB+
        avg_score = sum([
            size_score.get('raspberry_pi', 0),
            size_score.get('jetson_nano', 0),
            size_score.get('desktop_pc', 0),
            size_score.get('aws_server', 0)
        ]) / 4.0

        # Inverse scoring: lower score = larger model
        # Estimate: 1.0 score = 100MB, 0.0 score = 5000MB
        estimated_mb = 100 + (1.0 - avg_score) * 4900
        return estimated_mb

    # Default fallback
    return 500.0  # 500 MB default


def _get_artifact_dependencies(artifact_id: str) -> list:
    """
    Get all dependencies of an artifact from the lineage graph.

    For now, returns empty list as lineage integration is complex.
    In production, this would query the ModelLineage table.

    Args:
        artifact_id: The artifact ID

    Returns:
        List of dependency artifact IDs
    """
    # TODO: Query lineage table for upstream dependencies
    # For now, return empty list
    return []


@bp.route('/artifact/<artifact_type>/<id>/cost', methods=['GET'])
def get_artifact_cost(artifact_type, id):
    """
    GET /api/v1/artifact/{artifact_type}/{id}/cost

    Calculate the download cost (size in MB) of an artifact.

    Path parameters:
        artifact_type: Type of artifact (model, dataset, code)
        id: Artifact ID

    Query parameters:
        dependency: If true, include costs of all dependencies (default: false)

    Returns:
        200: Cost information
        400: Invalid parameters
        404: Artifact not found
        500: Internal error
    """
    # Validate artifact_type
    valid_types = ['model', 'dataset', 'code']
    if artifact_type not in valid_types:
        return jsonify({
            "error": "BadRequest",
            "message": f"Invalid artifact_type. Must be one of: {', '.join(valid_types)}"
        }), 400

    # Get dependency flag from query params
    include_dependencies = request.args.get('dependency', 'false').lower() == 'true'

    try:
        # Fetch the artifact from DynamoDB
        response = _table.get_item(Key={'modelId': id})

        if 'Item' not in response:
            return jsonify({
                "error": "NotFound",
                "message": f"Artifact with id '{id}' not found"
            }), 404

        artifact = response['Item']

        # Calculate standalone cost
        standalone_cost = _calculate_artifact_size(artifact)

        # Build response
        cost_info: Dict[str, dict] = {}

        if include_dependencies:
            # Include dependencies in the response
            dependency_ids = _get_artifact_dependencies(id)

            # Add main artifact
            cost_info[id] = {
                "standalone_cost": round(standalone_cost, 2),
                "total_cost": round(standalone_cost, 2)
            }

            # Add dependencies
            for dep_id in dependency_ids:
                dep_response = _table.get_item(Key={'modelId': dep_id})
                if 'Item' in dep_response:
                    dep_cost = _calculate_artifact_size(dep_response['Item'])
                    cost_info[dep_id] = {
                        "standalone_cost": round(dep_cost, 2),
                        "total_cost": round(dep_cost, 2)
                    }
                    # Add to main artifact's total cost
                    cost_info[id]["total_cost"] += dep_cost

            # Round final total
            cost_info[id]["total_cost"] = round(cost_info[id]["total_cost"], 2)
        else:
            # Simple response without dependencies
            cost_info[id] = {
                "total_cost": round(standalone_cost, 2)
            }

        return jsonify(cost_info), 200

    except Exception as e:
        return jsonify({
            "error": "InternalError",
            "message": f"Failed to calculate cost: {str(e)}"
        }), 500
