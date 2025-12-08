from flask import Blueprint, request, jsonify
from ..store import STORE

ingest_bp = Blueprint("ingest", __name__, url_prefix="/ingest")


@ingest_bp.route("", methods=["POST"])
def ingest():
    # Accept: { "urls": [...] } or { "url": "..." }
    data = request.get_json(silent=True) or {}

    urls = data.get("urls")
    if not urls:
        single = data.get("url")
        urls = [single] if single else None

    if not urls or not isinstance(urls, list):
        return jsonify({"error": "bad_request", "message": "Need 'url' or 'urls'"}), 400

    # For now, we do NOT process immediately — we just create a queued job.
    # Later we will attach a worker / SQS / Celery consumer.
    job_id = STORE.job_create({"urls": urls})

    return jsonify({"job_id": job_id, "status": "queued"}), 202


@ingest_bp.route("/jobs/<job_id>", methods=["GET"])
def job_status(job_id):
    job = STORE.job_get(job_id)
    if not job:
        return jsonify({"error": "not_found"}), 404
    return jsonify(job), 200
