"""
Reviewedness Metric

The fraction of all code (not weights) in the associated GitHub repository
that was introduced through pull requests with a code review.

Returns -1 if there is no linked GitHub repository.
"""
import os
import re
import time
from typing import Optional, Tuple

import requests

from src.core.hf_client import download_snapshot, model_info
from src.metrics.base import register


def _extract_github_url(model_url: str, readme_content: Optional[str] = None) -> Optional[str]:
    """
    Extract GitHub repository URL from model metadata or README.

    Args:
        model_url: HuggingFace model URL
        readme_content: Optional README content to search

    Returns:
        GitHub repository URL or None
    """
    repo_id = model_url.replace("https://huggingface.co/", "").strip("/")

    # Try to get from HuggingFace model info
    try:
        info = model_info(repo_id)
        # Check cardData for github links
        if hasattr(info, 'cardData') and info.cardData:
            card_data = info.cardData
            # Look for common fields
            for field in ['github', 'repository', 'repo', 'source']:
                if field in card_data:
                    url = card_data[field]
                    if isinstance(url, str) and 'github.com' in url:
                        return url
    except Exception:
        pass

    # Try to extract from README
    if readme_content:
        # Look for GitHub URLs in markdown links or plain text
        github_patterns = [
            r'https?://github\.com/[\w\-]+/[\w\-]+',
            r'\[.*?\]\((https?://github\.com/[\w\-]+/[\w\-]+)\)',
        ]

        for pattern in github_patterns:
            match = re.search(pattern, readme_content)
            if match:
                url = match.group(1) if match.lastindex else match.group(0)
                # Clean up the URL
                url = url.rstrip('/.)')
                return url

    return None


def _get_pr_review_fraction(github_url: str) -> float:
    """
    Calculate the fraction of code introduced via reviewed PRs.

    Args:
        github_url: GitHub repository URL

    Returns:
        Fraction (0.0 to 1.0) of code from reviewed PRs
    """
    # Extract owner and repo from URL
    match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', github_url.rstrip('/'))
    if not match:
        return 0.0

    owner, repo = match.groups()

    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        # Get repository statistics
        repo_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_response = requests.get(repo_url, headers=headers, timeout=10)

        if repo_response.status_code != 200:
            return 0.0

        # Get pull requests (merged only)
        pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        pr_params = {
            'state': 'closed',
            'per_page': 100,  # Sample last 100 PRs
            'sort': 'updated',
            'direction': 'desc'
        }

        pr_response = requests.get(pr_url, params=pr_params, headers=headers, timeout=10)

        if pr_response.status_code != 200:
            return 0.0

        pull_requests = pr_response.json()

        # Filter to merged PRs only
        merged_prs = [pr for pr in pull_requests if pr.get('merged_at')]

        if not merged_prs:
            return 0.0

        # Count PRs with reviews
        reviewed_prs = 0
        for pr in merged_prs[:50]:  # Check up to 50 most recent merged PRs
            pr_number = pr['number']

            # Get reviews for this PR
            reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
            reviews_response = requests.get(reviews_url, headers=headers, timeout=5)

            if reviews_response.status_code == 200:
                reviews = reviews_response.json()
                # Count as reviewed if there's at least one review
                if len(reviews) > 0:
                    reviewed_prs += 1

        # Calculate fraction
        total_checked = min(len(merged_prs), 50)
        if total_checked == 0:
            return 0.0

        fraction = reviewed_prs / total_checked
        return fraction

    except requests.exceptions.RequestException:
        return 0.0
    except Exception:
        return 0.0


def compute(model_url: str) -> dict:
    """
    Compute reviewedness metric.

    Calculates the fraction of code introduced via reviewed pull requests
    in the associated GitHub repository.

    Args:
        model_url: HuggingFace model URL

    Returns:
        dict: {"value": float, "latency_ms": int}
        value: -1 if no GitHub repo, 0.0-1.0 fraction otherwise
    """
    t0 = time.perf_counter()

    repo_id = model_url.replace("https://huggingface.co/", "").strip("/")
    score = -1.0  # Default: no GitHub repository

    try:
        # Download README to search for GitHub URL
        local_path = download_snapshot(repo_id, allow_patterns=["README.md"])
        readme_file = os.path.join(local_path, "README.md")

        readme_content = None
        if os.path.exists(readme_file):
            with open(readme_file, "r", encoding="utf-8", errors="ignore") as f:
                readme_content = f.read()

        # Extract GitHub URL
        github_url = _extract_github_url(model_url, readme_content)

        if github_url:
            # Calculate PR review fraction
            score = _get_pr_review_fraction(github_url)
        else:
            # No GitHub repository found
            score = -1.0

    except Exception:
        # Error during processing, assume no GitHub repo
        score = -1.0

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# Register in the metrics registry
register("reviewedness", "reviewedness", compute)
