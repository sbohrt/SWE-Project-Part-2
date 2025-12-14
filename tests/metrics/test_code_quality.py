from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from metrics import code_quality as cq


def _mock_model_info(filenames: list[str] | None = None) -> SimpleNamespace:
    """Creates a mock model_info object with a specified list of repo files."""
    if filenames is None:
        filenames = []
    siblings = [SimpleNamespace(rfilename=f) for f in filenames]
    return SimpleNamespace(siblings=siblings)


@patch.object(cq, "model_info")
def test_hf_high_score(mock_model_info: MagicMock) -> None:
    """Tests a Hugging Face repo with Python files and dependencies."""
    files = ["model.py", "utils.py", "requirements.txt", "README.md"]
    mock_model_info.return_value = _mock_model_info(files)
    out = cq.compute("https://huggingface.co/user/hf-model")
    # Score = 0.3 (for deps) + (2 py_files / 4 total_files) * 0.7 = 0.3 + 0.35 = 0.65
    assert abs(out["value"] - 0.65) < 0.001


@patch.object(cq, "model_info")
def test_hf_deps_only(mock_model_info: MagicMock) -> None:
    """Tests a Hugging Face repo with only dependency files."""
    files = ["config.json", "README.md"]
    mock_model_info.return_value = _mock_model_info(files)
    out = cq.compute("https://huggingface.co/user/hf-model")
    # Score = 0.3 (only for deps, no python files)
    assert out["value"] == 0.3


@patch.object(cq, "get_github_repo_files")
def test_github_high_score(mock_get_files: MagicMock) -> None:
    """Tests a GitHub repo with Python files and requirements.txt."""
    files = {"main.py", "utils.py", "requirements.txt", "LICENSE"}
    mock_get_files.return_value = files
    out = cq.compute("https://github.com/user/gh-repo")
    # Score = 0.5 (for reqs) + (2 py_files / 4 total_files) * 0.5 = 0.5 + 0.25 = 0.75
    assert out["value"] == 0.75


@patch.object(cq, "get_github_repo_files")
def test_github_py_files_only(mock_get_files: MagicMock) -> None:
    """Tests a GitHub repo with only Python files."""
    files = {"script.py", "docs.txt"}
    mock_get_files.return_value = files
    out = cq.compute("https://github.com/user/gh-repo")
    # Score = (1 py_file / 2 total_files) * 0.5 = 0.25
    assert out["value"] == 0.25


@patch.object(cq, "get_github_repo_files")
@patch.object(cq, "model_info")
def test_sum_scores_from_multiple_urls(
    mock_model_info: MagicMock, mock_get_files: MagicMock
) -> None:
    """Tests that scores from multiple relevant URLs are summed."""
    # HF score = 0.3 (deps only)
    mock_model_info.return_value = _mock_model_info(["config.json"])
    # GitHub score = 0.5 (reqs only)
    mock_get_files.return_value = {"requirements.txt", "README.md"}
    out = cq.compute("https://huggingface.co/user/model, https://github.com/user/repo")
    # Total score = 0.3 + 0.5 = 0.8
    assert out["value"] == 0.8


@patch.object(cq, "get_github_repo_files")
@patch.object(cq, "model_info")
def test_score_is_capped_at_one(
    mock_model_info: MagicMock, mock_get_files: MagicMock
) -> None:
    """Tests that the final score is capped at 1.0."""
    # HF score = 0.65
    mock_model_info.return_value = _mock_model_info(
        ["model.py", "utils.py", "requirements.txt", "README.md"]
    )
    # GitHub score = 0.75
    mock_get_files.return_value = {"main.py", "utils.py", "requirements.txt", "LICENSE"}
    out = cq.compute("https://huggingface.co/user/model, https://github.com/user/repo")
    # Total score = 0.65 + 0.75 = 1.4, which is capped at 1.0
    assert out["value"] == 1.0


def test_irrelevant_urls_score_zero() -> None:
    """Tests that URLs not from GitHub or Hugging Face are ignored."""
    out = cq.compute("https://example.com, https://another-site.org/model")
    assert out["value"] == 0.0


@patch.object(cq, "model_info", side_effect=Exception("API is down"))
def test_hf_api_failure_scores_zero(mock_model_info: MagicMock) -> None:
    """Tests that a failure in the Hugging Face API call results in a score of 0."""
    out = cq.compute("https://huggingface.co/user/failing-model")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)


@patch.object(cq, "get_github_repo_files", side_effect=Exception("API is down"))
def test_github_api_failure_scores_zero(mock_get_files: MagicMock) -> None:
    """Tests that a failure in the GitHub API call results in a score of 0."""
    out = cq.compute("https://github.com/user/failing-repo")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int)
