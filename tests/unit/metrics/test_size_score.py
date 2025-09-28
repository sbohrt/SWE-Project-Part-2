from __future__ import annotations

import math
from types import SimpleNamespace

from swe_project.metrics import size_score as ss

# ---------- helpers: pure behavior ----------


def test_clamp01_edges():
    assert ss._clamp01(-1.0) == 0.0
    assert ss._clamp01(0.0) == 0.0
    assert ss._clamp01(1.0) == 1.0
    assert ss._clamp01(2.5) == 1.0


def test_scores_from_size_rounding_and_clamp():
    # 0 MB => full 1.0 everywhere
    s0 = ss._scores_from_size(0.0)
    assert all(v == 1.0 for v in s0.values())

    # Way over capacity => 0.0 everywhere
    s_hi = ss._scores_from_size(20000.0)
    assert all(v == 0.0 for v in s_hi.values())

    # Mid value for raspberry_pi: cap=500 MB -> 250 MB => 0.5 (rounded to 2 decimals)
    s_mid = ss._scores_from_size(250.0)
    assert math.isclose(s_mid["raspberry_pi"], 0.5, rel_tol=0, abs_tol=1e-9)
    # Check it's rounded to 2 decimals for another device
    # e.g., 250/8000 = 0.03125 -> 1 - that = 0.96875 -> rounded 0.97
    assert s_mid["desktop_pc"] == 0.97


# ---------- _sum_weight_megabytes: counting files ----------


def test_sum_weight_megabytes_counts_supported_exts(monkeypatch):
    files = [
        SimpleNamespace(rfilename="model.safetensors", size=100_000_000),  # 100 MB
        SimpleNamespace(rfilename="weights.bin", size=400_000_000),  # 400 MB
        SimpleNamespace(rfilename="README.md", size=5_000),  # ignored
    ]
    info = SimpleNamespace(siblings=files, siblings_with_metadata=None)
    monkeypatch.setattr(ss, "model_info", lambda repo_id, revision=None: info)

    total = ss._sum_weight_megabytes("org/name", revision=None)
    assert math.isclose(total, 500.0, rel_tol=0, abs_tol=1e-6)  # MB


def test_sum_weight_megabytes_accepts_alt_field_names(monkeypatch):
    # use `siblings_with_metadata` and `path` field instead of rfilename
    files = [
        SimpleNamespace(path="pytorch_model.bin", size=1_500_000_000),  # 1500 MB
        SimpleNamespace(path="something.tflite", size=10_000_000),  # +10 MB
    ]
    info = SimpleNamespace(siblings=None, siblings_with_metadata=files)
    monkeypatch.setattr(ss, "model_info", lambda repo_id, revision=None: info)

    total = ss._sum_weight_megabytes("org/name", revision="main")
    assert math.isclose(total, 1510.0, rel_tol=0, abs_tol=1e-6)


def test_sum_weight_megabytes_handles_exception(monkeypatch):
    monkeypatch.setattr(
        ss, "model_info", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    total = ss._sum_weight_megabytes("org/name", revision=None)
    assert total == 0.0


# ---------- compute(): public contract ----------


def test_compute_happy_path(monkeypatch):
    # avoid parsing; force known repo_id/revision and size
    monkeypatch.setattr(ss, "to_repo_id", lambda url: ("org/name", "rev"))
    monkeypatch.setattr(
        ss, "_sum_weight_megabytes", lambda rid, rev: 1000.0
    )  # 1000 MB total

    out = ss.compute("https://huggingface.co/org/name")
    assert set(out["value"].keys()) == {
        "raspberry_pi",
        "jetson_nano",
        "desktop_pc",
        "aws_server",
    }
    # 1000/500 -> 0; 1000/1500 -> 1 - 0.666.. ~ 0.33 -> rounded 0.33
    assert out["value"]["raspberry_pi"] == 0.0
    assert out["value"]["jetson_nano"] == 0.33
    assert out["value"]["desktop_pc"] == 0.88  # 1 - 1000/8000 = 0.875 -> 0.88
    assert out["value"]["aws_server"] == 0.94  # 1 - 1000/16000 = 0.9375 -> 0.94
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0


def test_compute_exception_fallback(monkeypatch):
    # Force an exception before size computation
    def boom(url):  # signature matches to_repo_id(url)
        raise RuntimeError("parse fail")

    monkeypatch.setattr(ss, "to_repo_id", boom)

    out = ss.compute("bad://url")
    assert out["value"] == {
        "raspberry_pi": 0.0,
        "jetson_nano": 0.0,
        "desktop_pc": 0.0,
        "aws_server": 0.0,
    }
    assert isinstance(out["latency_ms"], int)
