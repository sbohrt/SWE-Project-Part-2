"""
Tests for the reviewedness metric.

The reviewedness metric calculates the fraction of code introduced via
reviewed pull requests in the associated GitHub repository.

Returns -1 if there is no linked GitHub repository.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_download_snapshot():
    """Mock download_snapshot to return a temp directory with test files."""
    with patch('metrics.reviewedness.download_snapshot') as mock:
        yield mock


@pytest.fixture
def mock_model_info():
    """Mock model_info to return test model metadata."""
    with patch('metrics.reviewedness.model_info') as mock:
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests for GitHub API calls."""
    with patch('metrics.reviewedness.requests') as mock:
        yield mock


def test_reviewedness_no_github_repo(mock_download_snapshot):
    """Test model with no GitHub repository."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# My Model\n\nNo GitHub link here.")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert result["value"] == -1.0
        assert "latency_ms" in result


def test_reviewedness_github_in_readme(mock_download_snapshot, mock_requests):
    """Test extracting GitHub URL from README."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("""
# My Model

Code available at: https://github.com/user/repo
""")

        mock_download_snapshot.return_value = tmpdir

        # Mock GitHub API responses
        mock_repo_response = MagicMock()
        mock_repo_response.status_code = 200
        mock_repo_response.json.return_value = {"name": "repo"}

        mock_pr_response = MagicMock()
        mock_pr_response.status_code = 200
        mock_pr_response.json.return_value = [
            {"number": 1, "merged_at": "2024-01-01"},
            {"number": 2, "merged_at": "2024-01-02"},
        ]

        mock_review_response = MagicMock()
        mock_review_response.status_code = 200
        mock_review_response.json.return_value = [
            {"id": 1, "state": "APPROVED"}
        ]

        mock_requests.get.side_effect = [
            mock_repo_response,
            mock_pr_response,
            mock_review_response,
            mock_review_response,
        ]

        result = compute("https://huggingface.co/my-model")

        # Should find GitHub repo and calculate fraction
        assert result["value"] >= 0.0
        assert result["value"] <= 1.0


def test_reviewedness_all_prs_reviewed(mock_download_snapshot, mock_requests):
    """Test repository where all PRs have reviews."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("https://github.com/org/project")

        mock_download_snapshot.return_value = tmpdir

        # Mock GitHub API
        mock_repo = MagicMock()
        mock_repo.status_code = 200

        mock_prs = MagicMock()
        mock_prs.status_code = 200
        mock_prs.json.return_value = [
            {"number": 1, "merged_at": "2024-01-01"},
            {"number": 2, "merged_at": "2024-01-02"},
        ]

        mock_reviews = MagicMock()
        mock_reviews.status_code = 200
        mock_reviews.json.return_value = [{"id": 1}]

        mock_requests.get.side_effect = [
            mock_repo,
            mock_prs,
            mock_reviews,
            mock_reviews,
        ]

        result = compute("https://huggingface.co/my-model")

        # All PRs reviewed = 1.0
        assert result["value"] == 1.0


def test_reviewedness_no_prs_reviewed(mock_download_snapshot, mock_requests):
    """Test repository where no PRs have reviews."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("[GitHub](https://github.com/org/project)")

        mock_download_snapshot.return_value = tmpdir

        # Mock GitHub API
        mock_repo = MagicMock()
        mock_repo.status_code = 200

        mock_prs = MagicMock()
        mock_prs.status_code = 200
        mock_prs.json.return_value = [
            {"number": 1, "merged_at": "2024-01-01"},
            {"number": 2, "merged_at": "2024-01-02"},
        ]

        mock_no_reviews = MagicMock()
        mock_no_reviews.status_code = 200
        mock_no_reviews.json.return_value = []

        mock_requests.get.side_effect = [
            mock_repo,
            mock_prs,
            mock_no_reviews,
            mock_no_reviews,
        ]

        result = compute("https://huggingface.co/my-model")

        # No reviews = 0.0
        assert result["value"] == 0.0


def test_reviewedness_partial_reviews(mock_download_snapshot, mock_requests):
    """Test repository with some reviewed PRs."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("https://github.com/user/repo")

        mock_download_snapshot.return_value = tmpdir

        mock_repo = MagicMock()
        mock_repo.status_code = 200

        mock_prs = MagicMock()
        mock_prs.status_code = 200
        mock_prs.json.return_value = [
            {"number": 1, "merged_at": "2024-01-01"},
            {"number": 2, "merged_at": "2024-01-02"},
            {"number": 3, "merged_at": "2024-01-03"},
            {"number": 4, "merged_at": "2024-01-04"},
        ]

        # First two have reviews, last two don't
        mock_has_reviews = MagicMock()
        mock_has_reviews.status_code = 200
        mock_has_reviews.json.return_value = [{"id": 1}]

        mock_no_reviews = MagicMock()
        mock_no_reviews.status_code = 200
        mock_no_reviews.json.return_value = []

        mock_requests.get.side_effect = [
            mock_repo,
            mock_prs,
            mock_has_reviews,
            mock_has_reviews,
            mock_no_reviews,
            mock_no_reviews,
        ]

        result = compute("https://huggingface.co/my-model")

        # 2/4 = 0.5
        assert result["value"] == 0.5


def test_reviewedness_no_merged_prs(mock_download_snapshot, mock_requests):
    """Test repository with no merged PRs."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("https://github.com/user/repo")

        mock_download_snapshot.return_value = tmpdir

        mock_repo = MagicMock()
        mock_repo.status_code = 200

        mock_prs = MagicMock()
        mock_prs.status_code = 200
        # Only closed PRs without merged_at
        mock_prs.json.return_value = [
            {"number": 1, "merged_at": None},
            {"number": 2, "merged_at": None},
        ]

        mock_requests.get.side_effect = [mock_repo, mock_prs]

        result = compute("https://huggingface.co/my-model")

        # No merged PRs = 0.0
        assert result["value"] == 0.0


def test_reviewedness_github_api_error(mock_download_snapshot, mock_requests):
    """Test handling of GitHub API errors."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("https://github.com/user/repo")

        mock_download_snapshot.return_value = tmpdir

        # Mock API error
        mock_error = MagicMock()
        mock_error.status_code = 404

        mock_requests.get.return_value = mock_error

        result = compute("https://huggingface.co/my-model")

        # API error should return 0.0
        assert result["value"] == 0.0


def test_reviewedness_network_error(mock_download_snapshot, mock_requests):
    """Test handling of network errors."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("Code: https://github.com/user/repo\n")

        mock_download_snapshot.return_value = tmpdir

        # Mock network error
        import requests
        mock_requests.get.side_effect = requests.exceptions.RequestException("Network error")

        result = compute("https://huggingface.co/my-model")

        # Network error during API call should return 0.0
        # If GitHub URL not found, returns -1.0
        assert result["value"] in [0.0, -1.0]


def test_reviewedness_invalid_github_url(mock_download_snapshot):
    """Test handling of invalid GitHub URLs."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("https://github.com/invalid")  # Missing repo name

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        # Invalid URL should return 0.0 or -1.0
        assert result["value"] in [0.0, -1.0]


def test_reviewedness_markdown_link_format(mock_download_snapshot, mock_requests):
    """Test extraction from markdown link format."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("[Source Code](https://github.com/org/my-repo)")

        mock_download_snapshot.return_value = tmpdir

        mock_repo = MagicMock()
        mock_repo.status_code = 200

        mock_prs = MagicMock()
        mock_prs.status_code = 200
        mock_prs.json.return_value = []

        mock_requests.get.side_effect = [mock_repo, mock_prs]

        result = compute("https://huggingface.co/my-model")

        # Should extract URL from markdown link
        assert result["value"] >= 0.0


def test_reviewedness_latency_measurement(mock_download_snapshot):
    """Test that latency is properly measured."""
    from metrics.reviewedness import compute

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("No GitHub link")

        mock_download_snapshot.return_value = tmpdir

        result = compute("https://huggingface.co/my-model")

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0


def test_reviewedness_exception_handling(mock_download_snapshot):
    """Test error handling when download fails."""
    from metrics.reviewedness import compute

    mock_download_snapshot.side_effect = Exception("Download failed")

    result = compute("https://huggingface.co/my-model")

    # Should return -1.0 on error
    assert result["value"] == -1.0
    assert "latency_ms" in result
