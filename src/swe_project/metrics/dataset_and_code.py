from __future__ import annotations

import logging
import time
from typing import Any

from swe_project.core.metric_utils import filenames_for_model_or_repo
from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "dataset_and_code", "dataset_and_code"

def compute(input_line: str) -> MetricResult:
    """
    Score based on the presence of datasets, code, and a Space:
      +0.5 if the model card lists datasets or a dataset URL is provided,
      +0.3 if we find any .py files (either in GitHub repo or HF siblings),
      +0.2 if the model has linked Spaces.
    """
    t0 = time.perf_counter()
    try:
        urls = [u.strip() for u in (input_line or "").split(",") if u.strip()]
        code_url = next((u for u in urls if "github.com" in u), None)
        dataset_url = next((u for u in urls if "huggingface.co/datasets/" in u), None)
        model_url = next((u for u in urls if "huggingface.co" in u and "/datasets/" not in u), None)

        if not model_url:
            return {"value": 0.0, "latency_ms": int((time.perf_counter() - t0) * 1000)}

        rid, _ = to_repo_id(model_url)
        info: Any = model_info(rid)  # tests patch THIS (dca.model_info)

        score = 0.0

        # datasets present?
        card_datasets = (getattr(info, "cardData", {}) or {}).get("datasets", [])
        if dataset_url or card_datasets:
            score += 0.5

        # code files present?
        repo_to_check = code_url or model_url
        filenames = filenames_for_model_or_repo(repo_to_check, existing_info=info)
        if any(str(f).endswith(".py") for f in filenames):
            score += 0.3

        # space linked?
        if getattr(info, "spaces", []) or getattr(info, "siblings", []) and any(
            str(getattr(s, "rfilename", "")).startswith("spaces/")
            for s in getattr(info, "siblings", [])
        ):
            score += 0.2

        return {
            "value": max(0.0, min(1.0, float(score))),
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    except Exception:
        logging.exception("%s failed for %s", NAME, input_line)
        return {"value": 0.0, "latency_ms": int((time.perf_counter() - t0) * 1000)}

register(NAME, FIELD, compute)
# Keep legacy alias so CLI/tests looking for the old field still work.
register("dataset_and_code_score", "dataset_and_code_score", compute)
