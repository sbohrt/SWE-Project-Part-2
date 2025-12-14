import os
import re
import time

from core.hf_client import download_snapshot
from llm_client import ask_llm
from metrics.base import register


def compute(model_url: str):
    """
    Compute ramp-up time score by analyzing README with LLM.
    Supports both Hugging Face repos and local absolute paths.
    """
    t0 = time.perf_counter()

    # case 1: Local repo path
    if os.path.isabs(model_url) and os.path.exists(model_url):
        readme_file = os.path.join(model_url, "README.md")

    else:
        # case 2: hugging Face repo
        repo_id = model_url.replace("https://huggingface.co/", "").strip("/")
        local_path = download_snapshot(repo_id, allow_patterns=["README.md"])
        readme_file = os.path.join(local_path, "README.md")

    if not os.path.exists(readme_file):
        return {
            "value": 0.0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    with open(readme_file, "r", encoding="utf-8") as f:
        readme_text = f.read()

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
        try:
            score = float(response.strip())
        except ValueError:
            m = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", response)
            if m:
                score = float(m.group(1))

    score = max(0.0, min(1.0, score))

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


register("ramp_up_time", "ramp_up_time", compute)
