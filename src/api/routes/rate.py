from flask import Blueprint, request, jsonify

from ..scoring import compute_all

rate_bp = Blueprint("rate", __name__)

# POST /rate
@rate_bp.route("/rate", methods=["POST"])
def rate():
    # expect: {"url": "...", "code_url": "...", "dataset_url": "..."} (code/dataset optional)
    data = request.get_json(silent=True) or {}
    url = data.get("url") or data.get("model_url")
    if not url or not isinstance(url, str):
        return jsonify({"error": "bad_request", "message": "Missing 'url'"}), 400

    code_url = data.get("code_url")
    dataset_url = data.get("dataset_url")

    try:
        result = compute_all(url, code_url=code_url, dataset_url=dataset_url)
    except Exception as e:
        # never 500 for Delivery 1 — always return stable shape
        return jsonify({
            "model_url": url,
            "metrics": {
                "ramp_up_time": 0.0,
                "bus_factor": 0.0,
                "license": 0.0,
                "size_score": 0.0,
                "dataset_and_code_score": 0.0,
                "dataset_quality": 0.0,
                "code_quality": 0.0,
                "performance_claims": 0.0,
            },
            "latencies_ms": {},
            "net_score": 0.0,
            "error": str(e),
        }), 200

    # normal case
    return jsonify({"model_url": url, **result}), 200
