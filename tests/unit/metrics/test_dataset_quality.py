from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from swe_project.metrics import dataset_quality as dq


def _mock_dataset_info(
    has_card: bool = False,
    has_viewer: bool = False,
    has_configs: bool = False,
    downloads: int = 0,
    gated: bool = False,
) -> SimpleNamespace:
    """Creates a mock dataset_info object with specified quality signals."""
    return SimpleNamespace(
        cardData={"some_key": "some_value"} if has_card else None,
        viewer=has_viewer,
        configs=["default"] if has_configs else [],
        downloads=downloads,
        gated=gated,
    )


@patch.object(dq, "dataset_info")
def test_quality_high_score_single_dataset(mock_dataset_info) -> None:
    """Tests a single high-quality dataset URL."""
    mock_dataset_info.return_value = _mock_dataset_info(
        has_card=True, has_viewer=True, has_configs=True, downloads=5000
    )

    out = dq.compute("https://huggingface.co/datasets/user/high-quality-dataset")
    # Score should be 0.5(card) + 0.25(downloads) + 0.2(configs) + 0.05(viewer) = 1.0
    assert out["value"] == 1.0
    assert isinstance(out["latency_ms"], int)


@patch.object(dq, "dataset_info")
def test_quality_average_score_multiple_datasets(mock_dataset_info) -> None:
    """Tests averaging scores from multiple dataset URLs."""
    # First dataset is high quality (score=1.0), second is low quality (score=0.0)
    high_quality = _mock_dataset_info(
        has_card=True, has_viewer=True, has_configs=True, downloads=5000
    )
    low_quality = _mock_dataset_info()
    mock_dataset_info.side_effect = [high_quality, low_quality]

    out = dq.compute(
        "https://huggingface.co/datasets/d1, https://huggingface.co/datasets/d2"
    )
    # Average of 1.0 and 0.0 is 0.5
    assert out["value"] == 0.5
    assert mock_dataset_info.call_count == 2


@patch.object(dq, "dataset_info")
def test_gated_dataset_scores_zero(mock_dataset_info) -> None:
    """Tests that a gated dataset receives a score of 0."""
    mock_dataset_info.return_value = _mock_dataset_info(
        has_card=True, downloads=5000, gated=True
    )
    out = dq.compute("https://huggingface.co/datasets/gated-dataset")
    assert out["value"] == 0.0


@patch.object(dq, "dataset_info")
def test_no_dataset_urls(mock_dataset_info) -> None:
    """Tests input with no valid Hugging Face dataset URLs."""
    out = dq.compute("https://some-other-website.com, http://another-url.net")
    assert out["value"] == 0.0
    mock_dataset_info.assert_not_called()


def test_empty_input_line() -> None:
    """Tests that an empty input string results in a score of 0."""
    out = dq.compute("")
    assert out["value"] == 0.0


@patch.object(dq, "dataset_info")
def test_quality_dataset_info_fails(mock_dataset_info) -> None:
    """Tests when a dataset lookup fails; should score as 0 for that dataset."""
    # First call succeeds (score=0.5), second one fails (score=0.0).
    good_dataset = _mock_dataset_info(has_card=True)
    mock_dataset_info.side_effect = [good_dataset, Exception("API Error")]

    out = dq.compute(
        "https://huggingface.co/datasets/good-dataset, https://huggingface.co/datasets/bad-dataset"
    )
    # Average of 0.5 and 0.0 is 0.25
    assert out["value"] == 0.25
