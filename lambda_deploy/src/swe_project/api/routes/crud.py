# src/swe_project/api/routes/crud.py
"""
CRUD endpoints for managing scored models in DynamoDB.

SECURITY FIX: DELETE /reset endpoint requires API key authentication.
"""
import os

import boto3
from flask import Blueprint, request, jsonify

from src.swe_project.api.auth import require_api_key

bp = Blueprint("crud", __name__)

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


@bp.route('/artifacts', methods=['POST'])
def list_artifacts():
    """
    POST /api/v1/artifacts

    Enumerate and search artifacts based on query criteria.

    Request body:
        [
            {
                "name": "*",  # "*" for all, or specific name to filter
                "types": ["model", "dataset", "code"]  # Optional filter
            }
        ]

    Query parameters:
        - offset: Pagination offset (optional)

    Returns:
        200: Array of artifact metadata with pagination offset header
        400: Invalid query format
        413: Too many results
    """
    # Parse request body
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, list):
        return jsonify({
            "error": "BadRequest",
            "message": "Request body must be a JSON array of artifact queries"
        }), 400

    if len(data) == 0:
        return jsonify({
            "error": "BadRequest",
            "message": "At least one artifact query is required"
        }), 400

    # Get pagination offset from query parameters
    offset = request.args.get('offset', '0')
    try:
        offset_int = int(offset)
    except ValueError:
        return jsonify({
            "error": "BadRequest",
            "message": "Invalid offset parameter"
        }), 400

    # Page size for pagination
    PAGE_SIZE = 100
    MAX_RESULTS = 10000

    try:
        # Scan DynamoDB table to get all items
        response = _table.scan()
        items = response.get('Items', [])

        # Handle pagination in DynamoDB
        while 'LastEvaluatedKey' in response:
            response = _table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        # Process each query in the request
        query = data[0]  # For now, process first query (spec allows multiple)
        name_filter = query.get('name', '*')
        types_filter = query.get('types', ['model', 'dataset', 'code'])

        # Convert items to ArtifactMetadata format
        artifacts = []
        for item in items:
            # Extract metadata from DynamoDB item
            artifact_name = item.get('name', 'unknown')
            artifact_id = item.get('modelId', item.get('id', 'unknown'))
            # Currently only models are stored, but structure for extensibility
            artifact_type = item.get('type', 'model')

            # Apply name filter
            if name_filter != '*':
                if artifact_name != name_filter:
                    continue

            # Apply type filter
            if artifact_type not in types_filter:
                continue

            artifacts.append({
                "name": artifact_name,
                "id": artifact_id,
                "type": artifact_type
            })

        # Check if too many results
        if len(artifacts) > MAX_RESULTS:
            return jsonify({
                "error": "TooManyResults",
                "message": f"Query returned {len(artifacts)} results, maximum is {MAX_RESULTS}"
            }), 413

        # Apply pagination
        start_idx = offset_int
        end_idx = start_idx + PAGE_SIZE
        paginated_artifacts = artifacts[start_idx:end_idx]

        # Calculate next offset
        next_offset = end_idx if end_idx < len(artifacts) else len(artifacts)

        # Return response with offset header
        response = jsonify(paginated_artifacts)
        response.headers['offset'] = str(next_offset)
        return response, 200

    except Exception as e:
        return jsonify({
            "error": "InternalError",
            "message": f"Failed to enumerate artifacts: {str(e)}"
        }), 500


@bp.route('/reset', methods=['DELETE'])
@require_api_key
def reset():
    """
    DELETE /api/v1/reset

    ADMIN ONLY: Delete all models from the DynamoDB table.

    Requires X-API-Key header with valid admin API key.

    Returns:
        200: {"message": "All models deleted", "count": N}
        401: Missing API key
        403: Invalid API key
        500: Internal error
    """
    try:
        # Scan to get all items
        response = _table.scan()
        items = response.get('Items', [])

        # Handle pagination if there are many items
        while 'LastEvaluatedKey' in response:
            response = _table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        # Delete each item
        deleted_count = 0
        for item in items:
            _table.delete_item(Key={'modelId': item['modelId']})
            deleted_count += 1

        return jsonify({
            "message": "All models deleted successfully",
            "count": deleted_count
        }), 200

    except Exception as e:
        return jsonify({
            "error": "InternalError",
            "message": f"Failed to reset table: {str(e)}"
        }), 500


# CRUD operations using DynamoDB
@bp.route('/models', methods=['GET'])
def list_models():
    """List all models from DynamoDB"""
    try:
        response = _table.scan()
        items = response.get('Items', [])

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = _table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": f"Failed to list models: {str(e)}"}), 500


@bp.route('/models/<model_id>', methods=['GET'])
def get_model(model_id):
    """Get specific model by ID from DynamoDB"""
    try:
        response = _table.get_item(Key={'modelId': model_id})
        if 'Item' not in response:
            return jsonify({"error": "Model not found"}), 404
        return jsonify(response['Item']), 200
    except Exception as e:
        return jsonify({"error": f"Failed to get model: {str(e)}"}), 500


@bp.route('/models', methods=['POST'])
def create_model():
    """Add a new model to DynamoDB"""
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({"error": "Missing required field: id"}), 400

    model_id = data['id']

    try:
        # Check if model already exists
        response = _table.get_item(Key={'modelId': model_id})
        if 'Item' in response:
            return jsonify({"error": "Model already exists"}), 409

        # Add modelId to data if not present
        data['modelId'] = model_id
        _table.put_item(Item=data)
        return jsonify(data), 201
    except Exception as e:
        return jsonify({"error": f"Failed to create model: {str(e)}"}), 500


@bp.route('/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    """Update an existing model in DynamoDB"""
    try:
        # Check if model exists
        response = _table.get_item(Key={'modelId': model_id})
        if 'Item' not in response:
            return jsonify({"error": "Model not found"}), 404

        data = request.get_json()
        data['modelId'] = model_id  # Ensure modelId is preserved
        _table.put_item(Item=data)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": f"Failed to update model: {str(e)}"}), 500


@bp.route('/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    """Delete a model from DynamoDB"""
    try:
        # Check if model exists
        response = _table.get_item(Key={'modelId': model_id})
        if 'Item' not in response:
            return jsonify({"error": "Model not found"}), 404

        deleted = response['Item']
        _table.delete_item(Key={'modelId': model_id})
        return jsonify({"message": "Model deleted", "model": deleted}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete model: {str(e)}"}), 500
