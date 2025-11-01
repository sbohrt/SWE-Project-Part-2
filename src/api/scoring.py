# reuse existing metrics + combiner with a simple wrapper
from metrics.base import registered
from core.scoring import combine
from core.url_ctx import set_context

# import metric modules so they auto-register via import side-effects
import metrics.bus_factor          # noqa: F401
import metrics.code_quality        # noqa: F401
import metrics.dataset_and_code    # noqa: F401
import metrics.dataset_quality     # noqa: F401
import metrics.license             # noqa: F401
import metrics.performance_claims  # noqa: F401
import metrics.ramp_up_time        # noqa: F401
import metrics.size_score          # noqa: F401


def compute_all(model_url, code_url=None, dataset_url=None):
    # make the optional urls available to any metric that needs them
    set_context(model_url, code_url, dataset_url)

    metrics = {}
    latencies_ms = {}

    # walk all registered metrics and collect values
    for name, field, compute in registered():
        try:
            res = compute(model_url)  # expects {"value": any, "latency_ms": int}
        except Exception:
            res = {"value": 0.0, "latency_ms": 0}

        val = res.get("value")
        lat = int(res.get("latency_ms", 0))
        latencies_ms[field] = lat

        # size_score sometimes returns a dict of device scores, average it
        if field == "size_score" and isinstance(val, dict):
            vals = list(val.values()) if val else [0.0]
            try:
                metrics[field] = sum(float(v) for v in vals) / max(len(vals), 1)
            except Exception:
                metrics[field] = 0.0
        else:
            try:
                metrics[field] = float(val)
            except Exception:
                metrics[field] = 0.0

    net_score = float(combine(metrics))
    return {"metrics": metrics, "latencies_ms": latencies_ms, "net_score": net_score}
