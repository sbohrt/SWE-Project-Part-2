import subprocess
import json
import pathlib
import tempfile
import os

SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")

def run(*args, env=None):
    env_vars = os.environ.copy()
    env_vars["PYTHONPATH"] = SRC  # <-- key line
    if env:
        env_vars.update(env)
    return subprocess.run(
        ["python", "-m", "swe_project.cli", *args],
        text=True, capture_output=True, env=env_vars,
    )

def test_invalid_command_exits_1():
    r = run("nope")
    assert r.returncode in (1, 2)      # accept Typer's 2
    assert (r.stdout + r.stderr) != ""

def test_install_command_exists():
    r = run("install")
    # May fail for now, but subcommand should exist
    assert r.returncode in (0, 1)

def test_score_outputs_ndjson():
    with tempfile.TemporaryDirectory() as d:
        url_file = pathlib.Path(d, "urls.txt")
        url_file.write_text("https://huggingface.co/dummy\n")
        r = run("score", str(url_file))
        assert r.returncode == 0
        line = r.stdout.strip().splitlines()[0]
        obj = json.loads(line)
        assert "name" in obj and "net_score" in obj
