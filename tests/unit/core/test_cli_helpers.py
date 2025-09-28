from __future__ import annotations

import csv
import io
from pathlib import Path

# we import the helper functions directly from the CLI module
from swe_project.cli import _coverage_percent, _iter_models_from_csv, _pytest_counts
from swe_project.core.model_url import is_hf_model_url


# -----------------------------
# is_hf_model_url quick sanity
# -----------------------------
def test_is_hf_model_url_good_and_bad():
    assert is_hf_model_url("https://huggingface.co/org/name")
    assert is_hf_model_url("https://huggingface.co/org/name/tree/main")
    assert is_hf_model_url("https://huggingface.co/org/name/resolve/v1/model.bin")

    # datasets should be rejected
    assert not is_hf_model_url("https://huggingface.co/datasets/org/data")
    # random URLs should be rejected
    assert not is_hf_model_url("https://example.com/anything")


# -----------------------------
# _pytest_counts
# -----------------------------
def test_pytest_counts_prefers_collected_hint():
    text = "collected 7 items\n5 passed, 1 failed, 1 skipped"
    passed, total = _pytest_counts(text)
    assert passed == 5 and total == 7


def test_pytest_counts_without_collected_uses_buckets():
    # no "collected" line → sum buckets
    text = "2 passed, 1 failed, 2 errors, 1 skipped, 1 xfailed"
    passed, total = _pytest_counts(text)
    # 2+1+2+1+1 = 7
    assert passed == 2 and total == 7


# -----------------------------
# _coverage_percent
# -----------------------------
def test_coverage_percent_on_total_line():
    report = "Name  Stmts  Miss  Cover\nTOTAL  100    20   80%"
    assert _coverage_percent(report) == 80


def test_coverage_percent_fallback_greps():
    # no line startswith("TOTAL"), but TOTAL appears later
    report = "foo\nsomething TOTAL ... 73%\nbar"
    assert _coverage_percent(report) == 73


# -----------------------------
# _iter_models_from_csv
# -----------------------------
def test_iter_models_from_csv_handles_comments_blanks_and_padding(tmp_path):
    """
    - ignores blank lines and comment lines
    - pads short rows to 3 cells
    - yields only valid HF *model* URLs (not datasets)
    """
    p: Path = tmp_path / "urls.csv"

    # Build a small CSV in memory then write it
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([])  # blank
    w.writerow(["# this is a comment"])
    # Proper triple: code_url, dataset_url, model_url
    w.writerow(
        [
            "https://github.com/org/repo",
            "https://huggingface.co/datasets/user/ds",
            "https://huggingface.co/a/b",
        ]
    )
    # Only 2 columns → should be padded so last cell is still model_url
    w.writerow(["code-ignored-here", "https://huggingface.co/c/d"])
    # Not a model URL
    w.writerow(["", "", "https://example.com/not-a-model"])
    # Dataset URL → must be ignored
    w.writerow(["", "", "https://huggingface.co/datasets/user/xyz"])
    # Valid with /tree path
    w.writerow(["", "", "https://huggingface.co/e/f/tree/main"])

    p.write_text(buf.getvalue(), encoding="utf-8")

    out = list(_iter_models_from_csv(str(p)))
    assert out == [
        "https://huggingface.co/a/b",
        "https://huggingface.co/c/d",
        "https://huggingface.co/e/f/tree/main",
    ]
