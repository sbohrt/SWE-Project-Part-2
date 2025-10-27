from __future__ import annotations

from types import SimpleNamespace
from swe_project.metrics import license as lic

# ---------- normalize_license ----------


def test_normalize_license_known_good():
    score, key = lic.normalize_license("MIT")
    assert score == 1.0
    assert key == "mit"


def test_normalize_license_known_bad():
    score, key = lic.normalize_license("gpl-3.0")
    assert score == 0.0
    assert key == "gpl-3.0"


def test_normalize_license_unknown_or_custom():
    score, key = lic.normalize_license("weird-license-x")
    assert score == 0.5
    assert key == "weird-license-x"


def test_normalize_license_none():
    score, key = lic.normalize_license(None)
    assert score == 0.0
    assert key == "None"


# ---------- compute (metadata path) ----------


def test_compute_metadata_good_license(monkeypatch):
    monkeypatch.setattr(
        lic, "model_info", lambda rid: SimpleNamespace(license="apache-2.0")
    )
    monkeypatch.setattr(
        lic, "download_snapshot", lambda rid, allow_patterns=None: "/tmp"
    )  # not used
    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 1.0


def test_compute_metadata_bad_license(monkeypatch):
    monkeypatch.setattr(
        lic, "model_info", lambda rid: SimpleNamespace(license="proprietary")
    )
    monkeypatch.setattr(
        lic, "download_snapshot", lambda rid, allow_patterns=None: "/tmp"
    )
    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0


def test_compute_metadata_unclear_triggers_readme(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lic, "model_info", lambda rid: SimpleNamespace(license="custom-x")
    )
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    # Change this line:
    (repo_dir / "README.md").write_text("License: MIT", encoding="utf-8")
    monkeypatch.setattr(
        lic, "download_snapshot", lambda rid, allow_patterns=None: repo_dir.as_posix()
    )

    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 1.0


# ---------- compute (fallback to README) ----------


def test_compute_no_metadata_license_reads_readme(monkeypatch, tmp_path):
    monkeypatch.setattr(lic, "model_info", lambda rid: SimpleNamespace(license=None))
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("License: GPL-3.0", encoding="utf-8")
    monkeypatch.setattr(
        lic, "download_snapshot", lambda rid, allow_patterns=None: repo_dir.as_posix()
    )

    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0  # GPL → incompatible


def test_compute_no_license_anywhere(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lic, "model_info", lambda rid: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    repo_dir = tmp_path / "repo3"
    repo_dir.mkdir()
    # Change this line (avoid the word 'license' entirely):
    (repo_dir / "README.md").write_text(
        "This readme lacks any licensing info.", encoding="utf-8"
    )
    monkeypatch.setattr(
        lic, "download_snapshot", lambda rid, allow_patterns=None: repo_dir.as_posix()
    )

    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0


def test_compute_readme_exception_ignored(monkeypatch):
    monkeypatch.setattr(lic, "model_info", lambda rid: SimpleNamespace(license=None))
    # simulate download_snapshot raising
    monkeypatch.setattr(
        lic,
        "download_snapshot",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fail")),
    )

    out = lic.compute("https://huggingface.co/org/name")
    assert out["value"] == 0.0  # fallback safe
