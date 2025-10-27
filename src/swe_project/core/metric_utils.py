from __future__ import annotations

from typing import Any, Optional, Set, Tuple

from swe_project.core.gh_utils import get_github_repo_files
from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id


def parse_urls(input_line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    urls = [u.strip() for u in input_line.split(",") if u.strip()]
    code_url = next((u for u in urls if "github.com" in u), None)
    dataset_url = next((u for u in urls if "huggingface.co/datasets/" in u), None)
    model_url = next(
        (u for u in urls if "huggingface.co" in u and "/datasets/" not in u), None
    )
    return code_url, dataset_url, model_url


def filenames_for_model_or_repo(url: str, *, existing_info=None) -> set[str]:
    """
    Return file names for either a GitHub repo or an HF model repo.
    If `existing_info` is provided, it will ALWAYS be used (no network calls).
    """
    from swe_project.core.model_url import to_repo_id
    from swe_project.core.hf_client import model_info as _hf_model_info
    from swe_project.core.gh_utils import get_github_repo_files as _gh_files

    url = (url or "").strip()
    if "github.com" in url:
        return _gh_files(url)

    # Hugging Face: use the info we were given, otherwise fetch.
    rid, _ = to_repo_id(url)
    info = existing_info if existing_info is not None else _hf_model_info(rid)
    siblings = getattr(info, "siblings", []) or []
    out = set()
    for sibl in siblings:
        fn = getattr(sibl, "rfilename", None)
        if isinstance(fn, str) and fn:
            out.add(fn)
    return out


