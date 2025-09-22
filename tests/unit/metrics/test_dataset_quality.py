from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from swe_project.metrics import dataset_quality as dq


def _mock_model_info(dataset_ids: list[str] | None = None) -> SimpleNamespace:
    # Creates a mock model_info object linking to specified dataset IDs.
    if dataset_ids is None:
        dataset_ids = []
    return SimpleNamespace(cardData={"datasets": dataset_ids})


def _mock_dataset_info(
    has_card: bool = False,
    has_viewer: bool = False,
    has_configs: bool = False,
    downloads: int = 0,
) -> SimpleNamespace:
    # Creates a mock dataset_info object with specified quality signals.
    return SimpleNamespace(
        cardData={"some_key": "some_value"} if has_card else None,
        viewer=has_viewer,
        configs=["default"] if has_configs else [],
        downloads=downloads,
    )


@patch.object(dq, "dataset_info")
@patch.object(dq, "model_info")
def test_quality_high_score_single_dataset(mock_model_info, mock_dataset_info) -> None:
    # Tests a model linking to one high-quality dataset.
    mock_model_info.return_value = _mock_model_info(["user/high-quality-dataset"])
    mock_dataset_info.return_value = _mock_dataset_info(
        has_card=True, has_viewer=True, has_configs=True, downloads=5000
    )

    out = dq.compute("some/model")
    # Score should be 0.5(card) + 0.2(viewer) + 0.1(configs) + 0.2(downloads) = 1.0
    assert out["value"] == 1.0
    assert isinstance(out["latency_ms"], int)


@patch.object(dq, "dataset_info")
@patch.object(dq, "model_info")
def test_quality_average_score_multiple_datasets(
    mock_model_info, mock_dataset_info
) -> None:
    mock_model_info.return_value = _mock_model_info(["d1", "d2"])

    # First dataset is high quality (score=1.0), second is low quality (score=0.0)
    high_quality = _mock_dataset_info(
        has_card=True, has_viewer=True, has_configs=True, downloads=5000
    )
    low_quality = _mock_dataset_info()
    mock_dataset_info.side_effect = [high_quality, low_quality]

    out = dq.compute("some/model")
    # Average of 1.0 and 0.0 is 0.5
    assert out["value"] == 0.5
    assert mock_dataset_info.call_count == 2


@patch.object(dq, "dataset_info")
@patch.object(dq, "model_info")
def test_quality_no_datasets_linked(mock_model_info, mock_dataset_info) -> None:
    # Tests a model that links to zero datasets.
    mock_model_info.return_value = _mock_model_info([])  # Empty list

    out = dq.compute("some/model")
    assert out["value"] == 0.0
    mock_dataset_info.assert_not_called()


@patch.object(dq, "model_info", side_effect=Exception("API Error"))
def test_quality_model_info_fails(mock_model_info) -> None:
    """Tests when the initial model_info lookup fails."""
    out = dq.compute("some/model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)


@patch.object(dq, "dataset_info", side_effect=Exception("API Error"))
@patch.object(dq, "model_info")
def test_quality_dataset_info_fails(mock_model_info, mock_dataset_info) -> None:
    """Tests when a dataset lookup fails; should score as 0 for that dataset."""
    mock_model_info.return_value = _mock_model_info(["good-dataset", "bad-dataset"])

    # First call succeeds (score=0.5), second one fails (score=0.0).
    good_dataset = _mock_dataset_info(has_card=True)
    mock_dataset_info.side_effect = [good_dataset, Exception("API Error")]

    out = dq.compute("some/model")
    # Average of 0.5 and 0.0 is 0.25
    assert out["value"] == 0.25
