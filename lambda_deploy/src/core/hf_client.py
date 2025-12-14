from __future__ import annotations

from typing import Any, Optional

from huggingface_hub import HfApi, snapshot_download, hf_hub_download
from tqdm.auto import tqdm  # needed to silence the progress bars

# -------- CHANGES MADE FOR STEP 2 ---------
import json
import os
from pathlib import Path
# ------------------------------------------

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
        kwargs['disable'] = True
        super().__init__(*args, **kwargs)


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


# ------------- ADDED FOR STEP 2 ---------------

def model_config(repo_id: str, revision: Optional[str] = None) -> dict:
    """
    Download and parse config.json for a Hugging Face model repo.

    Returns an empty dict if config.json is missing or invalid.
    """
    # Reuse snapshot_download so we don't duplicate logic
    snapshot_dir = snapshot_download(
        repo_id=repo_id,
        revision=revision,
        allow_patterns=["config.json"],
        local_dir_use_symlinks=False,
        tqdm_class=SilentTqdm,
    )

    config_path = Path(snapshot_dir) / "config.json"
    if not config_path.exists():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # malformed config
        return {}


def readme_text(repo_id: str, repo_type: str = "model", revision: Optional[str] = None) -> str:
    """
    Fetch README text for a HuggingFace repo (model or dataset).

    This is used to support /artifact/byRegEx which must search names AND READMEs.
    We keep this best-effort: return "" if missing/unavailable.
    """
    # Try a few common filename casings
    candidates = ["README.md", "readme.md", "README.MD", "README"]
    for filename in candidates:
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type=repo_type,
                revision=revision,
            )
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                # limit size to keep DynamoDB item small-ish
                return f.read(50_000)
        except Exception:
            continue
    return ""
