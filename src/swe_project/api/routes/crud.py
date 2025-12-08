# src/swe_project/api/routes/crud.py
"""
CRUD endpoints for managing scored models in DynamoDB.

SECURITY FIX: DELETE /reset endpoint requires API key authentication.
"""
import os

import boto3
from flask import Blueprint, request, jsonify

from swe_project.api.auth import require_api_key

bp = Blueprint("crud", __name__)

# DynamoDB setup
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "swe-project-model-ratings")
_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(DYNAMODB_TABLE_NAME)


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
