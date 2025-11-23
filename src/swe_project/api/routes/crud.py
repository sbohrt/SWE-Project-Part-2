# src/api/routes/crud.py
from flask import Blueprint, request, jsonify

bp = Blueprint("crud", __name__)

# Temporary in-memory storage (replace with DynamoDB later)
models_db = {}

@bp.route('/models', methods=['GET'])
def list_models():
    """List all models"""
    return jsonify(list(models_db.values())), 200

@bp.route('/models/<model_id>', methods=['GET'])
def get_model(model_id):
    """Get specific model by ID"""
    if model_id not in models_db:
        return jsonify({"error": "Model not found"}), 404
    return jsonify(models_db[model_id]), 200

@bp.route('/models', methods=['POST'])
def create_model():
    """Add a new model"""
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({"error": "Missing required field: id"}), 400
    
    model_id = data['id']
    if model_id in models_db:
        return jsonify({"error": "Model already exists"}), 409
    
    models_db[model_id] = data
    return jsonify(data), 201

@bp.route('/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    """Update an existing model"""
    if model_id not in models_db:
        return jsonify({"error": "Model not found"}), 404
    
    data = request.get_json()
    models_db[model_id].update(data)
    return jsonify(models_db[model_id]), 200

@bp.route('/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    """Delete a model"""
    if model_id not in models_db:
        return jsonify({"error": "Model not found"}), 404
    
    deleted = models_db.pop(model_id)
    return jsonify({"message": "Model deleted", "model": deleted}), 200