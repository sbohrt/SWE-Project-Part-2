from __future__ import annotations

import logging
import time
from typing import Any, Set

from swe_project.core.gh_utils import (  # noqa: F401
    get_github_repo_files as get_github_repo_files,
)

# Re-export these so tests can patch them on this module:
from swe_project.core.hf_client import model_info as model_info  # noqa: F401
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "code_quality", "code_quality"


def _filenames_for(url: str) -> Set[str]:
    """Tiny local wrapper so tests can patch model_info/get_github_repo_files and affect behavior."""
    if "github.com" in url:
        return set(get_github_repo_files(url))
    rid, _ = to_repo_id(url)
    info: Any = model_info(rid)
    siblings = getattr(info, "siblings", []) or []
    return {
        getattr(s, "rfilename", "") for s in siblings if getattr(s, "rfilename", "")
    }


def _score_from_filenames(filenames: Set[str], is_github: bool) -> float:
    score = 0.0
    total = len(filenames)
    if total == 0:
        return 0.0
    py_count = sum(1 for f in filenames if str(f).endswith(".py"))
    has_deps = any(
        n in filenames for n in ("requirements.txt", "pyproject.toml", "config.json")
    )

    if is_github:
        if "requirements.txt" in filenames:
            score += 0.5
        if py_count > 0:
            score += (py_count / total) * 0.5
    else:
        if py_count > 0:
            if has_deps:
                score += 0.3
            score += (py_count / total) * 0.7
        elif has_deps:
            score = 0.3

    return max(0.0, min(1.0, score))


def compute(input_line: str) -> MetricResult:
    t0 = time.perf_counter()
    try:
        urls = [u.strip() for u in input_line.split(",") if u.strip()]
        targets = [
            u
            for u in urls
            if ("github.com" in u) or ("huggingface.co" in u and "/datasets/" not in u)
        ]
        if not targets:
            return {
                "value": 0.0,
                "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
            }

        total = 0.0
        for url in targets:
            filenames = _filenames_for(url)
            total += _score_from_filenames(filenames, is_github=("github.com" in url))

        final = max(0.0, min(1.0, total))
        return {
            "value": float(final),
            "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
        }
    except Exception:
        logging.exception("code_quality failed for %r", input_line)
        return {
            "value": 0.0,
            "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
        }


register(NAME, FIELD, compute)
