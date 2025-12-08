from __future__ import annotations

from pathlib import Path

from swe_project.metrics import (
    ramp_up_time as rt,  # import the module so we can monkeypatch its *local* imports
)


def _write_readme(dirpath: Path, text: str = "# Title\n\nHello"):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "README.md").write_text(text, encoding="utf-8")
    return dirpath / "README.md"


# ---------- Local absolute path branch ----------


def test_local_repo_with_readme_plain_float(monkeypatch, tmp_path):
    repo = tmp_path / "local_model"
    _write_readme(repo, "README\n\ncontents")
    # patch the LLM call used inside this module
    monkeypatch.setattr(rt, "ask_llm", lambda *a, **k: "0.85")
    out = rt.compute(repo.as_posix())
    assert 0.84 <= out["value"] <= 0.86
    assert isinstance(out["latency_ms"], int) and out["latency_ms"] >= 0


def test_local_repo_with_readme_embedded_number(monkeypatch, tmp_path):
    repo = tmp_path / "local2"
    _write_readme(repo, "Some text that is long enough to call the LLM.")
    # LLM returns chatter; code should regex-extract the number
    monkeypatch.setattr(rt, "ask_llm", lambda *a, **k: "score: 0.73 ✅")
    out = rt.compute(repo.as_posix())
    assert 0.72 <= out["value"] <= 0.74


def test_local_repo_with_readme_garbage_reply(monkeypatch, tmp_path):
    repo = tmp_path / "local3"
    _write_readme(repo, "Content")
    monkeypatch.setattr(rt, "ask_llm", lambda *a, **k: "N/A")
    out = rt.compute(repo.as_posix())
    assert out["value"] == 0.0


def test_local_repo_missing_readme_returns_zero(tmp_path):
    repo = tmp_path / "no_readme"
    repo.mkdir(parents=True, exist_ok=True)
    out = rt.compute(repo.as_posix())
    assert out["value"] == 0.0


# ---------- Hugging Face URL branch (snapshot path) ----------


def test_hf_url_uses_download_snapshot_and_clamps_high(monkeypatch, tmp_path):
    # Make a fake local dir returned by download_snapshot with a README inside
    fake_dir = tmp_path / "snap"
    _write_readme(fake_dir, "Docs go here")
    # patch the symbol imported in this module
    monkeypatch.setattr(
        rt, "download_snapshot", lambda repo_id, allow_patterns: fake_dir.as_posix()
    )
    # LLM returns >1.0; result must be clamped to 1.0
    monkeypatch.setattr(rt, "ask_llm", lambda *a, **k: "1.23")

    out = rt.compute("https://huggingface.co/org/name")
    assert out["value"] == 1.0


def test_hf_url_clamps_negative(monkeypatch, tmp_path):
    fake_dir = tmp_path / "snap2"
    _write_readme(fake_dir, "Docs go here")
    monkeypatch.setattr(
        rt, "download_snapshot", lambda repo_id, allow_patterns: fake_dir.as_posix()
    )
    monkeypatch.setattr(rt, "ask_llm", lambda *a, **k: "-0.2")

    out = rt.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0
