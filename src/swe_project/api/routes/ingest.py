# src/api/routes/ingest.py
from flask import Blueprint, request, jsonify

from src.swe_project.api.artifacts_store import STORE

bp = Blueprint('ingest', __name__)


def _detect_artifact_type(url: str) -> str:
    """Detect artifact type from URL."""
    url_lower = url.lower()
    # GitHub URLs are code
    if "github.com" in url_lower:
        return "code"
    # HuggingFace datasets
    if "huggingface.co/datasets" in url_lower:
        return "dataset"
    # HuggingFace models (default for huggingface)
    if "huggingface.co" in url_lower:
        return "model"
    # Default to model
    return "model"


@bp.route('/ingest', methods=['POST'])
def ingest_model():
    """Ingest a URL into the system as an artifact."""
    data = request.get_json() or {}
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Missing required field: url'}), 400
    
    # Detect artifact type from URL or use provided type
    artifact_type = data.get('type') or _detect_artifact_type(url)
    
    # Normalize type
    type_map = {"model": "model", "models": "model", "dataset": "dataset", "datasets": "dataset", "code": "code"}
    atype = type_map.get(artifact_type.lower(), "model")
    
    try:
        rec = STORE.create(atype, url)
    except FileExistsError:
        # Already exists - just return success for idempotency
        return jsonify({
            'status': 'success',
            'message': f'Artifact already exists: {url}'
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    return jsonify({
        'status': 'success',
        'message': f'Artifact ingested: {url}',
        'artifact': rec
    }), 201