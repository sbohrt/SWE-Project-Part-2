# src/swe_project/api/routes/rate.py
from flask import Blueprint, request, jsonify
import time

from core.exec_pool import run_parallel
from core.scoring import combine
from metrics.base import registered
from core.url_ctx import set_context

bp = Blueprint("rate", __name__)


def _load_metrics():
    """Lazy load metrics only when needed so registration runs."""
    from metrics import bus_factor
    from metrics import code_quality
    from metrics import dataset_and_code
    from metrics import dataset_quality
    from metrics import license_check
    from metrics import performance
    from metrics import rampup
    from metrics import size

    # Touch modules so their @register decorators run.
    _ = [
        bus_factor,
        code_quality,
        dataset_and_code,
        dataset_quality,
        license_check,
        performance,
        rampup,
        size,
    ]
    return registered()


@bp.route("/rate", methods=["POST"])
def rate():
    """Rate a model by URL, returning net score + per-metric scores."""
    body = request.get_json(silent=True) or {}

    url = body.get("url") or body.get("model_url")
    code_url = body.get("code_url")
    dataset_url = body.get("dataset_url")

    if not url or not isinstance(url, str):
        return jsonify({"error": "bad_request", "message": "Missing 'url'"}), 400

    metrics = _load_metrics()

    # Build jobs: one job per metric
    def make_job(metric_cls):
        def job():
            with set_context(url=url, code_url=code_url, dataset_url=dataset_url):
                t0 = time.time()
                value = metric_cls().compute()
                latency_ms = (time.time() - t0) * 1000.0
                return metric_cls.key, {"value": value, "latency_ms": latency_ms}

        return job

    jobs = [make_job(m) for m in metrics]

    t0_all = time.time()
    results_list = run_parallel(jobs)
    net_latency_ms = (time.time() - t0_all) * 1000.0

    results = {k: v for (k, v) in results_list}

    def _val(key, default=None):
        info = results.get(key) or {}
        return info.get("value", default)

    scalars = {
        "bus_factor": _val("bus_factor"),
        "ramp_up": _val("ramp_up"),
        "responsiveness": _val("responsiveness"),
        "license": _val("license"),
        "dataset_and_code_score": _val("dataset_and_code_score"),
        "dataset_quality": _val("dataset_quality"),
        "code_quality": _val("code_quality"),
        "performance_claims": _val("performance_claims"),
        "size_score": _val("size_score"),
    }

    net_score = combine(scalars)

    return (
        jsonify(
            {
                "net_score": net_score,
                "net_score_latency": net_latency_ms,
                "metrics": results,
            }
        ),
        200,
    )
