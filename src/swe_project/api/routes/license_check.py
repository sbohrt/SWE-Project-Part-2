# src/swe_project/api/routes/license_check.py
"""
License compatibility checking endpoint.

Checks if a GitHub project's license is compatible with a model's license
for fine-tuning and inference/generation use cases.
"""
import os
import re
from typing import Optional, Tuple

import boto3
import requests
from flask import Blueprint, request, jsonify

bp = Blueprint("license_check", __name__)

# DynamoDB setup
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "swe-project-model-ratings")

# Support local DynamoDB for development
dynamodb_config = {}
endpoint_url = os.getenv("AWS_ENDPOINT_URL")
if endpoint_url:
    dynamodb_config = {
        "endpoint_url": endpoint_url,
        "region_name": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    }

_dynamodb = boto3.resource("dynamodb", **dynamodb_config)
_table = _dynamodb.Table(DYNAMODB_TABLE_NAME)


# License compatibility matrix for fine-tune + inference use case
# Based on common open-source license compatibility rules
LICENSE_COMPATIBILITY = {
    # Permissive licenses - compatible with most other licenses
    "mit": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "lgpl-3.0", "mpl-2.0", "gpl-2.0", "gpl-3.0", "agpl-3.0"],
    "apache-2.0": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "lgpl-3.0", "mpl-2.0", "gpl-3.0", "agpl-3.0"],
    "bsd-2-clause": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "lgpl-3.0", "mpl-2.0", "gpl-2.0", "gpl-3.0", "agpl-3.0"],
    "bsd-3-clause": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "lgpl-3.0", "mpl-2.0", "gpl-2.0", "gpl-3.0", "agpl-3.0"],

    # LGPL - can be combined with most licenses
    "lgpl-2.1": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "lgpl-3.0", "gpl-2.0", "gpl-3.0"],
    "lgpl-3.0": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-3.0", "gpl-3.0", "agpl-3.0"],

    # MPL - moderately permissive
    "mpl-2.0": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "mpl-2.0", "gpl-3.0"],

    # GPL - more restrictive
    "gpl-2.0": ["mit", "bsd-2-clause", "bsd-3-clause", "lgpl-2.1", "gpl-2.0"],
    "gpl-3.0": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-3.0", "gpl-3.0", "agpl-3.0"],

    # AGPL - most restrictive
    "agpl-3.0": ["mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "lgpl-3.0", "gpl-3.0", "agpl-3.0"],

    # Proprietary - generally not compatible
    "proprietary": [],
}


def _normalize_license_name(license_str: Optional[str]) -> str:
    """Normalize license string to lowercase SPDX-like identifier."""
    if not license_str:
        return "unknown"

    # Normalize to lowercase and strip
    normalized = license_str.lower().strip()

    # Handle common variations
    aliases = {
        "apache": "apache-2.0",
        "apache 2.0": "apache-2.0",
        "apache2": "apache-2.0",
        "bsd": "bsd-3-clause",
        "lgpl": "lgpl-2.1",
        "gpl": "gpl-3.0",
        "mozilla": "mpl-2.0",
    }

    for alias, canonical in aliases.items():
        if alias in normalized:
            return canonical

    return normalized


def _get_github_license(github_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch license information from a GitHub repository.

    Args:
        github_url: GitHub repository URL

    Returns:
        Tuple of (license_spdx_id, error_message)
    """
    # Extract owner and repo from URL
    # Expected format: https://github.com/owner/repo
    match = re.match(r'https://github\.com/([^/]+)/([^/]+)', github_url.rstrip('/'))
    if not match:
        return None, "Invalid GitHub URL format"

    owner, repo = match.groups()

    # Use GitHub API to get license info
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code == 404:
            return None, "GitHub repository not found"
        elif response.status_code != 200:
            return None, f"GitHub API error: {response.status_code}"

        data = response.json()
        license_info = data.get('license')

        if license_info and license_info.get('spdx_id'):
            spdx_id = license_info['spdx_id'].lower()
            # GitHub uses "NOASSERTION" when license can't be determined
            if spdx_id == 'noassertion':
                return "unknown", None
            return spdx_id, None
        else:
            return "unknown", None

    except requests.exceptions.Timeout:
        return None, "GitHub API request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch GitHub license: {str(e)}"


def _check_license_compatibility(model_license: str, github_license: str) -> bool:
    """
    Check if the licenses are compatible for fine-tune + inference use case.

    Args:
        model_license: Model's license (normalized)
        github_license: GitHub project's license (normalized)

    Returns:
        True if compatible, False otherwise
    """
    model_license = _normalize_license_name(model_license)
    github_license = _normalize_license_name(github_license)

    # If either license is unknown, be conservative and return False
    if model_license == "unknown" or github_license == "unknown":
        return False

    # Check compatibility matrix
    compatible_licenses = LICENSE_COMPATIBILITY.get(model_license, [])
    return github_license in compatible_licenses


@bp.route('/artifact/model/<id>/license-check', methods=['POST'])
def check_model_license_compatibility(id):
    """
    POST /api/v1/artifact/model/{id}/license-check

    Check if a GitHub project's license is compatible with a model's license
    for fine-tuning and inference/generation use cases.

    Path parameters:
        id: Model artifact ID

    Request body:
        {
            "github_url": "https://github.com/owner/repo"
        }

    Returns:
        200: Boolean indicating compatibility
        400: Invalid request
        404: Artifact or GitHub project not found
        502: Failed to retrieve license information
    """
    # Parse request body
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "error": "BadRequest",
            "message": "Request body must be valid JSON"
        }), 400

    github_url = data.get('github_url')
    if not github_url:
        return jsonify({
            "error": "BadRequest",
            "message": "Missing required field: github_url"
        }), 400

    try:
        # Fetch the model artifact from DynamoDB
        response = _table.get_item(Key={'modelId': id})

        if 'Item' not in response:
            return jsonify({
                "error": "NotFound",
                "message": f"Model artifact with id '{id}' not found"
            }), 404

        artifact = response['Item']

        # Get model's license
        # License might be stored as a score (0-1) or as a string
        model_license = artifact.get('license_id', artifact.get('license', 'unknown'))
        if isinstance(model_license, (int, float)):
            # If it's a score, we need to infer the license
            # For now, assume LGPL-2.1 as per project requirements
            model_license = "lgpl-2.1"

        # Get GitHub repository license
        github_license, error = _get_github_license(github_url)

        if error:
            return jsonify({
                "error": "BadGateway",
                "message": error
            }), 502

        # Check compatibility
        is_compatible = _check_license_compatibility(model_license, github_license)

        return jsonify(is_compatible), 200

    except Exception as e:
        return jsonify({
            "error": "InternalError",
            "message": f"Failed to check license compatibility: {str(e)}"
        }), 500
