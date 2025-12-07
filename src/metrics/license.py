import os
import re
import time
from typing import Optional, Tuple

from swe_project.core.hf_client import download_snapshot, model_info
from swe_project.metrics.base import register

# Simple regex to catch license mentions in README (ai generated)
LICENSE_PATTERN = re.compile(
    r"(?i)(?:license|licensed under)\s*[:\-]?\s*([A-Za-z0-9\.\-+]+)"
)

# map licenses to scores (1.0 = compatible, 0.0 = incompatible, 0.5 = unclear/custom)
LICENSE_SCORES = {
    "apache-2.0": 1.0,
    "mit": 1.0,
    "bsd-3-clause": 1.0,
    "bsd-2-clause": 1.0,
    "lgpl-2.1": 1.0,
    "mpl-2.0": 1.0,
    "gpl-3.0": 0.0,
    "agpl-3.0": 0.0,
    "proprietary": 0.0,
}


def normalize_license(raw: Optional[str]) -> Tuple[float, str]:
    """normalize raw license string to score + SPDX-like identifier."""
    if not raw:  # if there is no license info found
        return 0.0, "None"

    key = raw.lower().strip()
    if key in LICENSE_SCORES:
        return LICENSE_SCORES[key], key

    # fallback: unclear/custom license
    return 0.5, key


def compute(model_url: str):
    """
    Compute license metric:
      - Check Hugging Face metadata for license.
      - If missing, scan README.md for license mention.
      - Score = 1.0 (compatible), 0.5 (unclear), or 0.0 (incompatible).
    """
    t0 = time.perf_counter()

    repo_id = model_url.replace("https://huggingface.co/", "").strip("/")

    # 1. Try Hugging Face model metadata
    try:
        info = model_info(repo_id)
        raw_license = getattr(info, "license", None)
        score, license_id = normalize_license(raw_license)
    except Exception:
        raw_license = None
        score, license_id = 0.0, "None"

    # 2. check readme if no license found
    if (not raw_license) or (score == 0.5):
        try:
            local_path = download_snapshot(repo_id, allow_patterns=["README.md"])
            readme_file = os.path.join(local_path, "README.md")

            if os.path.exists(readme_file):
                with open(readme_file, "r", encoding="utf-8") as f:
                    text = f.read()

                m = LICENSE_PATTERN.search(text)
                if m:
                    raw_license = m.group(1)
                    score, license_id = normalize_license(raw_license)
        except Exception:
            pass  # ignore if README not found

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# register in the metrics registry
register("license", "license", compute)
