# src/swe_project/api/auth.py
"""
Authentication and authorization utilities for the API.

SECURITY FIX: API key-based authentication for admin endpoints.
"""
import os
from functools import wraps

from flask import request, jsonify


def require_api_key(f):
    """
    Decorator to require valid API key in X-API-Key header.

    Usage:
        @bp.route('/admin/reset', methods=['DELETE'])
        @require_api_key
        def reset():
            # Only accessible with valid API key
            pass

    The API key is read from the ADMIN_API_KEY environment variable.
    If not set, all requests are rejected (fail-secure).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the API key from environment (fail-secure if not set)
        expected_api_key = os.getenv("ADMIN_API_KEY")

        if not expected_api_key:
            # No API key configured - deny all requests
            return jsonify({
                "error": "Unauthorized",
                "message": "API key authentication not configured"
            }), 500

        # Get the API key from request header
        provided_api_key = request.headers.get("X-API-Key")

        if not provided_api_key:
            return jsonify({
                "error": "Unauthorized",
                "message": "Missing X-API-Key header"
            }), 401

        # Constant-time comparison to prevent timing attacks
        if not _secure_compare(provided_api_key, expected_api_key):
            return jsonify({
                "error": "Forbidden",
                "message": "Invalid API key"
            }), 403

        # API key is valid, proceed with the request
        return f(*args, **kwargs)

    return decorated_function


def _secure_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.

    Standard string comparison (a == b) can leak information about
    the expected value through timing differences.
    """
    import hmac
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))
