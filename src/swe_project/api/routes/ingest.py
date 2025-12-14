# src/api/routes/ingest.py
import os
import boto3
from decimal import Decimal
from flask import Blueprint, request, jsonify

from src.cli import score_single_model

bp = Blueprint('ingest', __name__)

# Configure DynamoDB
dynamodb_config = {}
endpoint_url = os.getenv("AWS_ENDPOINT_URL")
if endpoint_url:
    dynamodb_config = {
        "endpoint_url": endpoint_url,
        "region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    }
_dynamodb = boto3.resource("dynamodb", **dynamodb_config)
_table = _dynamodb.Table("swe-project-model-ratings")


def _convert_to_decimal(obj):
    """Convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_decimal(item) for item in obj]
    return obj


@bp.route('/ingest', methods=['POST'])
def ingest_model():
    """Ingest a HuggingFace model URL into the system"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'Missing required field: url'}), 400

    try:
        # Score the model
        scores = score_single_model(url)

        # Convert floats to Decimal for DynamoDB
        scores_decimal = _convert_to_decimal(scores)

        # Create model ID from URL
        model_id = url.replace("https://huggingface.co/", "").strip("/").replace("/", "-")
        scores_decimal['modelId'] = model_id

        # Save to DynamoDB
        _table.put_item(Item=scores_decimal)

        return jsonify({
            'status': 'success',
            'message': f'Model ingested: {url}',
            'modelId': model_id
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to ingest model: {str(e)}'
        }), 500
