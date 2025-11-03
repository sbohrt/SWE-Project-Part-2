from src.metrics.base import registered
from src.core.scoring import combine
from src.core.url_ctx import set_context

import src.metrics.bus_factor          # noqa: F401
import src.metrics.code_quality        # noqa: F401
import src.metrics.dataset_and_code    # noqa: F401
import src.metrics.dataset_quality     # noqa: F401
import src.metrics.license             # noqa: F401
import src.metrics.performance_claims  # noqa: F401
import src.metrics.ramp_up_time        # noqa: F401
import src.metrics.size_score          # noqa: F401


def compute_all(model_url, code_url=None, dataset_url=None):
    set_context(model_url, code_url, dataset_url)

    metrics = {}
    latencies_ms = {}

    for name, field, compute in registered():
        try:
            res = compute(model_url)  # {"value": any, "latency_ms": int}
        except Exception:
            res = {"value": 0.0, "latency_ms": 0}

        val = res.get("value")
        lat = int(res.get("latency_ms", 0))
        latencies_ms[field] = lat

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
