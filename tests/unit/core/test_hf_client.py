from swe_project.core import hf_client as hc


def test_model_info_calls_hfapi(monkeypatch):
    called = {}

    class FakeApi:
        def model_info(self, rid):
            called["rid"] = rid
            return {"ok": True, "rid": rid}

        def dataset_info(self, rid):
            raise AssertionError("dataset_info should not be called")

    monkeypatch.setattr(hc, "_api", FakeApi())

    out = hc.model_info("org/name")
    assert out == {"ok": True, "rid": "org/name"}
    assert called["rid"] == "org/name"


def test_dataset_info_calls_hfapi(monkeypatch):
    class FakeApi:
        def model_info(self, rid):
            raise AssertionError("model_info should not be called")

        def dataset_info(self, rid):
            return {"id": rid}

    monkeypatch.setattr(hc, "_api", FakeApi())

    out = hc.dataset_info("dataset/id")
    assert out == {"id": "dataset/id"}


def test_download_snapshot_passes_through(monkeypatch, tmp_path):
    captured = {}

    def fake_snapshot_download(*, repo_id, allow_patterns, local_dir_use_symlinks):
        captured["repo_id"] = repo_id
        captured["allow_patterns"] = allow_patterns
        captured["symlinks"] = local_dir_use_symlinks
        return tmp_path.as_posix()

    monkeypatch.setattr(hc, "snapshot_download", fake_snapshot_download)

    out = hc.download_snapshot("org/name", ["*.json", "*.md"])
    assert out == tmp_path.as_posix()
    assert captured["repo_id"] == "org/name"
    assert captured["allow_patterns"] == ["*.json", "*.md"]
    assert captured["symlinks"] is False
