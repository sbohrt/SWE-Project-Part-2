from __future__ import annotations

from types import SimpleNamespace

from swe_project.metrics import performance_claims as pc


def _fake_info(card_data=None, tags=None):
    return SimpleNamespace(cardData=(card_data or {}), tags=(tags or []))


# ------------------- structured model-index + third-party link -------------------


def test_structured_claims_with_third_party_tag(monkeypatch):
    # Two results with three metrics total; should hit structured branch.
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
    # Add a third-party domain in tags to trigger bonus
    info = _fake_info(card_data, tags=["https://arxiv.org/abs/1234.5678"])
    monkeypatch.setattr(pc, "model_info", lambda rid: info)

    # Ensure README stays empty (no need for HF libs here)
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)

    out = pc.compute("https://huggingface.co/org/name")
    # base 0.74 + richness (min 0.12) + third-party 0.06 = 0.92
    assert 0.90 <= out["value"] <= 1.0


# ------------------- semi-structured markdown table -------------------


def test_semi_structured_markdown_table(monkeypatch, tmp_path):
    # README with a markdown table and metric+number nearby
    md = """
| dataset | metric   | score |
| ------- | -------- | ----- |
| GLUE    | accuracy | 91%   |
"""
    # Stub HF availability and return a fake path; we mock ModelCard.load to return content.
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

    out = pc.compute("https://huggingface.co/org/name")
    # semi-structured base ~0.72 + table bonus -> usually 0.76–0.90 depending on rows
    assert 0.75 <= out["value"] <= 0.90


# ------------------- vague claim only -------------------


def test_vague_claim_only(monkeypatch, tmp_path):
    md = "We achieved F1 0.88 on internal benchmark."
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

    out = pc.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.15  # vague branch exact score


# ------------------- no claims anywhere -------------------


def test_no_claims_returns_zero(monkeypatch):
    # No HF libs -> md empty; no tags; empty cardData
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)
    monkeypatch.setattr(pc, "model_info", lambda rid: _fake_info({}, []))

    out = pc.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0


# ------------------- exception safety -------------------


def test_exception_safety(monkeypatch):
    # Make model_info blow up → compute should recover to 0.0, not crash
    monkeypatch.setattr(
        pc, "model_info", lambda rid: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    # Avoid README branch entirely
    monkeypatch.setattr(pc, "_HF_AVAILABLE", False)

    out = pc.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0
