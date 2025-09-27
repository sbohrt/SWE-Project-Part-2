from __future__ import annotations

import os
from typing import Any, List, Optional

from huggingface_hub import HfApi, snapshot_download

_api = HfApi()


def model_info(repo_id: str, revision: Optional[str] = None) -> Any:
    """Back-compat wrapper: prefer files_metadata, but fall back gracefully."""
    try:
        return _api.model_info(repo_id, revision=revision, files_metadata=True)
    except TypeError:
        # Older/Mocked clients that don't accept kwargs in tests
        return _api.model_info(repo_id)


def dataset_info(repo_id: str) -> Any:
    return _api.dataset_info(repo_id)


def download_snapshot(repo_id: str, allow_patterns: List[str]) -> str:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    return str(
        snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns,
            local_dir_use_symlinks=False,
        )
    )
