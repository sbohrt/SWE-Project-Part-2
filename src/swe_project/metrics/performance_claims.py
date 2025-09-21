from __future__ import annotations

import logging
import re
import time
from typing import Any

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import register

NAME, FIELD = "performance_claims", "performance_claims"
_METRIC_PAT = re.compile(r"\b(accuracy|f1|bleu|rouge|map|auc|perplexity)\b", re.I)


def compute(model_url: str):
    t0 = time.perf_counter()
    score = 0.0
    try:
        rid, _ = to_repo_id(model_url)
        info: Any = model_info(rid)
        likes = getattr(info, "likes", 0) or 0
        downloads = getattr(info, "downloads", 0) or 0
        # model-index evidence
        card = getattr(info, "cardData", None) or {}
        model_index = card.get("model-index") if isinstance(card, dict) else None
        if model_index:
            score += 0.5
            # crude richness scan
            for entry in model_index or []:
                for res in entry.get("results", []):
                    if res.get("task") and res.get("metrics"):
                        score += 0.1
                        if res.get("dataset"):
                            score += 0.05
            score = min(score, 0.9)
        # popularity nudges
        if likes >= 50:
            score += 0.05
        if downloads >= 10_000:
            score += 0.05
    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        score = 0.0

    score = max(0.0, min(1.0, score))
    return {
        "value": float(score),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)
