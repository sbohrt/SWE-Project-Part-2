from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "dataset_and_code", "dataset_and_code"


def get_github_repo_files(repo_url: str) -> set[str]:
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url.replace(".git", ""))
    if not match:
        return set()

    owner, repo = match.groups()
    headers = {}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {token}"

    try:
        repo_info_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(repo_info_url, headers=headers, timeout=10)
        response.raise_for_status()
        default_branch = response.json().get("default_branch", "main")

        trees_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
        response = requests.get(trees_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {item["path"] for item in data.get("tree", []) if item["type"] == "blob"}
    except requests.RequestException as e:
        logging.error(f"Failed to fetch files from GitHub repo {repo_url}: {e}")
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
            "Usage: python -m swe_project.metrics.dataset_and_code_score <URL1, URL2, ...>",
            file=sys.stderr,
        )

# if __name__ == "__main__":
#     import sys
#     import json
#     import os

#     if len(sys.argv) > 1:
#         first_arg = sys.argv[1]
#         lines_to_process = []

#         # Check if the input is a file path that exists
#         if os.path.isfile(first_arg):
#             try:
#                 with open(first_arg, 'r') as f:
#                     lines_to_process = f.readlines()
#             except IOError as e:
#                 print(f"Error reading file: {e}", file=sys.stderr)
#                 sys.exit(1)
#         else:
#             # If not a file, treat all arguments as one comma-separated line
#             lines_to_process = [" ".join(sys.argv[1:])]

#         for line in lines_to_process:
#             line = line.strip()
#             if not line:
#                 continue

#             result = compute(input_line=line)
#             # Add the original line to the output for context during testing
#             output_data = {
#                 "input_line": line,
#                 "dataset_and_code_score": result["value"],
#                 "dataset_and_code_score_latency": result["latency_ms"]
#             }
#             print(json.dumps(output_data))

#     else:
#         print("Usage 1 (for autograder): python -m ... <path_to_url_file>", file=sys.stderr)
#         print("Usage 2 (for testing):  python -m ... <URL1, URL2, ...>", file=sys.stderr)
