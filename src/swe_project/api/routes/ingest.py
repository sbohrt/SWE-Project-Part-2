# src/api/routes/ingest.py
from flask import Blueprint, request, jsonify

bp = Blueprint('ingest', __name__)

@bp.route('/ingest', methods=['POST'])
def ingest_model():
    """Ingest a HuggingFace model URL into the system"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Missing required field: url'}), 400
    
    # TODO: Implement actual ingest logic
    return jsonify({
        'status': 'success',
        'message': f'Model ingested: {url}'
    }), 200