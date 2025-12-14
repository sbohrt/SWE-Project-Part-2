# src/swe_project/api/routes/rate.py
"""
Rate endpoint for scoring models.

SECURITY FIX: Added URL validation to prevent SSRF attacks.
"""
from flask import Blueprint, request, jsonify

from src.swe_project.api.validators import validate_model_url
from src.cli import score_single_model

bp = Blueprint("rate", __name__)


@bp.route("/rate", methods=["POST"])
def rate():
    """
    POST /api/v1/rate

    Score a model from a given URL.

    Request body:
        {
            "url": "https://huggingface.co/model-name"
        }

    Returns:
        200: Model score data
        400: Invalid input or scoring error
    """
    # Use silent=True to prevent Flask from raising exceptions on malformed JSON
    data = request.get_json(silent=True)

    # Check if JSON parsing failed (returns None for malformed JSON)
    if data is None:
        return jsonify({
            'error': 'BadRequest',
            'message': 'Request body must be valid JSON'
        }), 400

    url = data.get('url')

    if not url:
        return jsonify({
            'error': 'BadRequest',
            'message': 'Missing required field: url'
        }), 400

    # SECURITY FIX: Validate URL to prevent SSRF attacks
    is_valid, error_msg = validate_model_url(url)
    if not is_valid:
        return jsonify({
            'error': 'BadRequest',
            'message': f'Invalid URL: {error_msg}'
        }), 400

    # Score the model using Phase 1 logic
    try:
        result = score_single_model(url)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'error': 'InternalError',
            'message': f'Failed to score model: {str(e)}'
        }), 500
