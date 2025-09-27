from __future__ import annotations

import logging
import time
from typing import Any

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.core.url_ctx import get_code_url, get_dataset_url
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

        # 1. Dataset Check (0.5 points)
        # Prioritize the URL from the input file, then fall back to the model card.
        if get_dataset_url(model_url):
            score += 0.5
        else:
            card = getattr(info, "cardData", {})
            if card and card.get("datasets"):
                score += 0.5

        # 2. Code Check (0.3 points)
        # This check is now dependent on finding a `code_url` in the input file.
        code_url = get_code_url(model_url)
        if code_url:
            code_rid, _ = to_repo_id(code_url)
            code_info = model_info(code_rid) if code_rid != rid else info
            siblings = getattr(code_info, "siblings", [])
            if any(s.rfilename.endswith(".py") for s in siblings):
                score += 0.3

        # 3. Hugging Face Space Check (0.2 points)
        spaces = getattr(info, "spaces", [])
        if spaces and len(spaces) > 0:
            score += 0.2

    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        score = 0.0

    # Ensure the score is clamped between 0.0 and 1.0.
    final_score = max(0.0, min(1.0, score))

    return {
        "value": float(final_score),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)
