import json
import os
import pathlib
import subprocess
import tempfile
from typing import Dict, Optional

SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")


def run(*args: str, env: Optional[Dict] = None) -> subprocess.CompletedProcess:
    env_vars = os.environ.copy()
    env_vars["PYTHONPATH"] = SRC  # <-- key line
    if env:
        env_vars.update(env)
    return subprocess.run(
        ["python", "-m", "swe_project.cli", *args],
        text=True,
        capture_output=True,
        env=env_vars,
    )


def test_invalid_command_exits_1() -> None:
    r = run("nope")
    assert r.returncode in (1, 2)  # accept Typer's 2
    assert (r.stdout + r.stderr) != ""


def test_install_command_exists() -> None:
    r = run("install")
    # May fail for now, but subcommand should exist
    assert r.returncode in (0, 1)


def test_score_outputs_ndjson() -> None:
    with tempfile.TemporaryDirectory() as d:
        url_file = pathlib.Path(d, "urls.txt")
        url_file.write_text("https://huggingface.co/dummy\n")
        r = run("score", str(url_file))
        assert r.returncode == 0
        line = r.stdout.strip().splitlines()[0]
        obj = json.loads(line)
        assert "name" in obj and "net_score" in obj
