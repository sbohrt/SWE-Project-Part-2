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

NAME, FIELD = "code_quality", "code_quality"


def _gh_headers() -> Dict[str, str]:
    """Creates headers for GitHub API requests, including authorization if available."""
    hdrs: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "swe-project-code-quality/1.0",
    }
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if tok and tok.lower() not in {"invalid", "none", "placeholder"}:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def _gh_get(
    url: str, params: Optional[Dict[str, str]] = None, timeout: int = 10
) -> Optional[requests.Response]:
    """
    Performs a GET request to the GitHub API with robust error handling.
    Retries once without authorization on 401/403 errors.
    """
    params = params or {}
    hdrs = _gh_headers()
    try:
        res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
    except requests.RequestException as e:
        logging.warning("[code_quality] Network error for %s: %s", url, e)
        return None

    text_lower = (res.text or "").lower()
    if res.status_code in (401, 403) and (
        "bad credentials" in text_lower or "requires authentication" in text_lower
    ):
        # Retry once without the auth header if token is bad
        hdrs = {k: v for k, v in hdrs.items() if k.lower() != "authorization"}
        try:
            res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
        except requests.RequestException as e:
            logging.warning(
                "[code_quality] Retry without auth failed for %s: %s", url, e
            )
            return None

    if res.status_code != 200:
        logging.warning(
            "[code_quality] GET %s returned status %s", url, res.status_code
        )
        return None
    return res


def get_github_repo_files(repo_url: str) -> set[str]:
    """Fetches the list of all files in a GitHub repository's default branch."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url.replace(".git", ""))
    if not match:
        return set()

    owner, repo = match.groups()

    # Get repository info to find the default branch
    repo_info_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_res = _gh_get(repo_info_url)
    if not repo_res:
        logging.error(f"Failed to fetch repo info from {repo_info_url}")
        return set()

    try:
        default_branch = repo_res.json().get("default_branch", "main")
    except (requests.exceptions.JSONDecodeError, AttributeError):
        logging.error(f"Could not parse JSON or find default_branch for {repo_url}")
        return set()

    # Get the file tree for the default branch
    trees_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    tree_res = _gh_get(trees_url)
    if not tree_res:
        logging.error(f"Failed to fetch file tree from {trees_url}")
        return set()

    try:
        data = tree_res.json()
        if "tree" not in data:
            logging.warning(
                f"Response from {trees_url} is truncated: {data.get('message', '')}"
            )
            return set()
        return {item["path"] for item in data.get("tree", []) if item["type"] == "blob"}
    except (requests.exceptions.JSONDecodeError, AttributeError):
        logging.error(f"Could not parse JSON response for file tree of {repo_url}")
        return set()


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
