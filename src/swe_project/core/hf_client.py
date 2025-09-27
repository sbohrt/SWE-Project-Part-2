from __future__ import annotations

from typing import Any, Optional

from huggingface_hub import HfApi, snapshot_download

_api = HfApi()


def model_info(repo_id: str, revision: Optional[str] = None) -> Any:
    # include per-file sizes and names
    return _api.model_info(repo_id, revision=revision, files_metadata=True)


def dataset_info(repo_id: str) -> Any:
    return _api.dataset_info(repo_id)


def download_snapshot(repo_id: str, allow_patterns):
    return str(
        snapshot_download(
            repo_id=repo_id, allow_patterns=allow_patterns, local_dir_use_symlinks=False
        )
    )
