# stdlib
from __future__ import annotations

import logging
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
    hdrs: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "swe-project-bus-factor/1.0",
    }
    tok = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if tok and tok.lower() not in {"invalid", "none", "placeholder"}:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def _gh_get(url: str, params: Optional[Dict[str, str]] = None, timeout: int = 10):
    """Fail-soft GET: retry once without Authorization on 401/Bad credentials.
    Returns a requests.Response on success, or None on failure.
    """
    params = params or {}
    hdrs = _gh_headers()
    try:
        res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
    except requests.RequestException as e:
        logging.warning("[bus_factor] network error %s: %s", url, e)
        return None

    text_lower = (res.text or "").lower()
    if res.status_code in (401, 403) and (
        "bad credentials" in text_lower or "requires authentication" in text_lower
    ):
        # Retry once without auth header
        hdrs = {k: v for k, v in hdrs.items() if k.lower() != "authorization"}
        try:
            res = requests.get(url, headers=hdrs, params=params, timeout=timeout)
        except requests.RequestException as e:
            logging.warning("[bus_factor] retry without auth failed %s: %s", url, e)
            return None

    if res.status_code != 200:
        logging.warning("[bus_factor] GET %s -> %s", url, res.status_code)
        return None
    return res


def _parse_gh(url: str) -> Optional[Tuple[str, str]]:
    m = _GH_RE.search(url or "")
    return (m.group("owner"), m.group("repo")) if m else None


def _get_default_branch(o: str, r: str) -> Optional[str]:
    res = _gh_get(f"https://api.github.com/repos/{o}/{r}")
    if not res:
        return None
    data = res.json()
    if isinstance(data, dict):
        val = data.get("default_branch")
        return val if isinstance(val, str) else None
    return None


def _list_active_since(
    o: str, r: str, since_iso: str, branch: Optional[str]
) -> Tuple[Set[str], Optional[datetime]]:
    """Backward-compatible helper used by your older tests."""
    commits_opt = _list_commits(o, r, since_iso, branch)
    if commits_opt is None:
        # No data available → return empty set / None; callers usually fail-soft to DEFAULT
        return set(), None

    authors: Set[str] = set()
    newest: Optional[datetime] = None
    for c in commits_opt:
        if _is_bot(c.get("login"), c.get("email")):
            continue
        key = (c.get("login") or f"email:{c.get('email') or 'unknown'}").lower()
        authors.add(key)
        d = c.get("date")
        if d:
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                if (newest is None) or (dt > newest):
                    newest = dt
            except Exception:
                pass
    return authors, newest


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


# --- New helpers for a fairer score ---


def _is_bot(author_login: Optional[str], author_email: Optional[str]) -> bool:
    if not author_login and not author_email:
        return False
    login = (author_login or "").lower()
    email = (author_email or "").lower()
    return (
        login.endswith("[bot]")
        or login.endswith("-bot")
        or login.endswith("_bot")
        or "github-actions" in login
        or "bot@" in email
        or "noreply@" in email
    )


def _list_commits(
    o: str, r: str, since_iso: str, branch: Optional[str]
) -> Optional[list[dict]]:
    """Return commit dicts since 'since_iso', or None if API is unavailable."""
    params: Dict[str, str] = {"since": since_iso, "per_page": "100"}
    if branch:
        params["sha"] = branch
    url = f"https://api.github.com/repos/{o}/{r}/commits"
    commits: list[dict] = []

    for _ in range(8):  # up to ~800 commits via pagination
        res = _gh_get(url, params=params, timeout=10)
        if res is None:
            return None  # ← important: signal 'inconclusive'

        items = res.json()
        if not isinstance(items, list) or not items:
            break

        for c in items:
            login = (c.get("author") or {}).get("login")
            email = ((c.get("commit") or {}).get("author") or {}).get("email")
            date_s = ((c.get("commit") or {}).get("author") or {}).get("date")
            commits.append({"login": login, "email": email, "date": date_s})

        # follow Link: rel="next"
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
    return commits


def _hhi(shares: list[float]) -> float:
    return sum(s * s for s in shares)


def _k_for_coverage(counts: list[int], coverage: float = 0.80) -> int:
    """Smallest k authors covering 'coverage' of commits."""
    if not counts:
        return 0
    total = sum(counts)
    need = coverage * total
    acc, k = 0, 0
    for c in sorted(counts, reverse=True):
        acc += c
        k += 1
        if acc >= need:
            break
    return k


def _freshness(days_since_latest: int, tau: float = 180.0) -> float:
    # exp decay, 1.0 when fresh, ~0.37 at tau days, ~0.14 at 360d
    return float(math.exp(-max(0, days_since_latest) / tau))


def _log_norm(n: int, base: float) -> float:
    return 0.0 if n <= 0 else min(1.0, math.log1p(n) / math.log(base))


def _analyze_commits(commits: list[dict]) -> tuple[int, dict]:
    """
    Returns (days_since_latest, stats) where stats includes:
      C_recent (unique humans), counts per human, shares, HHI, K_needed
    """
    # filter bots + normalize keys
    humans: Dict[str, int] = {}
    latest: Optional[datetime] = None

    for c in commits:
        login = (c.get("login") or "") or None
        email = (c.get("email") or "") or None
        if _is_bot(login, email):
            continue
        key = (login or f"email:{email or 'unknown'}").lower()
        humans[key] = humans.get(key, 0) + 1

        d = c.get("date")
        if d:
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                latest = dt if (latest is None or dt > latest) else latest
            except Exception:
                pass

    days_since = (datetime.now(timezone.utc) - latest).days if latest else LOOKBACK_DAYS
    counts = list(humans.values())
    total = sum(counts)
    shares = [c / total for c in counts] if total > 0 else []
    hhi = _hhi(shares) if total >= 10 else None  # avoid noisy HHI on tiny samples
    k_needed = _k_for_coverage(counts, 0.80) if total > 0 else 0

    return days_since, {
        "C_recent": len(humans),
        "counts": counts,
        "shares": shares,
        "HHI": hhi,
        "K_needed": k_needed,
        "total_commits": total,
    }


def _count_lifetime_contributors(o: str, r: str, pages: int = 10) -> int:
    url = f"https://api.github.com/repos/{o}/{r}/contributors"
    params = {"per_page": "100", "anon": "1"}
    total = 0
    for _ in range(pages):
        try:
            res = requests.get(url, headers=_gh_headers(), params=params, timeout=10)
        except requests.RequestException:
            break
        if res.status_code != 200:
            break
        items = res.json()
        if not isinstance(items, list) or not items:
            break
        total += len(items)
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
    return total


def _score_from_stats(
    stats: dict,
    days_since: int,
    archived: bool,
    lifetime_commits: int,
    o: Optional[str] = None,
    r: Optional[str] = None,
) -> float:
    # ---- Active-path components (what you already have) ----
    C = _log_norm(stats.get("C_recent", 0), base=10.0)
    F = 0.0 if archived else _freshness(days_since, tau=180.0)
    L = _log_norm(int(lifetime_commits or 0), base=50.0)

    total = int(stats.get("total_commits", 0))
    if total >= 10:
        shares = stats.get("shares", [])
        hhi = sum(s * s for s in shares) if shares else 1.0
        D = max(0.0, min(1.0, 1.0 - hhi))
        k = max(1, int(stats.get("K_needed", 1)))
        K = min(1.0, 5.0 / float(k))
    else:
        D, K = 0.0, 0.0

    # ---- Inactive/archived branch: use lifetime breadth ----
    inactive = archived or stats.get("C_recent", 0) == 0
    if inactive and o and r:
        n_life = _count_lifetime_contributors(o, r)  # unique contributors over history
        # Breadth from lifetime
        C_life = 0.0 if n_life <= 0 else min(1.0, math.log1p(n_life) / math.log(6))
        # Diversity proxy without shares: assume “even-ish” when many people contributed.
        # Rescale best-case HHI (1/n) to 1.0: D_life = (1 - 1/n) / (1 - 1/∞) ≈ 1 - 1/n
        D_life = 0.0 if n_life <= 1 else max(0.0, min(1.0, 1.0 - 1.0 / n_life))
        # Redundancy proxy: more lifetime contributors → more people can cover 80%
        K_life = min(1.0, n_life / 5.0)  # reaches 1.0 by ~5 contributors

        # Use archived weights (drop F, renormalize) with lifetime signals
        w = {"D": 0.40, "K": 0.25, "C": 0.20, "L": 0.05}  # no F here
        s = sum(w.values())
        w = {k: v / s for k, v in w.items()}
        score = w["D"] * D_life + w["K"] * K_life + w["C"] * C_life + w["L"] * L
        return max(0.0, min(1.0, float(score)))

    # ---- Active repo blend (your “fair weights”) ----
    w = {"D": 0.40, "K": 0.25, "C": 0.20, "F": 0.10, "L": 0.05}
    score = w["D"] * D + w["K"] * K + w["C"] * C + w["F"] * F + w["L"] * L
    return max(0.0, min(1.0, float(score)))


def compute(model_url: str) -> MetricResult:
    t0 = time.perf_counter()
    try:
        # 1) Prefer explicit code URL from context
        code_url = get_code_url(model_url)
        parsed = _parse_gh(code_url) if code_url else None

        # 2) If none, try HF card to find repo
        repo_info = None
        lifetime_commits = 0
        archived = False

        if not parsed:
            repo_id, _ = to_repo_id(model_url)
            info = model_info(repo_id)
            gh = _find_github_url(info, repo_id)
            parsed = _parse_gh(gh) if gh else None

        if not parsed:
            # Nothing to analyze → neutral default
            return {
                "value": DEFAULT,
                "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
            }

        o, r = parsed

        # 3) Repo metadata (archived flag, etc.) using safe GET
        res = _gh_get(f"https://api.github.com/repos/{o}/{r}")
        if res and isinstance(res.json(), dict):
            repo_info = res.json()
            archived = bool(repo_info.get("archived", False))
            # GitHub API doesn't expose lifetime commits directly; keep your fallback
            lifetime_commits = int(repo_info.get("network_count", 0))

        # 4) Commits in lookback window (safe default-branch lookup)
        branch = _get_default_branch(o, r)
        since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

        commits = _list_commits(o, r, since, branch)
        if commits is None:
            # API unavailable / invalid token / rate-limited → neutral default (do NOT punish)
            return {
                "value": DEFAULT,
                "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
            }

        # 5) Analyze & score
        days_since, stats = _analyze_commits(commits)
        value = _score_from_stats(
            stats, days_since, archived, lifetime_commits, o=o, r=r
        )

        return {
            "value": float(value),
            "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
        }

    except Exception:
        # Network/token/surprise → neutral default
        return {
            "value": DEFAULT,
            "latency_ms": max(1, int((time.perf_counter() - t0) * 1000)),
        }


register(NAME, FIELD, compute)
