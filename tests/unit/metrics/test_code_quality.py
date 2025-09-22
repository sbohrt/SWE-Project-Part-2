from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from swe_project.metrics import code_quality as cq


def _mock_model_info(filenames: list[str] | None = None) -> SimpleNamespace:
    # Creates a mock model_info object with a specified list of repo files.
    if filenames is None:
        filenames = []
    siblings = [SimpleNamespace(rfilename=f) for f in filenames]
    return SimpleNamespace(siblings=siblings)


@patch.object(cq, "model_info")
def test_quality_full_score(mock_model_info) -> None:
    # Tests a repo with all quality signals present.
    mock_model_info.return_value = _mock_model_info(
        ["requirements.txt", "model.py", "config.json"]
    )
    out = cq.compute("some/model")
    assert out["value"] == 1.0
    assert isinstance(out["latency_ms"], int)


@patch.object(cq, "model_info")
def test_quality_partial_scores(mock_model_info) -> None:
    # Tests that each signal contributes the correct partial score.
    mock_model_info.return_value = _mock_model_info(["requirements.txt"])
    out = cq.compute("some/model")
    assert out["value"] == 0.4

    mock_model_info.return_value = _mock_model_info(["train.py"])
    out = cq.compute("some/model")
    assert out["value"] == 0.3

    mock_model_info.return_value = _mock_model_info(["config.json"])
    out = cq.compute("some/albert-base-v2")
    assert out["value"] == 0.3


@patch.object(cq, "model_info")
def test_quality_zero_score(mock_model_info) -> None:
    # Tests a repo with no quality signals.
    mock_model_info.return_value = _mock_model_info(["README.md", "model.safetensors"])
    out = cq.compute("some/model")
    assert out["value"] == 0.0


@patch.object(cq, "model_info", side_effect=Exception("API is down"))
def test_quality_api_fails(mock_model_info) -> None:
    # Tests that a failure in the API call results in a score of 0.0.
    out = cq.compute("some/model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)
