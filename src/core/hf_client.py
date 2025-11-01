from __future__ import annotations

from typing import Any, Optional

from huggingface_hub import HfApi, snapshot_download
from tqdm.auto import tqdm  # needed to silence the progress bars

_api = HfApi()


def model_info(repo_id: str, revision: Optional[str] = None) -> Any:
    """
    Thin wrapper around HfApi.model_info that tolerates older/test fakes
    which may not accept keyword args like 'revision' or 'files_metadata'.
    """
    try:
        return _api.model_info(repo_id, revision=revision, files_metadata=True)
    except TypeError:
        # test doubles or older clients without kwargs
        return _api.model_info(repo_id)


def dataset_info(repo_id: str, revision: Optional[str] = None) -> Any:
    """
    Similar tolerance for dataset_info (some fakes don't accept kwargs).
    """
    try:
        return _api.dataset_info(repo_id, revision=revision, files_metadata=True)
    except TypeError:
        return _api.dataset_info(repo_id)


# this is to silence the progress bars from huggingface_hub snapshot_download
class SilentTqdm(tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, disable=True)


# what we did was to create a subclass of tqdm that is always disabled, and pass it to snapshot_download


def download_snapshot(repo_id: str, allow_patterns):
    return str(
        snapshot_download(
            repo_id=repo_id,
            allow_patterns=allow_patterns,
            local_dir_use_symlinks=False,
            tqdm_class=SilentTqdm,
        )
    )
