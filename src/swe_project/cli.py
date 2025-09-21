"""
swe_project.cli

Implements the CLI for Phase 1 with three commands:
  install  -> pip install -r requirements.txt
              (adds --user if not in a venv)
  score    -> read URLs file and print NDJSON (stub metrics)
  test     -> run pytest under coverage and print:
              "X/Y test cases passed. Z% line coverage achieved."
Pure stdlib only.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from typing import List, Tuple

from swe_project.core.exec_pool import run_parallel
from swe_project.core.scoring import combine
from swe_project.logger import setup_logging

# from swe_project.metrics import bus_factor  # noqa: F401
from swe_project.metrics import performance_claims  # noqa: F401

# from swe_project.metrics import ramp_up_time  # noqa: F401
# from swe_project.metrics import (  # add license, dataset_and_code, dataset_quality,
# code_quality when ready; noqa: F401
#    size_score,
# )
from swe_project.metrics.base import registered

# ---------------- URL categorization regexes ----------------

# MODEL: any huggingface.co/{org}/{repo}[optional /tree/...], but NOT datasets/*
HF_MODEL = re.compile(
    r"https?://(?:www\.)?huggingface\.co/(?!datasets/)[^/\s]+/[^/\s]+"
    r"(?:/tree/[^ \t\n\r\f\v]*)?$",
    re.IGNORECASE,
)
# DATASET (ignored for output)
HF_DATASET = re.compile(
    r"https?://(?:www\.)?huggingface\.co/datasets/[^ \t\n\r\f\v]+",
    re.IGNORECASE,
)
# Code on GitHub (ignored for output; optional)
GITHUB_CODE = re.compile(
    r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+(?:/[^ \t\n\r\f\v]*)?$",
    re.IGNORECASE,
)


# ---------- helpers ----------


def _run(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a subprocess and capture output."""
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def _read_urls(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _pytest_counts(text: str) -> Tuple[int, int]:
    """Parse pytest summary to (passed, total)."""
    passed = 0
    total = 0

    # collected N items
    m = re.search(r"collected\s+(\d+)\s+items?", text)
    total_hint = int(m.group(1)) if m else 0

    def sum_matches(pattern: str) -> int:
        s = 0
        for mm in re.finditer(rf"(\d+)\s+{pattern}\b", text):
            s += int(mm.group(1))
        return s

    passed = sum_matches("passed")
    failed = sum_matches("failed")
    errors = sum_matches("error|errors")
    skipped = sum_matches("skipped")
    xfailed = sum_matches("xfailed")
    xpassed = sum_matches("xpassed")
    warns = sum_matches("warning|warnings")

    total = passed + failed + errors + skipped + xfailed + xpassed + warns
    if total == 0 and total_hint:
        total = total_hint
    return passed, total


def _coverage_percent(text: str) -> int:
    """Grab the TOTAL % from 'coverage report' output."""
    for line in text.splitlines():
        if line.strip().startswith("TOTAL"):
            m = re.search(r"(\d+)%\s*$", line)
            if m:
                return int(m.group(1))
    m2 = re.search(r"TOTAL.*?(\d+)%", text, flags=re.S | re.M)
    return int(m2.group(1)) if m2 else 0


def _in_venv() -> bool:
    """Detect if Python is running inside a virtual environment."""
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix


# ---------- commands ----------


def cmd_install() -> int:
    logging.info("Installing dependencies from requirements.txt ...")

    print("Installing dependencies from requirements.txt ...")

    args = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    if not _in_venv():
        args.insert(4, "--user")  # only use --user outside venv
    code, out, err = _run(args)
    if code == 0:
        logging.info("Dependencies installed.")
        return 0
    print((err or out) or "Installation failed.", file=sys.stderr)
    logging.error("Installation failed: %s", (err or out))
    return 1


def cmd_score(url_file: str) -> int:
    """
    Read newline-delimited URLs from `url_file` and emit ONE NDJSON line
    per MODEL URL only, using the full Table-1 schema with placeholder values.
    Datasets and code URLs are ignored for output.
    """
    try:
        urls = _read_urls(url_file)
    except OSError as e:
        logging.error("failed to read URL FILE: %s", e)
        print(json.dumps({"event": "error", "error": str(e), "url_file": url_file}))
        return 1

    logging.info("Scoring %d URLs from %s ...", len(urls), url_file)

    for u in urls:
        if not HF_MODEL.match(u):
            logging.debug("Ignoring non-model URL: %s", u)
            logging.debug("registered metrics: %s", [f for _, f, _ in registered()])
            continue

        def _make_metric_task(metric_func, model_url: str):
            def task():
                return metric_func(model_url)  # zero-arg callable for the pool

            return task

        # --- build tasks from registry (each compute(model_url) -> {"value", "latency_ms"}) ---
        tasks = []
        for _, field, compute in registered():
            # capture current compute and URL to avoid the late-binding lambda bug
            tasks.append((field, _make_metric_task(compute, u)))

        # run metrics in parallel
        t0 = time.perf_counter()
        results = run_parallel(tasks, timeout_s=90)
        net_latency_ms = int((time.perf_counter() - t0) * 1000)

        # helpers for safe extraction
        def _val(name: str) -> float:
            return float(results.get(name, {}).get("value", 0.0))

        def _lat(name: str) -> int:
            return int(results.get(name, {}).get("latency_ms", 0))

        # size_score is a dict; ensure all four device keys
        size_map = results.get("size_score", {}).get("value", {}) or {}
        for k in ("raspberry_pi", "jetson_nano", "desktop_pc", "aws_server"):
            size_map.setdefault(k, 0.0)
        size_lat = _lat("size_score")

        # gather scalar metrics for net score; use mean of size_map for its scalar
        scalars = {
            "ramp_up_time": _val("ramp_up_time"),
            "bus_factor": _val("bus_factor"),
            "license": _val("license"),
            "dataset_and_code_score": _val("dataset_and_code_score"),
            "dataset_quality": _val("dataset_quality"),
            "code_quality": _val("code_quality"),
            "performance_claims": _val("performance_claims"),
            "size_score": (sum(size_map.values()) / 4.0),
        }
        net = float(combine(scalars))

        payload = {
            "name": u,
            "category": "MODEL",
            "net_score": round(net, 3),
            "net_score_latency": net_latency_ms,
            "ramp_up_time": scalars["ramp_up_time"],
            "ramp_up_time_latency": _lat("ramp_up_time"),
            "bus_factor": scalars["bus_factor"],
            "bus_factor_latency": _lat("bus_factor"),
            "performance_claims": scalars["performance_claims"],
            "performance_claims_latency": _lat("performance_claims"),
            "license": scalars["license"],
            "license_latency": _lat("license"),
            "size_score": size_map,
            "size_score_latency": size_lat,
            "dataset_and_code_score": scalars["dataset_and_code_score"],
            "dataset_and_code_score_latency": _lat("dataset_and_code_score"),
            "dataset_quality": scalars["dataset_quality"],
            "dataset_quality_latency": _lat("dataset_quality"),
            "code_quality": scalars["code_quality"],
            "code_quality_latency": _lat("code_quality"),
        }
        print(json.dumps(payload))

    return 0


def cmd_test() -> int:
    """
    Run pytest under coverage and print exactly:
      'X/Y test cases passed. Z% line coverage achieved.'
    """

    logging.info("Running tests with coverage...")

    cov_ok = True
    code, out, err = _run(
        [sys.executable, "-m", "coverage", "run", "-m", "pytest", "tests"]
    )

    if code != 0 and "No module named coverage" in (out + err):
        cov_ok = False
        code, out, err = _run([sys.executable, "-m", "pytest", "tests"])

    combined = (out or "") + "\n" + (err or "")
    passed, total = _pytest_counts(combined)

    percent = 0
    if cov_ok:
        _, rep_out, rep_err = _run([sys.executable, "-m", "coverage", "report"])
        percent = _coverage_percent((rep_out or "") + "\n" + (rep_err or ""))

    logging.info("Tests completed: %d/%d passed, %d%% coverage", passed, total, percent)
    print(f"{passed}/{total} test cases passed. {percent}% line coverage achieved.")
    return 0 if code == 0 else 1


# ---------- entrypoint ----------


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    logging.info("CLI started successfully")
    parser = argparse.ArgumentParser(prog="run", description="SWE-Project CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("install")

    p_score = sub.add_parser("score")
    p_score.add_argument("url_file", help="Text file with one URL per line")

    sub.add_parser("test")

    args = parser.parse_args(argv)

    if args.cmd == "install":
        return cmd_install()
    if args.cmd == "score":
        return cmd_score(args.url_file)
    if args.cmd == "test":
        return cmd_test()

    parser.print_help()
    return 2


if __name__ == "__main__":
    # Allows: python -m swe_project.cli ...
    raise SystemExit(main())
