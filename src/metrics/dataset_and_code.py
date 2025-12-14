from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests
from core.hf_client import model_info
from core.model_url import to_repo_id
from metrics.base import MetricResult, register

NAME, FIELD = "dataset_and_code", "dataset_and_code"


def _gh_headers() -> Dict[str, str]:
    """Creates headers for GitHub API requests, including authorization if available."""
    hdrs: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "swe-project-dataset-and-code/1.0",
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
        logging.warning("[dataset_and_code] Network error for %s: %s", url, e)
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
                "[dataset_and_code] Retry without auth failed for %s: %s", url, e
            )
            return None

    if res.status_code != 200:
        logging.warning(
            "[dataset_and_code] GET %s returned status %s", url, res.status_code
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

        repo_to_check_for_code = code_url or model_url
        filenames = set()
        if "github.com" in repo_to_check_for_code:
            filenames = get_github_repo_files(repo_to_check_for_code)
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
