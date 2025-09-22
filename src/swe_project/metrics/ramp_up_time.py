import os
import time

from swe_project.core.hf_client import download_snapshot
from swe_project.llm_client import ask_llm
from swe_project.metrics.base import register


def compute(model_url: str):
    """
    Compute ramp-up time score by analyzing README with LLM.
    """
    t0 = time.perf_counter()

    # convert HF URL into repo_id (org/repo)
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

    # send the readme to the llm for evaluation
    # asking llm for a score between 0 and 1 based on the given criteria
    response = ask_llm(
        [
            {
                "role": "system",
                "content": "You are a strict evaluator of documentation clarity.",
            },
            {
                "role": "user",
                "content": f"Rate the clarity and completeness of this README in a single \
                number between 0 for the worst documentation and 1 for the perfect documentation.This is used to \
                measure the ramp-up time based on how informative and \
                clear the documentation in the README is:\n\n{readme_text[:4000]}",
            },
        ]
    )

    # try to parse the response as a float between 0 and 1
    try:
        score = max(0.0, min(1.0, float(response)))
    except ValueError:
        score = 0.0  # fallback if LLM doesn’t give a number

    return {
        "value": score,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }

    # register the metric


register("ramp_up_time", "ramp_up_time", compute)
