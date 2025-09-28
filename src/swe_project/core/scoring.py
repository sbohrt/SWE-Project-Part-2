from __future__ import annotations

from typing import Dict

# Adjust and document these report
DEFAULT_WEIGHTS: Dict[str, float] = {
    "ramp_up_time": 0.15,
    "bus_factor": 0.10,
    "license": 0.10,
    "size_score": 0.10,  # average across device scores
    "dataset_and_code": 0.15,
    "dataset_quality": 0.15,
    "code_quality": 0.10,
    "performance_claims": 0.15,
}


def combine(scalars: Dict[str, float]) -> float:
    wsum = sum(DEFAULT_WEIGHTS.values()) or 1.0
    total = 0.0
    for k, w in DEFAULT_WEIGHTS.items():
        total += w * float(scalars.get(k, 0.0))
    # clamp
    total = total / wsum
    return max(0.0, min(1.0, total))
