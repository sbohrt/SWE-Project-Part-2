from __future__ import annotations

import logging
import time
from typing import Any

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id

# NEW: pull code_url from the CSV context (if present)
# (If code_url is GitHub (not HF), we intentionally keep the original behavior
# and still inspect the HF model repo (no logic change)).
from swe_project.core.url_ctx import get_code_url
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "code_quality", "code_quality"


def compute(model_url: str) -> MetricResult:
    """
    Computes a code quality score based on the presence of key files in the model repo.
    Metric suggested by LLM: Gemini.
    Prompt: What would be a good metric to measure the code quality of a model repo?

    The score is based on:
    - 0.4 points for a requirements.txt or pyproject.toml file.
    - 0.3 points for any Python (.py) source files.
    - 0.3 points for a config.json file.
    """
    t0 = time.perf_counter()
    score = 0.0
    try:
        # NEW
        prefer_url = get_code_url(model_url) or model_url
        rid, _ = to_repo_id(prefer_url)

        info: Any = model_info(rid)

        siblings = getattr(info, "siblings", [])
        filenames = {s.rfilename for s in siblings}

        # 1. Check for dependency management files.
        if "requirements.txt" in filenames or "pyproject.toml" in filenames:
            score += 0.4

        # 2. Check for Python source code.
        if any(f.endswith(".py") for f in filenames):
            score += 0.3

        # 3. Check for a model configuration file.
        if "config.json" in filenames:
            score += 0.3

    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        score = 0.0

    final_score = max(0.0, min(1.0, score))

    return {
        "value": float(final_score),
        # lentency
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)
