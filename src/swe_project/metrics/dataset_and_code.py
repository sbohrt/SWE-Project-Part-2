from __future__ import annotations

import logging
import time
from typing import Any

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "dataset_and_code_score", "dataset_and_code_score"


def compute(model_url: str) -> MetricResult:
    # - 0.5 points if the model card explicitly lists datasets.
    # - 0.3 points if the repository contains Python source files.
    # - 0.2 points if the model is linked to a Hugging Face Space.

    t0 = time.perf_counter()
    score = 0.0
    try:
        rid, _ = to_repo_id(model_url)
        info: Any = model_info(rid)

        # 1. Check for datasets listed in the model card.
        card = getattr(info, "cardData", {})
        if card and card.get("datasets"):
            score += 0.5

        # 2. Check for Python code files in the repository.
        siblings = getattr(info, "siblings", [])
        if any(s.rfilename.endswith(".py") for s in siblings):
            score += 0.3

        # 3. Check for linked Hugging Face Spaces (demos).
        spaces = getattr(info, "spaces", [])
        if spaces and len(spaces) > 0:
            score += 0.2

    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        # On failure, score is 0.
        score = 0.0

    # Ensure the score is clamped between 0.0 and 1.0.
    final_score = max(0.0, min(1.0, score))

    return {
        "value": float(final_score),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


# Register the metric with the central registry.
register(NAME, FIELD, compute)
