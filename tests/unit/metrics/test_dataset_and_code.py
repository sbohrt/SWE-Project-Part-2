from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch



# Import the metric module with an alias to patch its 'model_info' symbol.
from swe_project.metrics import dataset_and_code as dca


def _create_mock_info(
    has_dataset: bool = False,
    has_code: bool = False,
    has_space: bool = False,
) -> SimpleNamespace:
    """Creates a mock model_info object with specified availability signals."""
    return SimpleNamespace(
        cardData={"datasets": ["some-dataset"]} if has_dataset else {},
        siblings=[SimpleNamespace(rfilename="model.py")] if has_code else [],
        spaces=["user/space"] if has_space else [],
    )


@patch.object(dca, "model_info", autospec=True)
def test_availability_full_score(mock_model_info) -> None:
    """A model with datasets, code, and a space should receive a full score."""
    mock_model_info.return_value = _create_mock_info(
        has_dataset=True, has_code=True, has_space=True
    )

    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 1.0
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0


@patch.object(dca, "model_info", autospec=True)
def test_availability_partial_scores(mock_model_info) -> None:
    """Test that each signal contributes the correct partial score."""
    # Test dataset only
    mock_model_info.return_value = _create_mock_info(has_dataset=True)
    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.5

    # Test code only
    mock_model_info.return_value = _create_mock_info(has_code=True)
    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.3

    # Test space only
    mock_model_info.return_value = _create_mock_info(has_space=True)
    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.2


@patch.object(dca, "model_info", autospec=True)
def test_availability_zero_score(mock_model_info) -> None:
    """A model with no availability signals should receive a score of 0.0."""
    mock_model_info.return_value = _create_mock_info()  # All flags are False

    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)


@patch.object(dca, "model_info", side_effect=Exception("API failed"), autospec=True)
def test_availability_handles_exception(mock_model_info) -> None:
    """Any failure during API call should result in a score of 0.0."""
    out = dca.compute("https://huggingface.co/org/model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)
