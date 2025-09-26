# stdlib
from __future__ import annotations

import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from re import Match, Pattern
from typing import Any, Dict, Optional, Set, Tuple

# third-party
import requests
from huggingface_hub import ModelCard

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.core.url_ctx import get_code_url

# local
from swe_project.metrics.base import MetricResult, register

NAME = "bus_factor"
FIELD = "bus_factor"
LOOKBACK_DAYS = 365
DEFAULT = 0.3

_GH_RE: Pattern[str] = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?]+)"
)
_GH_LINK_RE: Pattern[str] = re.compile(
    r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
)


def _gh_headers() -> Dict[str, str]:
    hdrs: Dict[str, str] = {"Accept": "application/vnd.github+json"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def _parse_gh(url: str) -> Optional[Tuple[str, str]]:
    m = _GH_RE.search(url or "")
    return (m.group("owner"), m.group("repo")) if m else None


def _get_default_branch(o: str, r: str) -> Optional[str]:
    try:
        res = requests.get(
            f"https://api.github.com/repos/{o}/{r}", headers=_gh_headers(), timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                val = data.get("default_branch")
                return val if isinstance(val, str) else None
    except requests.RequestException:
        pass
    return None


def _list_active_since(
    o: str, r: str, since_iso: str, branch: Optional[str]
) -> Tuple[Set[str], Optional[datetime]]:
    params: Dict[str, str] = {"since": since_iso, "per_page": "100"}
    if branch:
        params["sha"] = branch
    active: Set[str] = set()
    newest: Optional[datetime] = None
    url = f"https://api.github.com/repos/{o}/{r}/commits"

    for _ in range(3):
        try:
            res = requests.get(url, headers=_gh_headers(), params=params, timeout=10)
        except requests.RequestException:
            break
        if res.status_code != 200:
            break
        items = res.json()
        if not isinstance(items, list) or not items:
            break

        for c in items:
            login = (c.get("author") or {}).get("login")
            if login:
                active.add(login)
            else:
                email = ((c.get("commit") or {}).get("author") or {}).get("email")
                if email:
                    active.add(f"email:{email}")

            d = ((c.get("commit") or {}).get("author") or {}).get("date")
            if d:
                try:
                    dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                    if (newest is None) or (dt > newest):
                        newest = dt
                except Exception:
                    pass

        link = res.headers.get("Link", "")
        nxt = next(
            (
                p[p.find("<") + 1 : p.find(">")]
                for p in link.split(",")
                if 'rel="next"' in p
            ),
            None,
        )
        if not nxt:
            break
        url, params = nxt, {}

    return active, newest


def _contributors_score(n: int) -> float:
    return 0.0 if n <= 0 else min(1.0, math.log1p(n) / math.log(6))


def _freshness_score(latest: Optional[datetime]) -> float:
    if not latest:
        return 0.0
    days = max(0, min(LOOKBACK_DAYS, (datetime.now(timezone.utc) - latest).days))
    return 1.0 - (days / LOOKBACK_DAYS)


def _combine(c: float, f: float) -> float:
    return max(0.0, min(1.0, 0.7 * c + 0.3 * f))


def _find_github_url_from_card_md(repo_id: str) -> Optional[str]:
    """Read the HF model card markdown and extract the first GitHub link."""
    try:
        # Force 'Any' from huggingface-hub to become a concrete str
        md: str = str(ModelCard.load(repo_id).content)
    except Exception:
        return None

    m: Optional[Match[str]] = _GH_LINK_RE.search(md)
    if m is None:
        return None

    g0: str = m.group(0)  # explicit local variable typed as str
    return g0


def _find_github_url(info: Any, repo_id: str) -> Optional[str]:
    """Locate a GitHub repo link from HF model card metadata/tags/markdown."""
    card = getattr(info, "cardData", None) or {}
    tags = getattr(info, "tags", []) or []

    gh_url = card.get("code_repository") or card.get("repository")
    if isinstance(gh_url, str) and "github.com" in gh_url:
        return gh_url

    for t in tags:
        if isinstance(t, str) and "github.com" in t:
            return t

    return _find_github_url_from_card_md(repo_id)


def compute(model_url: str) -> MetricResult:
    t0 = time.perf_counter()
    try:
        # 1) Prefer code URL from input context
        code_url = get_code_url(model_url)
        parsed = _parse_gh(code_url) if code_url else None
        if parsed:
            o, r = parsed
            branch = _get_default_branch(o, r)
            since = (
                datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
            ).isoformat()
            active, newest = _list_active_since(o, r, since, branch)
            score = _combine(_contributors_score(len(active)), _freshness_score(newest))
            return {
                "value": float(score),
                "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
            }

        # 2) Fallback: find GitHub from HF model card
        repo_id, _ = to_repo_id(model_url)
        info = model_info(repo_id)
        gh = _find_github_url(info, repo_id)
        parsed = _parse_gh(gh) if gh else None
        if parsed:
            o, r = parsed
            branch = _get_default_branch(o, r)
            since = (
                datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
            ).isoformat()
            active, newest = _list_active_since(o, r, since, branch)
            score = _combine(_contributors_score(len(active)), _freshness_score(newest))
            return {
                "value": float(score),
                "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
            }

        # 3) Nothing found → conservative default
        return {
            "value": DEFAULT,
            "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
        }
    except Exception:
        return {
            "value": DEFAULT,
            "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
        }


register(NAME, FIELD, compute)
