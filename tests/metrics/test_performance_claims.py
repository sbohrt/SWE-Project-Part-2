from __future__ import annotations

from types import SimpleNamespace

import pytest

from swe_project.metrics import performance_claims as pc


def _fake_info(card_data=None, tags=None):
    return SimpleNamespace(cardData=(card_data or {}), tags=(tags or []))


# ------------------- structured model-index + third-party link -------------------
def test_structured_claims_with_third_party_tag(monkeypatch):
    card_data = {
        "model-index": [
            {
                "results": [
                    {
                        "dataset": {"name": "glue"},
                        "metrics": [{"name": "accuracy", "value": 0.9}],
                    }
                ]
            },
            {
                "results": [
                    {
                        "dataset": {"type": "sst2"},
                        "metrics": [
                            {"type": "f1", "value": 0.88},
                            {"name": "exact match", "value": 0.75},
                        ],
                    }
                ]
            },
        ]
    }
    info = _fake_info(card_data, tags=["https://arxiv.org/abs/1234.5678"])
    monkeypatch.setattr(pc, "model_info", lambda rid: info)
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)
    out = pc.compute("https://huggingface.co/org/name")
    assert 0.90 <= out["value"] <= 1.0


# ------------------- semi-structured markdown table (kept as stub to avoid dup) -------------------
def test_semi_structured_markdown_table(monkeypatch, tmp_path):
    pass


def _mock_hf_card(monkeypatch, tmp_path, md: str) -> None:
    monkeypatch.setattr(pc, "_HF_AVAILABLE", True)
    fake_path = tmp_path / "README.md"
    fake_path.write_text(md, encoding="utf-8")
    monkeypatch.setattr(pc, "hf_hub_download", lambda *a, **k: str(fake_path))

    class FakeCard:
        @staticmethod
        def load(path):
            return SimpleNamespace(content=md)

    monkeypatch.setattr(pc, "ModelCard", FakeCard)
    monkeypatch.setattr(pc, "model_info", lambda rid: _fake_info({}, []))


@pytest.mark.parametrize(
    "md, mode, lo, hi, exact",
    [
        (
            "| dataset | metric   | score |\n| ------- | -------- | ----- |\n| GLUE    | accuracy | 91%   |\n",
            "range",
            0.75,
            0.90,
            None,
        ),
        ("We achieved F1 0.88 on internal benchmark.", "exact", None, None, 0.15),
    ],
)
def test_markdown_claims_param(monkeypatch, tmp_path, md, mode, lo, hi, exact):
    _mock_hf_card(monkeypatch, tmp_path, md)
    out = pc.compute("https://huggingface.co/org/name")
    if mode == "range":
        assert lo <= out["value"] <= hi
    else:
        assert out["value"] == exact


# ------------------- no claims anywhere -------------------
def test_no_claims_returns_zero(monkeypatch):
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)
    monkeypatch.setattr(pc, "model_info", lambda rid: _fake_info({}, []))
    out = pc.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0


# ------------------- exception safety -------------------
def test_exception_safety(monkeypatch):
    monkeypatch.setattr(
        pc, "model_info", lambda rid: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)
    out = pc.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0
