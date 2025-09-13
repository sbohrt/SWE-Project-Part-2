#!/usr/bin/env python3
"""
swe_project.cli

Implements the CLI for Phase 1 with three commands:
  install  -> pip install --user -r requirements.txt
  score    -> read URLs file and print NDJSON (stub metrics)
  test     -> run pytest under coverage and print:
              "X/Y test cases passed. Z% line coverage achieved."
Pure stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from typing import List, Tuple


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
    """Parse pytest summary into (passed, total)."""
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

    passed  = sum_matches("passed")
    failed  = sum_matches("failed")
    errors  = sum_matches("error|errors")
    skipped = sum_matches("skipped")
    xfailed = sum_matches("xfailed")
    xpassed = sum_matches("xpassed")
    warns   = sum_matches("warning|warnings")

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


# ---------- commands ----------

def cmd_install() -> int:
    """Install dependencies used by the grader and local runs."""
    print("Installing dependencies from requirements.txt ...")
    code, out, err = _run([sys.executable, "-m", "pip", "install", "--user", "-r", "requirements.txt"])
    if code == 0:
        print("Dependencies installed.")
        return 0
    print((err or out) or "Installation failed.", file=sys.stderr)
    return 1


def cmd_score(url_file: str) -> int:
    """
    Emit one NDJSON line per URL (minimal keys to satisfy tests).
    Aya's test expects keys: "name" and "net_score".
    We accept any huggingface.co URL for Milestone-2 stubs.
    """
    try:
        urls = _read_urls(url_file)
    except OSError as e:
        print(json.dumps({"event": "error", "error": str(e), "url_file": url_file}))
        return 1

    # Accept any Hugging Face URL with at least something after the domain.
    hf_any = re.compile(r"https?://(www\.)?huggingface\.co/\S+", re.I)

    # (Optional) simple timer to simulate latency if you want to extend later
    _ = time.perf_counter()

    for u in urls:
        if hf_any.match(u):
            # Minimal NDJSON object that Aya's test asserts on
            print(json.dumps({
                "name": u,
                "net_score": 0.0
            }))
    return 0


def cmd_test() -> int:
    """
    Run pytest under coverage and print exactly:
      'X/Y test cases passed. Z% line coverage achieved.'
    """
    # try with coverage first
    cov_ok = True
    code, out, err = _run([sys.executable, "-m", "coverage", "run", "-m", "pytest"])
    if code != 0 and "No module named coverage" in (out + err):
        cov_ok = False
        code, out, err = _run([sys.executable, "-m", "pytest"])

    combined = (out or "") + "\n" + (err or "")
    passed, total = _pytest_counts(combined)

    percent = 0
    if cov_ok:
        _, rep_out, rep_err = _run([sys.executable, "-m", "coverage", "report"])
        percent = _coverage_percent((rep_out or "") + "\n" + (rep_err or ""))

    print(f"{passed}/{total} test cases passed. {percent}% line coverage achieved.")
    return 0 if code == 0 else 1


# ---------- entrypoint ----------

def main(argv: list[str] | None = None) -> int:
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
    # Needed because Aya calls: python -m swe_project.cli …
    raise SystemExit(main())
