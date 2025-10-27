from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

from swe_project.core.metric_utils import parse_urls, filenames_for_model_or_repo
from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.core.gh_utils import gh_get as _gh_get, gh_headers as _gh_headers, get_github_repo_files


code_url, dataset_url, model_url = parse_urls(input_line)


NAME, FIELD = "dataset_and_code", "dataset_and_code"


def compute(input_line: str) -> MetricResult:
    # Computes a score based on the availability of datasets, code, and demos.
    # - 0.5 if a dataset is linked in the input or on the model card.
    # - 0.3 if Python files are found in the model or linked code repo.
    # - 0.2 if the model is linked to a Hugging Face Space.
    t0 = time.perf_counter()
    score = 0.0

    urls = [url.strip() for url in input_line.split(",") if url.strip()]
    code_url = next((url for url in urls if "github.com" in url), None)
    dataset_url = next((url for url in urls if "huggingface.co/datasets/" in url), None)
    model_url = next(
        (url for url in urls if "huggingface.co" in url and "/datasets/" not in url),
        None,
    )

    if not model_url:
        return {
            "value": 0.0,
            "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
        }

    try:
        rid, _ = to_repo_id(model_url)
        m_info: Any = model_info(rid)

        card_datasets = getattr(m_info, "cardData", {}).get("datasets", [])
        if dataset_url or card_datasets:
            score += 0.5

        repo_to_check = code_url or model_url
        filenames = filenames_for_model_or_repo(repo_to_check, existing_info=m_info)
        if "github.com" in repo_to_check:
            filenames = get_github_repo_files(repo_to_check)
        else:
            code_rid, _ = to_repo_id(repo_to_check_for_code)
            info_for_code = m_info if code_rid == rid else model_info(code_rid)
            siblings = getattr(info_for_code, "siblings", [])
            filenames = {s.rfilename for s in siblings}

        if any(f.endswith(".py") for f in filenames):
            score += 0.3

        if getattr(m_info, "spaces", []):
            score += 0.2

    except Exception:
        logging.exception("%s failed for %s", NAME, model_url)
        score = 0.0

    final_score = max(0.0, min(1.0, score))
    return {
        "value": float(final_score),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)
register("dataset_and_code_score", "dataset_and_code_score", compute)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        input_line = " ".join(sys.argv[1:])
        result = compute(input_line=input_line)
        print(json.dumps(result))
    else:
        print(
            "Usage: python -m swe_project.metrics.dataset_and_code <URL1, URL2, ...>",
            file=sys.stderr,
        )
