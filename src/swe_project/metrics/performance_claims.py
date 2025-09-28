from __future__ import annotations

import re
import time
from typing import Any, Iterable, Tuple

from huggingface_hub import ModelCard, hf_hub_download

from swe_project.core.hf_client import model_info
from swe_project.core.model_url import to_repo_id
from swe_project.metrics.base import register

NAME, FIELD = "performance_claims", "performance_claims"

# ------------ helpers ------------

_THIRD_PARTY_DOMAINS = (
    "arxiv.org",
    "openreview.net",
    "aclweb.org",
    "aclanthology.org",
    "neurips.cc",
    "paperswithcode.com",
    "scholar.google",
    "dl.acm.org",
    "ieeexplore.ieee.org",
)

# Common benchmark/dataset tokens to help the “vague claims” heuristic
# (Expanded to include ASR / speech datasets.)
_DATASET_TOKENS = (
    # NLP / CV staples
    "squad",
    "mnli",
    "sst-2",
    "sst2",
    "qqp",
    "qnli",
    "cola",
    "stsb",
    "mrpc",
    "imagenet",
    "cifar",
    "glue",
    "superglue",
    "snli",
    "msmarco",
    "wikitext",
    "lambada",
    "hellaswag",
    "mmlu",
    # ASR / speech
    "librispeech",
    "common voice",
    "cv",
    "ted-lium",
    "gigaspeech",
    "fleurs",
    "voxpopuli",
    "ljspeech",
    "wsj",
    "switchboard",
    "ami",
    "timit",
)

# Metric tokens + nearby number/percent → “vague but present” claim
# (Expanded to include WER/CER and wording variants.)
_METRIC_WORDS = (
    r"(accuracy|acc|f1|bleu|rouge|map|auc|perplexity|exact\s*match|em|mcc|pearson|spearman"
    r"|wer|word\s*error\s*rate|cer|character\s*error\s*rate)"
)
_NEAR_NUMBER = r"([0-9]+(\.[0-9]+)?\s*%?)"
_VAGUE_CLAIM_RE = re.compile(rf"{_METRIC_WORDS}[^.\n]{{0,60}}{_NEAR_NUMBER}", re.I)

# crude detectors for semi-structured evidence in README
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.M)  # markdown table rows
_HTML_TABLE_RE = re.compile(r"<\s*table\b", re.I)  # HTML tables


def _has_third_party_link(text: str, tags: Iterable[str]) -> bool:
    """Detect presence of recognizable third-party benchmark/paper domains."""
    hay = (text or "") + " " + " ".join(tags or [])
    low = hay.lower()
    return any(dom in low for dom in _THIRD_PARTY_DOMAINS)


def _any_dataset_token(text: str) -> bool:
    low = (text or "").lower()
    return any(tok in low for tok in _DATASET_TOKENS)


def _contains_vague_perf(text: str, tags: Iterable[str]) -> bool:
    """
    Consider there to be at least a vague performance claim if we see a metric word
    near a number (e.g., "accuracy 93%" or "WER 7.7%") OR dataset token + metric word.
    """
    hay = (text or "") + " " + " ".join(tags or [])
    return bool(_VAGUE_CLAIM_RE.search(hay)) or (
        _any_dataset_token(hay) and re.search(_METRIC_WORDS, hay, re.I) is not None
    )


def _count_structured_claims(card_data: Any) -> Tuple[int, int]:
    """
    Returns (n_results, n_metric_entries) from cardData across:
      1) 'model-index' (official HF structure)
      2) ad-hoc lists often seen on cards: 'eval_results' / 'metrics'
    A 'result' is counted when we have dataset info + >=1 metric having a name/type and a value.
    """
    n_results = 0
    n_metrics = 0
    if not isinstance(card_data, dict):
        return (0, 0)

    # 1) Official HF model-index
    mi = card_data.get("model-index")
    if isinstance(mi, list):
        for entry in mi:
            for res in (entry or {}).get("results", []) or []:
                dataset = (res or {}).get("dataset") or {}
                metrics = (res or {}).get("metrics") or []
                has_dataset = bool(dataset.get("name") or dataset.get("type"))
                if has_dataset and isinstance(metrics, list) and metrics:
                    good_metrics = 0
                    for m in metrics:
                        if not isinstance(m, dict):
                            continue
                        has_metric_name = bool(m.get("name") or m.get("type"))
                        has_value = m.get("value") is not None
                        if has_metric_name and has_value:
                            good_metrics += 1
                    if good_metrics > 0:
                        n_results += 1
                        n_metrics += good_metrics

    # 2) Ad-hoc lists
    for key in ("eval_results", "metrics"):
        vals = card_data.get(key)
        if isinstance(vals, list):
            for item in vals:
                if not isinstance(item, dict):
                    continue
                has_metric = bool(
                    item.get("metric") or item.get("name") or item.get("type")
                )
                has_value = item.get("value") is not None
                has_dataset = bool(
                    item.get("dataset")
                    or item.get("dataset_name")
                    or item.get("task_name")
                )
                if has_metric and has_value and has_dataset:
                    n_results += 1
                    n_metrics += 1

    return (n_results, n_metrics)


def _markdown_claims_strength(md: str) -> Tuple[bool, int]:
    """
    Heuristic: if the README has a markdown table OR an HTML table AND a metric-with-number nearby,
    treat it as semi-structured. Return (has_semi_structured, approx_rows).
    """
    if not md:
        return (False, 0)
    table_rows = _TABLE_ROW_RE.findall(
        md
    )  # count rows as a proxy for structure richness
    html_table = bool(_HTML_TABLE_RE.search(md))
    has_vague = bool(_VAGUE_CLAIM_RE.search(md))
    has_semi = (bool(table_rows) or html_table) and has_vague
    approx = (
        len(table_rows) if table_rows else (6 if html_table else 0)
    )  # assume modest structure for HTML table
    return (has_semi, approx)


# ------------ main ------------


def compute(model_url: str):
    t0 = time.perf_counter()
    score: float = 0.0
    try:
        # Normalize the HF URL to (repo_id, optional revision/branch)
        repo_id, rev = to_repo_id(model_url)

        # Fetch the model info (does NOT download large weights)
        info: Any = model_info(repo_id)
        card_data = getattr(info, "cardData", None) or {}
        tags = getattr(info, "tags", None) or []

        # Load markdown content robustly, handling revision safely
        md: str = ""
        path: str | None = None

        # Prefer README at explicit revision if available
        try:
            if rev:
                path = hf_hub_download(repo_id, filename="README.md", revision=rev)
        except Exception:
            path = None

        # Fallback to default branch README if rev not provided or previous step failed
        if path is None:
            try:
                path = hf_hub_download(repo_id, filename="README.md")
            except Exception:
                path = None

        if path:
            # Try to parse as a ModelCard first (gives us consistent .content)
            try:
                md = str(ModelCard.load(path).content)
            except Exception:
                # If parsing fails, read raw text
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        md = f.read()
                except Exception:
                    md = ""
        else:
            # Last resort: try loading the card by repo_id (no revision arg allowed here)
            try:
                md = str(ModelCard.load(repo_id).content)
            except Exception:
                md = ""

        # --- signals ---
        third_party = _has_third_party_link(md, tags)
        n_results, n_metrics = _count_structured_claims(card_data)
        has_structured = n_results > 0 and n_metrics > 0

        # If cardData lacks structure, fall back to README tables+metrics as "semi-structured"
        semi_structured, approx_rows = _markdown_claims_strength(md)

        vague = _contains_vague_perf(md, tags)

        # -------- Calibrated rubric (defensible & generalizable) --------
        # - Proper structured claims (dataset+metric+value) score high,
        #   with small bonuses for multiple results/metrics and third-party links.
        # - Semi-structured (README tables + metric tokens) score mid–high.
        # - Vague-only statements get a small floor.
        if has_structured:
            # Base credit for proper dataset+metric(+value)
            base = 0.74
            # Richness bonus: small bumps for multiple results/metrics (cap 0.12)
            richness_bonus = min(
                0.12, 0.04 * min(n_results, 3) + 0.02 * min(n_metrics, 5)
            )
            # Third-party corroboration (papers/proceedings/PWC/etc.)
            third_party_bonus = 0.06 if third_party else 0.0
            score = base + richness_bonus + third_party_bonus

        elif semi_structured:
            # README has a table + metric-with-number → treat as semi-structured
            base = 0.72
            # More rows → slightly more confidence (cap 0.12)
            table_bonus = min(0.12, 0.02 * min(approx_rows, 8))
            third_party_bonus = 0.04 if third_party else 0.0
            score = base + table_bonus + third_party_bonus

        elif vague:
            # Only vague/narrative claims → small floor
            score = 0.15

        else:
            score = 0.0

        # Clamp to [0,1]
        score = max(0.0, min(1.0, score))

    except Exception:
        # Be conservative; missing/outage shouldn't crash the whole run
        score = 0.0

    return {
        "value": float(score),
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


register(NAME, FIELD, compute)
