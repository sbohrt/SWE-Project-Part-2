from flask import Blueprint, request, jsonify

from ..store import STORE

crud_bp = Blueprint("crud", __name__, url_prefix="/models")

# POST /models
@crud_bp.route("", methods=["POST"])
def create_model():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "bad_request", "message": "Missing 'name'"}), 400
    _id = STORE.create(data)
    return jsonify({"id": _id}), 201

# GET /models
@crud_bp.route("", methods=["GET"])
def list_models():
    items = STORE.list()
    return jsonify({"items": items, "count": len(items)}), 200

# GET /models/<id>
@crud_bp.route("/<mid>", methods=["GET"])
def get_model(mid):
    item = STORE.get(mid)
    if not item:
        return jsonify({"error": "not_found"}), 404
    return jsonify(item), 200

# PUT /models/<id>
@crud_bp.route("/<mid>", methods=["PUT"])
def update_model(mid):
    patch = request.get_json(silent=True) or {}
    if not STORE.update(mid, patch):
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": "ok"}), 200

# DELETE /models/<id>
@crud_bp.route("/<mid>", methods=["DELETE"])
def delete_model(mid):
    if not STORE.delete(mid):
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": "ok"}), 200
