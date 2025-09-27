from __future__ import annotations

import logging
import time
from typing import Any, List

from swe_project.core.hf_client import dataset_info, model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "dataset_quality", "dataset_quality"


def _score_single_dataset(d_info: Any) -> float:
    score = 0.0
    # README.
    if getattr(d_info, "cardData", None):
        score += 0.5

    # preview.
    if getattr(d_info, "viewer", False):
        score += 0.2

    # defined configurations.
    if getattr(d_info, "configs", []):
        score += 0.1

    # popularity.
    if getattr(d_info, "downloads", 0) > 1000:
        score += 0.2
    return min(1.0, score)


def compute(model_url: str) -> MetricResult:
    t0 = time.perf_counter()
    total_score = 0.0
    dataset_ids: List[str] = []

    try:
        rid, _ = to_repo_id(model_url)
        m_info: Any = model_info(rid)

        card = getattr(m_info, "cardData", {})
        if card and isinstance(card, dict):
            dataset_ids = card.get("datasets", [])

        if not dataset_ids:
            # If no datasets are listed, the score is 0.
            return {
                "value": 0.0,
                "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
            }

        for d_id in dataset_ids:
            try:
                d_info = dataset_info(d_id)
                total_score += _score_single_dataset(d_info)
            except Exception:
                logging.warning("%s: failed to fetch info for dataset %s", NAME, d_id)
                total_score += 0.0

        # Average the score across all datasets.
        final_score = total_score / len(dataset_ids)

    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        final_score = 0.0

    return {
        "value": float(max(0.0, min(1.0, final_score))),
        # latency added
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


#

register(NAME, FIELD, compute)
