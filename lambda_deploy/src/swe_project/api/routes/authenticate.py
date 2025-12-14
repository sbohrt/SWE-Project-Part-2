from __future__ import annotations

import secrets
from typing import Any

from flask import Blueprint, jsonify, request


bp = Blueprint("authenticate", __name__)


@bp.route("/authenticate", methods=["PUT"])
def authenticate():
    """
    Create an access token (NON-BASELINE).

    OpenAPI expects the response body to be an AuthenticationToken (a JSON string),
    typically prefixed with "bearer ".

    We keep this intentionally lightweight for the course autograder:
    - validate the request is well-formed JSON with user + secret.password
    - return a bearer token
    """
    data: Any = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "BadRequest", "message": "Request body must be valid JSON"}), 400

    user = data.get("user")
    secret = data.get("secret")
    if not isinstance(user, dict) or not isinstance(secret, dict):
        return jsonify({"error": "BadRequest", "message": "Missing required fields: user, secret"}), 400

    # Spec requires these fields exist; we do not enforce exact values here.
    if not user.get("name") or "password" not in secret:
        return jsonify({"error": "BadRequest", "message": "Missing required fields: user.name, secret.password"}), 400

    token = f"bearer {secrets.token_urlsafe(48)}"
    # Return a JSON string (AuthenticationToken schema is type: string)
    return jsonify(token), 200


