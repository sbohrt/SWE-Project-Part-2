# src/api/routes/rate.py
from flask import Blueprint, request, jsonify
from swe_project.acemcli.orchestrator import compute_all
   
bp = Blueprint('rate', __name__)

@bp.route('/rate', methods=['POST'])
def rate_model():
    data = request.get_json()
    url = data.get('url')
    
    # Reuse Phase 1 logic
    results, errors = compute_all([(url, 'MODEL')])
    
    if errors:
        return jsonify({'error': errors[0][1]}), 400
        
    return jsonify(results[0].__dict__)