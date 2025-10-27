# src/swe_project/core/metric_utils.py
from __future__ import annotations
from typing import Any, Optional, Tuple, Set

from swe_project.core.model_url import to_repo_id
from swe_project.core.hf_client import model_info
from swe_project.core.gh_utils import get_github_repo_files

def parse_urls(input_line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    urls = [u.strip() for u in input_line.split(",") if u.strip()]
    code_url = next((u for u in urls if "github.com" in u), None)
    dataset_url = next((u for u in urls if "huggingface.co/datasets/" in u), None)
    model_url = next((u for u in urls if "huggingface.co" in u and "/datasets/" not in u), None)
    return code_url, dataset_url, model_url

def filenames_for_model_or_repo(model_or_repo_url: str, existing_info: Any | None = None) -> Set[str]:
    if "github.com" in model_or_repo_url:
        return get_github_repo_files(model_or_repo_url)
    rid, _ = to_repo_id(model_or_repo_url)
    info = existing_info if existing_info and getattr(existing_info, "id", None) == rid else model_info(rid)
    siblings = getattr(info, "siblings", []) or []
    return {getattr(s, "rfilename", "") for s in siblings if getattr(s, "rfilename", "")}
