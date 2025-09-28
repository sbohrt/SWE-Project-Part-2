from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlparse

_BLOCK = {"datasets", "spaces", "models", "docs"}


def to_repo_id(hf_url: str) -> Tuple[str, Optional[str]]:
    """
    Normalize Hugging Face model URLs to ('org/name' OR 'name', optional_branch).

    Accepts forms like:
      https://huggingface.co/org/name
      https://huggingface.co/name                     # root-level repo (e.g., gpt2)
      https://huggingface.co/org/name/
      https://huggingface.co/org/name/tree/main
      https://huggingface.co/org/name/resolve/main/pytorch_model.bin
      http://www.huggingface.co/org/name?foo=bar

    Returns:
      (repo_id, branch) where repo_id is NEVER None (kept as str for metrics),
      and branch may be None.
      If not an HF URL, we **return the original input string** (backward compatible).
    """
    s = (hf_url or "").strip()
    if not s:
        return hf_url.strip(), None

    # Allow bare paths like "huggingface.co/org/name"
    if "://" not in s:
        s = "https://" + s

    p = urlparse(s)
    # Accept any host that ends with huggingface.co (incl. enterprise subdomains)
    if not p.netloc.endswith("huggingface.co"):
        # Not an HF URL; preserve old behavior so metrics don't crash
        return hf_url.strip(), None

    parts = [seg for seg in p.path.split("/") if seg]  # remove empty segments
    if not parts:
        # No repo segment; preserve old behavior
        return hf_url.strip(), None

    # repo_id can be 1-seg (root-level) or 2-seg (org/name)
    branch: Optional[str] = None
    if len(parts) >= 2:
        repo_id = f"{parts[0]}/{parts[1]}"
        rest = parts[2:]
    else:
        repo_id = parts[0]
        rest = []

    # Handle /tree/<branch> or /resolve/<branch>/...
    if len(rest) >= 2 and rest[0] in {"tree", "resolve"}:
        branch = rest[1]

    return repo_id, branch


def is_hf_model_url(hf_url: str) -> bool:
    """
    True iff the URL points to a Hugging Face *model* repo.
    Accepts root-level (e.g., https://huggingface.co/gpt2) and org/name.
    Excludes datasets/spaces/docs/models sections.
    """
    s = (hf_url or "").strip()
    if not s:
        return False
    if "://" not in s:
        s = "https://" + s
    p = urlparse(s)
    if not p.netloc.endswith("huggingface.co"):
        return False
    parts = [seg for seg in p.path.split("/") if seg]
    if not parts:
        return False
    if parts[0] in _BLOCK:
        return False
    # At least one segment (root-level) is OK; second segment (org/name) also OK.
    return True
