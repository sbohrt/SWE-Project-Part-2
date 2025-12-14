from __future__ import annotations

import logging
import os
import re
from typing import Dict, Optional, Set

import requests


def gh_headers() -> Dict[str, str]:
    hdrs: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "swe-project/1.0",
    }
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if tok and tok.lower() not in {"invalid", "none", "placeholder"}:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def gh_get(
    url: str, params: Optional[Dict[str, str]] = None, timeout: int = 10
) -> Optional[requests.Response]:
    params = params or {}
    hdrs = gh_headers()
    try:
        res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
    except requests.RequestException as e:
        logging.warning("[gh_utils] network error %s: %s", url, e)
        return None

    tl = (res.text or "").lower()
    if res.status_code in (401, 403) and (
        "bad credentials" in tl or "requires authentication" in tl
    ):
        hdrs = {k: v for k, v in hdrs.items() if k.lower() != "authorization"}
        try:
            res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
        except requests.RequestException as e:
            logging.warning("[gh_utils] retry without auth failed %s: %s", url, e)
            return None

    if res.status_code != 200:
        logging.warning("[gh_utils] GET %s -> %s", url, res.status_code)
        return None
    return res


_RE_GH = re.compile(r"github\.com/([^/]+)/([^/]+)")


def get_github_repo_files(repo_url: str) -> Set[str]:
    m = _RE_GH.search(repo_url.replace(".git", ""))
    if not m:
        return set()
    owner, repo = m.groups()

    info = gh_get(f"https://api.github.com/repos/{owner}/{repo}")
    if not info:
        return set()
    default_branch = (info.json() or {}).get("default_branch") or "main"

    tree = gh_get(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    )
    if not tree:
        return set()
    j = tree.json() or {}
    if "tree" not in j:
        return set()
    return {n.get("path", "") for n in j.get("tree", []) if n.get("type") == "blob"}
