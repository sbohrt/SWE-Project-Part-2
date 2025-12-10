from __future__ import annotations

import re
from flask import Blueprint, jsonify, request

from src.swe_project.api.artifacts_store import STORE, _normalize_type


artifacts_bp = Blueprint("artifacts", __name__)


def _json_error(status_code: int, message: str):
    return jsonify({"error": message}), status_code


@artifacts_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@artifacts_bp.route("/reset", methods=["DELETE"])
def reset():
    STORE.reset()
    return jsonify({"message": "reset"}), 200


@artifacts_bp.route("/artifact/<artifact_type>", methods=["POST"])
def artifact_create(artifact_type):
    atype = _normalize_type(artifact_type)
    if atype is None:
        return _json_error(400, "invalid artifact_type")
    data = request.get_json(silent=True) or {}
    url = data.get("url") if isinstance(data, dict) else None
    if not url:
        return _json_error(400, "missing url")
    try:
        rec = STORE.create(atype, url)
    except FileExistsError:
        return _json_error(409, "artifact exists")
    except ValueError as e:
        return _json_error(400, str(e))
    return jsonify(rec), 201


@artifacts_bp.route("/artifact/<artifact_type>/<artifact_id>", methods=["GET"])
def artifact_get(artifact_type, artifact_id):
    atype = _normalize_type(artifact_type)
    if atype is None:
        return _json_error(400, "invalid artifact_type")
    rec = STORE.get(artifact_id)
    if not rec or rec["metadata"]["type"] != atype:
        return _json_error(404, "not found")
    return jsonify(rec), 200


@artifacts_bp.route("/artifact/<artifact_type>/<artifact_id>", methods=["PUT"])
def artifact_update(artifact_type, artifact_id):
    atype = _normalize_type(artifact_type)
    if atype is None:
        return _json_error(400, "invalid artifact_type")
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _json_error(400, "invalid body")
    ok = STORE.update(atype, artifact_id, body)
    if not ok:
        # differentiate not found vs bad payload
        rec = STORE.get(artifact_id)
        if not rec:
            return _json_error(404, "not found")
        return _json_error(400, "invalid artifact payload")
    rec = STORE.get(artifact_id)
    return jsonify(rec), 200


@artifacts_bp.route("/artifact/<artifact_type>/<artifact_id>", methods=["DELETE"])
def artifact_delete(artifact_type, artifact_id):
    atype = _normalize_type(artifact_type)
    if atype is None:
        return _json_error(400, "invalid artifact_type")
    ok = STORE.delete(atype, artifact_id)
    if not ok:
        return _json_error(404, "not found")
    return jsonify({"message": "deleted"}), 200


@artifacts_bp.route("/artifacts", methods=["POST"])
def artifacts_list():
    body = request.get_json(silent=True)
    if not isinstance(body, list) or not body:
        return _json_error(400, "missing artifact_query array")

    queries = []
    for q in body:
        if not isinstance(q, dict) or "name" not in q:
            return _json_error(400, "invalid artifact_query")
        name = q.get("name")
        types = q.get("types")
        if types is not None and not isinstance(types, list):
            return _json_error(400, "invalid types")
        queries.append({"name": name, "types": types})

    offset = request.args.get("offset")
    recs = STORE.list_by_queries(queries, offset=offset)
    # Build metadata-only response
    resp = [
        {
            "name": r["metadata"]["name"],
            "id": r["metadata"]["id"],
            "type": r["metadata"]["type"],
        }
        for r in recs
    ]
    response = jsonify(resp)
    response.headers["offset"] = "0"
    return response, 200


@artifacts_bp.route("/artifact/byName/<name>", methods=["GET"])
def artifact_by_name(name):
    recs = STORE.list_by_name(name)
    if not recs:
        return _json_error(404, "not found")
    resp = [
        {
            "name": r["metadata"]["name"],
            "id": r["metadata"]["id"],
            "type": r["metadata"]["type"],
        }
        for r in recs
    ]
    return jsonify(resp), 200


@artifacts_bp.route("/artifact/byRegEx", methods=["POST"])
def artifact_by_regex():
    body = request.get_json(silent=True) or {}
    regex = body.get("regex")
    if not regex or not isinstance(regex, str):
        return _json_error(400, "invalid regex")
    try:
        recs = STORE.list_by_regex(regex)
    except re.error:
        return _json_error(400, "invalid regex")
    if not recs:
        return _json_error(404, "not found")
    resp = [
        {
            "name": r["metadata"]["name"],
            "id": r["metadata"]["id"],
            "type": r["metadata"]["type"],
        }
        for r in recs
    ]
    return jsonify(resp), 200

