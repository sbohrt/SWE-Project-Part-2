import os
import re
import time

from swe_project.core.hf_client import download_snapshot
from swe_project.llm_client import ask_llm
from swe_project.metrics.base import register


def compute(model_url: str):
    """
    Compute ramp-up time score by analyzing README with LLM.
    """
    t0 = time.perf_counter()

    # Convert HF URL into repo_id (org/repo)
    repo_id = model_url.replace("https://huggingface.co/", "").strip("/")

    # download README.md (if exists)
    local_path = download_snapshot(repo_id, allow_patterns=["README.md"])
    readme_file = os.path.join(local_path, "README.md")

    if not os.path.exists(readme_file):
        return {
            "value": 0.0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    with open(readme_file, "r", encoding="utf-8") as f:
        readme_text = f.read()

    # ask LLM to give a score based on documentation clarity
    response = ask_llm(
        [
            {
                "role": "system",
                "content": "You are a strict evaluator of documentation clarity.",
            },
            {
                "role": "user",
                "content": (
                    "Rate the clarity and completeness of this README in a single number "
                    "between 0 (worst) and 1 (best). Respond with just the number.\n\n"
                    f"{readme_text[:4000]}"
                ),
            },
        ]
    )

    score = 0.0
    if response:
        # Try direct float parse first (this is because sometimes the gen ai gives numbers and words as well)
        try:
            score = float(response.strip())
        except ValueError:
            # Fallback: extract first number in response
            m = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", response)
            if m:
                score = float(m.group(1))

    # Clamp between 0 and 1
    score = max(0.0, min(1.0, score))

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# Register the metric
register("ramp_up_time", "ramp_up_time", compute)
