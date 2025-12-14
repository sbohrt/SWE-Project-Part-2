from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from core.url_ctx import clear as clear_url_ctx
from core.url_ctx import set_context
from metrics import bus_factor as bf

# -------- helpers to build fake commit streams --------


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_commits(spec: dict[str, tuple[int, int]]):
    """
    spec = { "alice": (count, days_ago_of_latest), ... }
    Creates a list of commit dicts the metric expects: {"login","email","date"}.
    For simplicity all commits of an author share the same 'days ago'.
    """
    now = datetime.now(timezone.utc)
    commits = []
    for login, (n, days_ago) in spec.items():
        dt = now - timedelta(days=days_ago)
        for _ in range(n):
            commits.append({"login": login, "email": None, "date": _iso(dt)})
    return commits


def _expected_from_commits(commits, archived=False, lifetime=100):
    days_since, stats = bf._analyze_commits(commits)
    return bf._score_from_stats(stats, days_since, archived, lifetime)


# -------- tests --------


def test_uses_code_url_from_context(monkeypatch) -> None:
    """
    If code_url is provided via url_ctx for the model_url, we should use it
    (no HF lookup) and score based on those commits.
    """
    clear_url_ctx()
    model_url = "https://huggingface.co/some/model"
    set_context(model_url, "https://github.com/foo/bar", None)

    # Force GH parsing/branch/metadata
    monkeypatch.setattr(bf, "_parse_gh", lambda u: ("foo", "bar"))
    monkeypatch.setattr(bf, "_get_default_branch", lambda *_: "main")
    # minimal repo metadata: not archived, some lifetime signal
    with patch("metrics.bus_factor.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "archived": False,
            "network_count": 123,
        }

        # 2 unique contributors; latest commit 10 days ago
        fake_commits = _make_commits({"u1": (5, 10), "u2": (3, 10)})
        monkeypatch.setattr(bf, "_list_commits", lambda *args, **kw: fake_commits)

        out = bf.compute(model_url)

    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0
    expected = _expected_from_commits(fake_commits, archived=False, lifetime=123)
    assert out["value"] == pytest.approx(expected, rel=1e-6)


@patch.object(bf, "_get_default_branch", return_value="main")
def test_fallback_via_card_metadata(mock_branch, monkeypatch) -> None:
    """
    No context set → fall back to HF model card metadata (code_repository).
    """
    clear_url_ctx()

    # HF model_info returns a direct GitHub repo link
    with patch.object(bf, "model_info") as mock_model_info, patch(
        "metrics.bus_factor.requests.get"
    ) as mock_get:
        mock_model_info.return_value = SimpleNamespace(
            cardData={"code_repository": "https://github.com/org/repo"},
            tags=[],
        )
        monkeypatch.setattr(bf, "_parse_gh", lambda u: ("org", "repo"))

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "archived": False,
            "network_count": 999,
        }

        # 3 contributors, latest is "now"
        fake_commits = _make_commits({"a": (4, 0), "b": (3, 0), "c": (2, 0)})
        monkeypatch.setattr(bf, "_list_commits", lambda *args, **kw: fake_commits)

        out = bf.compute("https://huggingface.co/acme/model-x")

    assert isinstance(out["latency_ms"], int)
    expected = _expected_from_commits(fake_commits, archived=False, lifetime=999)
    assert out["value"] == pytest.approx(expected, rel=1e-6)


@patch.object(bf, "_get_default_branch", return_value="main")
def test_fallback_via_card_markdown(mock_branch, monkeypatch) -> None:
    """
    If metadata has no GitHub link, scrape the model card markdown for the first GH URL.
    """
    clear_url_ctx()

    with patch.object(bf, "model_info") as mock_model_info, patch.object(
        bf.ModelCard, "load"
    ) as mock_load, patch("metrics.bus_factor.requests.get") as mock_get:
        mock_model_info.return_value = SimpleNamespace(cardData={}, tags=[])
        mock_load.return_value = SimpleNamespace(
            content="some text links https://github.com/acme/coolrepo and more"
        )
        monkeypatch.setattr(bf, "_parse_gh", lambda u: ("acme", "coolrepo"))

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "archived": False,
            "network_count": 10,
        }

        # one contributor; latest 50 days ago
        fake_commits = _make_commits({"dev": (7, 50)})
        monkeypatch.setattr(bf, "_list_commits", lambda *args, **kw: fake_commits)

        out = bf.compute("https://huggingface.co/acme/model-y")

    assert isinstance(out["latency_ms"], int)
    expected = _expected_from_commits(fake_commits, archived=False, lifetime=10)
    assert out["value"] == pytest.approx(expected, rel=1e-6)


def test_no_github_found_returns_default(monkeypatch) -> None:
    """
    If no GH link in context, metadata, or markdown, return DEFAULT.
    """
    clear_url_ctx()
    with patch.object(bf, "model_info") as mock_model_info, patch.object(
        bf.ModelCard, "load"
    ) as mock_load:
        mock_model_info.return_value = SimpleNamespace(cardData={}, tags=[])
        mock_load.return_value = SimpleNamespace(content="no GH link here")
        # Ensure parser finds nothing
        monkeypatch.setattr(bf, "_parse_gh", lambda u: None)

        out = bf.compute("https://huggingface.co/xxx/model-z")

    assert isinstance(out["latency_ms"], int)
    assert out["value"] == pytest.approx(bf.DEFAULT)


def test_handles_network_errors_gracefully() -> None:
    """
    Any unexpected exception should produce DEFAULT, not crash.
    """
    clear_url_ctx()
    with patch.object(bf, "model_info", side_effect=RuntimeError("boom")):
        out = bf.compute("https://huggingface.co/boom/model")
    assert out["value"] == pytest.approx(bf.DEFAULT)
    assert isinstance(out["latency_ms"], int)
