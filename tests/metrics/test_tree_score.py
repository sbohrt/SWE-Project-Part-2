"""
Tests for the tree_score metric.

The tree_score metric computes the average net_score of all parent models
identified in the model's lineage graph (via config.json).

Returns 0.0 if the model has no parents.
"""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_download_snapshot():
    """Mock download_snapshot to return a temp directory with test files."""
    with patch('metrics.tree_score.download_snapshot') as mock:
        yield mock


@pytest.fixture
def mock_model_info():
    """Mock model_info to return test model metadata."""
    with patch('metrics.tree_score.model_info') as mock:
        yield mock


def test_tree_score_no_parents(mock_download_snapshot):
    """Test model with no parent models."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "architectures": ["BertForMaskedLM"],
                "model_type": "bert"
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == 0.0
        assert "latency_ms" in result


def test_tree_score_single_parent(mock_download_snapshot):
    """Test model with a single parent."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "bert-base-uncased",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Should return score for bert-base-uncased (0.85)
        assert result["value"] == 0.85
        assert "latency_ms" in result


def test_tree_score_multiple_parents(mock_download_snapshot):
    """Test model with multiple parent models."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "bert-base-uncased",
                "base_model": "gpt2",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Should average bert-base-uncased (0.85) and gpt2 (0.90)
        expected = (0.85 + 0.90) / 2
        assert result["value"] == expected


def test_tree_score_unknown_parent(mock_download_snapshot):
    """Test model with unknown parent model."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "unknown-model-xyz",
                "architectures": ["CustomModel"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Unknown parent gets default score of 0.7
        assert result["value"] == 0.7


def test_tree_score_huggingface_path(mock_download_snapshot):
    """Test model with HuggingFace-style parent path."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "google-bert/bert-base-uncased",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Should recognize bert-base-uncased despite org prefix
        assert result["value"] == 0.85


def test_tree_score_local_path_ignored(mock_download_snapshot):
    """Test that local paths are ignored."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "./local/model/path",
                "base_model": "/absolute/local/path",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Local paths should be ignored, no parents found
        assert result["value"] == 0.0


def test_tree_score_duplicate_parents(mock_download_snapshot):
    """Test that duplicate parents are only counted once."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "bert-base-uncased",
                "base_model": "bert-base-uncased",  # Duplicate
                "parent_model": "gpt2",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Should only count unique parents: bert-base-uncased (0.85) and gpt2 (0.90)
        expected = (0.85 + 0.90) / 2
        assert result["value"] == expected


def test_tree_score_roberta_parent(mock_download_snapshot):
    """Test model with roberta-base parent."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "base_model": "roberta-base",
                "architectures": ["RobertaForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # roberta-base has score 0.86
        assert result["value"] == 0.86


def test_tree_score_t5_parent(mock_download_snapshot):
    """Test model with t5-base parent."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "model_name_or_path": "t5-base",
                "architectures": ["T5ForConditionalGeneration"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # t5-base has score 0.84
        assert result["value"] == 0.84


def test_tree_score_gpt2_variants(mock_download_snapshot):
    """Test different GPT2 model sizes."""
    from metrics.tree_score import compute

    # Test gpt2-medium
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "gpt2-medium",
                "architectures": ["GPT2LMHeadModel"]
            }, f)

        mock_download_snapshot.return_value = tmpdir
        result = compute("https://huggingface.co/my-model")
        # Matches 'gpt2' substring first, returns 0.90
        assert result["value"] == 0.90

    # Test gpt2-large
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "gpt2-large",
                "architectures": ["GPT2LMHeadModel"]
            }, f)

        mock_download_snapshot.return_value = tmpdir
        result = compute("https://huggingface.co/my-model")
        # Matches 'gpt2' substring first, returns 0.90
        assert result["value"] == 0.90


def test_tree_score_no_config_file(mock_download_snapshot):
    """Test model with no config.json file."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        # No config.json created
        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # No config = no parents = 0.0
        assert result["value"] == 0.0


def test_tree_score_invalid_json(mock_download_snapshot):
    """Test handling of invalid JSON in config file."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            f.write("{ invalid json }")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Invalid JSON should return 0.0
        assert result["value"] == 0.0


def test_tree_score_empty_parent_field(mock_download_snapshot):
    """Test handling of empty parent field values."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "",  # Empty string
                "base_model": None,  # None value
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Empty/None values should be ignored, no parents
        assert result["value"] == 0.0


def test_tree_score_all_parent_fields(mock_download_snapshot):
    """Test that all parent field types are checked."""
    from metrics.tree_score import compute

    # Test base_model_name_or_path
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "base_model_name_or_path": "distilbert-base-uncased",
                "architectures": ["DistilBertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir
        result = compute("https://huggingface.co/my-model")

        # Matches 'bert-base-uncased' substring first, returns 0.85
        assert result["value"] == 0.85


def test_tree_score_mixed_known_unknown(mock_download_snapshot):
    """Test model with mix of known and unknown parents."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "bert-base-uncased",  # Known: 0.85
                "base_model": "unknown-custom-model",  # Unknown: 0.7
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Average of 0.85 and 0.7
        expected = (0.85 + 0.7) / 2
        assert result["value"] == expected


def test_tree_score_download_error(mock_download_snapshot):
    """Test error handling when download fails."""
    from metrics.tree_score import compute

    mock_download_snapshot.side_effect = Exception("Download failed")

    result = compute("https://huggingface.co/my-model")

    # Should return 0.0 on error
    assert result["value"] == 0.0
    assert "latency_ms" in result


def test_tree_score_latency_measurement(mock_download_snapshot):
    """Test that latency is properly measured."""
    from metrics.tree_score import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        with open(config_path, "w") as f:
            json.dump({
                "_name_or_path": "bert-base-uncased",
                "architectures": ["BertForMaskedLM"]
            }, f)

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0
