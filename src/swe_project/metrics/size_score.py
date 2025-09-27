from __future__ import annotations

import time
from typing import Dict, Iterable, Optional, cast

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import MetricResult, register

# Weight-file extensions we count toward model size
_WEIGHT_EXTS: Iterable[str] = (".safetensors", ".bin", ".onnx", ".tflite", ".h5", ".pt")


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _sum_weight_megabytes(repo_id: str, revision: Optional[str]) -> float:
    """
    Use Hugging Face *metadata* (no big file downloads) to sum sizes of weight files.
    Returns total size in MB (base-10: 1 MB = 1e6 bytes). Falls back to 0 on any error.
    """
    try:
        info = model_info(
            repo_id, revision=revision
        )  # files_metadata=True in hf_client
        # Newer huggingface_hub exposes per-file metadata under `siblings` or `siblings_with_metadata`
        files = (
            getattr(info, "siblings", None)
            or getattr(info, "siblings_with_metadata", None)
            or []
        )

        total_bytes = 0
        for f in files:
            # Compatible access for both dict-like and object-like entries
            fname = (
                getattr(f, "rfilename", None)
                or getattr(f, "path", None)
                or getattr(f, "filename", None)
            )
            fsize = getattr(f, "size", None)
            if isinstance(fname, str) and isinstance(fsize, int):
                if any(fname.lower().endswith(ext) for ext in _WEIGHT_EXTS):
                    total_bytes += fsize

        return total_bytes / 1_000_000.0  # MB (decimal)
    except Exception:
        # Be fail-safe: if metadata fetch fails, treat as 0 MB so we don't crash the whole run
        return 0.0


def _device_capacities_mb() -> Dict[str, float]:
    """
    Rough capacity budget (in MB) per device class. These are tunable heuristics.
    The score is computed as: max(0, 1 - (model_mb / capacity_mb)).
    """
    return {
        "raspberry_pi": 500.0,  # smaller budget → large models score near 0
        "jetson_nano": 1500.0,
        "desktop_pc": 8000.0,
        "aws_server": 16000.0,
    }


def _scores_from_size(total_mb: float) -> Dict[str, float]:
    caps = _device_capacities_mb()
    scores: Dict[str, float] = {}
    for device, cap in caps.items():
        # Linear decay with clamp into [0, 1], rounded to 2 decimal places
        scores[device] = round(_clamp01(1.0 - (total_mb / cap)), 2) if cap > 0 else 0.0
    return scores


def compute(model_url: str) -> MetricResult:
    """
    Compute 'size_score' as a per-device compatibility dict using HF metadata only.
    Returns:
      {
        "value": { "raspberry_pi": float, "jetson_nano": float, "desktop_pc": float, "aws_server": float },
        "latency_ms": int
      }
    """
    t0 = time.perf_counter()
    try:
        repo_id, revision = to_repo_id(model_url)
        total_mb = _sum_weight_megabytes(repo_id, revision)
        scores = _scores_from_size(total_mb)  # Dict[str, float] (already rounded)

        return cast(
            MetricResult,
            {
                "value": scores,  # dict[str, float]
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
    except Exception:
        return cast(
            MetricResult,
            {
                "value": {
                    "raspberry_pi": 0.0,
                    "jetson_nano": 0.0,
                    "desktop_pc": 0.0,
                    "aws_server": 0.0,
                },
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )


# Register the metric so the CLI can discover it
register("size_score", "size_score", compute)
