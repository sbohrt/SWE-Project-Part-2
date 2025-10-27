from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register
from swe_project.core.gh_utils import get_github_repo_files


NAME, FIELD = "code_quality", "code_quality"


def _score_single_url(analysis_url: str) -> float:
    score = 0.0
    try:
        filenames = set()
        is_github = "github.com" in analysis_url

        if is_github:
            filenames = get_github_repo_files(analysis_url)
        else:
            rid, _ = to_repo_id(analysis_url)
            info: Any = model_info(rid)
            siblings = getattr(info, "siblings", [])
            filenames = {s.rfilename for s in siblings}

        total_files = len(filenames)

        if total_files > 0:
            if is_github:
                if "requirements.txt" in filenames:
                    score += 0.5
                py_files_count = sum(1 for f in filenames if f.endswith(".py"))
                if py_files_count > 0:
                    score += (py_files_count / total_files) * 0.5
            else:
                py_files_count = sum(1 for f in filenames if f.endswith(".py"))
                has_deps = (
                    "requirements.txt" in filenames
                    or "pyproject.toml" in filenames
                    or "config.json" in filenames
                )
                if py_files_count > 0:
                    if has_deps:
                        score += 0.3
                    score += (py_files_count / total_files) * 0.7
                elif has_deps:
                    score = 0.3

    except Exception:
        logging.exception("Sub-computation failed for %s", analysis_url)
        return 0.0

    return score


def compute(input_line: str) -> MetricResult:
    t0 = time.perf_counter()
    total_score = 0.0
    urls = [url.strip() for url in input_line.split(",") if url.strip()]

    relevant_urls = [
        url
        for url in urls
        if "github.com" in url or ("huggingface.co" in url and "/datasets/" not in url)
    ]

    if not relevant_urls:
        return {
            "value": 0.0,
            "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
        }

    for url in relevant_urls:
        total_score += _score_single_url(url)

    final_score = max(0.0, min(1.0, total_score))
    return {
        "value": float(final_score),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)

# if __name__ == "__main__":
#     import sys
#     import json

#     if len(sys.argv) > 1:
#         input_line = " ".join(sys.argv[1:])
#         result = compute(input_line=input_line)
#         print(json.dumps(result))
#     else:
#         print("Usage: python -m swe_project.metrics.code_quality <URL1, URL2, ...>", file=sys.stderr)
