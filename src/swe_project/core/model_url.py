# src/swe_project/core/model_url.py
from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse


def to_repo_id(hf_url: str) -> Tuple[str, Optional[str]]:
    """
    Normalize Hugging Face model URLs to ('org/name', optional_branch).

    Accepts forms like:
      https://huggingface.co/org/name
      https://huggingface.co/org/name/
      https://huggingface.co/org/name/tree/main
      https://huggingface.co/org/name/resolve/main/pytorch_model.bin
      http://www.huggingface.co/org/name?foo=bar

    Returns:
      (repo_id='org/name', branch='main' | None)
    """
    s = hf_url.strip()

    # Allow bare paths like "huggingface.co/org/name"
    if "://" not in s:
        s = "https://" + s

    p = urlparse(s)
    # Accept any host that ends with huggingface.co (incl. enterprise subdomains)
    if not p.netloc.endswith("huggingface.co"):
        # Not an HF URL; fall back to returning the stripped input as the id.
        return hf_url.strip(), None

    parts = [seg for seg in p.path.split("/") if seg]  # remove empty segments

    if len(parts) < 2:
        # Not enough info to form org/name
        return hf_url.strip(), None

    org, name = parts[0], parts[1]
    branch = None

    # Handle /tree/<branch> or /resolve/<branch>
    if len(parts) >= 4 and parts[2] in {"tree", "resolve"}:
        branch = parts[3]

    repo_id = f"{org}/{name}"
    return repo_id, branch
