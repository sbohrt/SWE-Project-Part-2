from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from swe_project.core.url_ctx import clear as clear_url_ctx
from swe_project.core.url_ctx import set_context
from swe_project.metrics import bus_factor as bf

# ---------- helpers ----------


def _expected_score(n_active: int, days_since_latest: int) -> float:
    """Recompute the metric's intended combination to assert against."""
    c = 0.0 if n_active <= 0 else min(1.0, math.log1p(n_active) / math.log(6))
    f = 1.0 - (max(0, min(bf.LOOKBACK_DAYS, days_since_latest)) / bf.LOOKBACK_DAYS)
    return max(0.0, min(1.0, 0.7 * c + 0.3 * f))


def _fake_parse_ok(url: str):
    return ("org", "repo")


# ---------- tests ----------


def test_uses_code_url_from_context(monkeypatch) -> None:
    """
    If code_url is provided via url_ctx for the model_url, bus_factor should use it
    (no HF lookup), and combine contributors/freshness from the GH stubs.
    """
    clear_url_ctx()
    model_url = "https://huggingface.co/some/model"
    set_context(model_url, "https://github.com/foo/bar", None)

    # Patch internals used after we have a GitHub URL
    monkeypatch.setattr(bf, "_parse_gh", lambda u: ("foo", "bar"))
    monkeypatch.setattr(bf, "_get_default_branch", lambda *_: "main")

    # Pretend 2 unique active contributors, latest commit 10 days ago
    newest = datetime.now(timezone.utc) - timedelta(days=10)
    monkeypatch.setattr(bf, "_list_active_since", lambda *_: ({"u1", "u2"}, newest))

    out = bf.compute(model_url)
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0

    expected = _expected_score(n_active=2, days_since_latest=10)
    assert math.isclose(out["value"], expected, rel_tol=1e-6)


@patch.object(bf, "_get_default_branch", return_value="main")
@patch.object(
    bf, "_list_active_since", return_value=({"a", "b", "c"}, datetime.now(timezone.utc))
)
def test_fallback_via_card_metadata(mock_list, mock_branch, monkeypatch) -> None:
    """
    If no code_url is set, we fall back to HF model card metadata (code_repository/repository).
    """
    # No context set: force fallback path
    clear_url_ctx()

    # HF model_info should return a .cardData with code_repository
    with patch.object(bf, "model_info") as mock_model_info:
        mock_model_info.return_value = SimpleNamespace(
            cardData={"code_repository": "https://github.com/org/repo"}, tags=[]
        )
        # parse should accept that repo
        monkeypatch.setattr(bf, "_parse_gh", _fake_parse_ok)

        out = bf.compute("https://huggingface.co/acme/model-x")
        assert isinstance(out["latency_ms"], int)

        # 3 contributors, latest is "now"
        expected = _expected_score(n_active=3, days_since_latest=0)
        assert math.isclose(out["value"], expected, rel_tol=1e-6)


@patch.object(bf, "_get_default_branch", return_value="main")
@patch.object(
    bf,
    "_list_active_since",
    return_value=({"dev"}, datetime.now(timezone.utc) - timedelta(days=50)),
)
def test_fallback_via_card_markdown(mock_list, mock_branch, monkeypatch) -> None:
    """
    If metadata has no GitHub link, we scrape the model card markdown for the first GitHub URL.
    """
    clear_url_ctx()

    # model_info has no useful repo link; no tags either
    with patch.object(bf, "model_info") as mock_model_info, patch.object(
        bf.ModelCard, "load"
    ) as mock_load:
        mock_model_info.return_value = SimpleNamespace(cardData={}, tags=[])
        # Simulate card markdown containing a GitHub URL
        mock_load.return_value = SimpleNamespace(
            content="some text links https://github.com/acme/coolrepo and more"
        )
        monkeypatch.setattr(bf, "_parse_gh", lambda u: ("acme", "coolrepo"))

        out = bf.compute("https://huggingface.co/acme/model-y")
        assert isinstance(out["latency_ms"], int)

        expected = _expected_score(n_active=1, days_since_latest=50)
        assert math.isclose(out["value"], expected, rel_tol=1e-6)


def test_no_github_found_returns_default(monkeypatch) -> None:
    """
    If code_url is absent and we can't find any GH link in metadata or markdown, return DEFAULT.
    """
    clear_url_ctx()

    with patch.object(bf, "model_info") as mock_model_info, patch.object(
        bf.ModelCard, "load"
    ) as mock_load:
        mock_model_info.return_value = SimpleNamespace(cardData={}, tags=[])
        mock_load.return_value = SimpleNamespace(content="no GH link here")
        # Ensure parser won’t find anything
        monkeypatch.setattr(bf, "_parse_gh", lambda u: None)

        out = bf.compute("https://huggingface.co/xxx/model-z")
        assert isinstance(out["latency_ms"], int)
        assert out["value"] == pytest.approx(bf.DEFAULT)


def test_handles_network_errors_gracefully(monkeypatch) -> None:
    """
    Any unexpected exception should produce DEFAULT, not crash.
    """
    clear_url_ctx()
    # Force an exception inside compute by making model_info raise
    with patch.object(bf, "model_info", side_effect=RuntimeError("boom")):
        out = bf.compute("https://huggingface.co/boom/model")
        assert out["value"] == pytest.approx(bf.DEFAULT)
        assert isinstance(out["latency_ms"], int)
