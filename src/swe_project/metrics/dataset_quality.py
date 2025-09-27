from __future__ import annotations

import logging
import time
from typing import Any

from swe_project.core.hf_client import dataset_info
from swe_project.metrics.base import MetricResult, register

NAME, FIELD = "dataset_quality", "dataset_quality"


def _score_single_dataset(d_info: Any) -> float:
    if getattr(d_info, "gated", False):
        return 0.0

    score = 0.0
    if getattr(d_info, "cardData", None):
        score += 0.5
    if getattr(d_info, "downloads", 0) > 1000:
        score += 0.25
    if getattr(d_info, "configs", []):
        score += 0.2
    if getattr(d_info, "viewer", False):
        score += 0.05

    return min(1.0, score)


def compute(input_line: str) -> MetricResult:
    t0 = time.perf_counter()
    total_score = 0.0

    urls = [url.strip() for url in input_line.split(",") if url.strip()]
    dataset_urls = [url for url in urls if "huggingface.co/datasets/" in url]

    if not dataset_urls:
        return {
            "value": 0.0,
            "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
        }

    try:
        dataset_ids = [
            url.split("huggingface.co/datasets/")[-1].split("/")[0]
            for url in dataset_urls
        ]

        for d_id in dataset_ids:
            try:
                d_info = dataset_info(d_id)
                total_score += _score_single_dataset(d_info)
            except Exception:
                logging.warning("%s: failed to fetch info for dataset %s", NAME, d_id)

        final_score = total_score / len(dataset_ids)

    except Exception:
        logging.exception("%s failed for line: %s", NAME, input_line)
        final_score = 0.0

    return {
        "value": float(max(0.0, min(1.0, final_score))),
        "latency_ms": int(round((time.perf_counter() - t0) * 1000)),
    }


register(NAME, FIELD, compute)

# if __name__ == "__main__":
#     import sys
#     import json
#     import os

#     if len(sys.argv) > 1:
#         first_arg = sys.argv[1]
#         lines_to_process = []
#         if os.path.isfile(first_arg):
#             try:
#                 with open(first_arg, 'r') as f:
#                     lines_to_process = f.readlines()
#             except IOError as e:
#                 print(f"Error reading file: {e}", file=sys.stderr)
#                 sys.exit(1)
#         else:
#             lines_to_process = [" ".join(sys.argv[1:])]

#         for line in lines_to_process:
#             line = line.strip()
#             if not line: continue
#             result = compute(input_line=line)
#             output_data = {
#                 "input_line": line,
#                 "dataset_quality": result["value"],
#                 "dataset_quality_latency": result["latency_ms"]
#             }
#             print(json.dumps(output_data))
#     else:
#         print("Usage 1: python -m ... <path_to_url_file>", file=sys.stderr)
#         print("Usage 2: python -m ... <URL1, URL2, ...>", file=sys.stderr)
