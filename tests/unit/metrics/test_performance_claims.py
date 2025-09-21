from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

# Import the metric module so we can patch its local 'model_info' symbol.
from swe_project.metrics import performance_claims as pc


def _info_with_index(
    likes: int = 250,
    downloads: int = 50_000,
) -> SimpleNamespace:
    # Minimal shape the metric reads: likes, downloads, cardData["model-index"]
    return SimpleNamespace(
        likes=likes,
        downloads=downloads,
        cardData={
            "model-index": [
                {
                    "name": "SomeBench",
                    "results": [
                        {
                            "task": {"name": "text-classification"},
                            "dataset": {"name": "sst2"},
                            "metrics": [{"type": "accuracy", "value": 0.95}],
                        }
                    ],
                }
            ]
        },
    )


def _info_without_index(
    likes: int = 200,
    downloads: int = 20_000,
) -> SimpleNamespace:
    return SimpleNamespace(
        likes=likes,
        downloads=downloads,
        cardData=None,  # no model-index
    )


@patch.object(pc, "model_info", autospec=True)
def test_performance_claims_happy_path(mock_model_info) -> None:
    """When model-index is present, score should be > 0 and latency > 0."""
    mock_model_info.return_value = _info_with_index()

    out = pc.compute("https://huggingface.co/org/model")
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0
    assert 0.1 <= out["value"] <= 1.0  # should award benchmark + nudges


@patch.object(pc, "model_info", autospec=True)
def test_performance_claims_no_model_index_uses_popularity_nudges(
    mock_model_info,
) -> None:
    """Without model-index, metric should fall back to small popularity credit."""
    mock_model_info.return_value = _info_without_index()

    out = pc.compute("https://huggingface.co/org/model")
    # In the provided heuristic: likes>=50 adds 0.05, downloads>=10k adds 0.05 → ~0.10
    assert 0.09 <= out["value"] <= 0.11
    assert isinstance(out["latency_ms"], int)


@patch.object(pc, "model_info", side_effect=Exception("boom"), autospec=True)
def test_performance_claims_handles_exception(mock_model_info) -> None:
    """Any failure should produce value 0.0 but still return a well-formed result."""
    out = pc.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)
