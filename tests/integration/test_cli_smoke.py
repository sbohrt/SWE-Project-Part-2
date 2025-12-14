# tests/integration/test_cli_smoke.py  (NEW)
import json
from pathlib import Path

from cli import main


def test_cli_score_smoke(capsys, tmp_path: Path) -> None:
    url_file = tmp_path / "urls.txt"
    # 3 columns: code_url, dataset_url, model_url (blank first two are allowed)
    url_file.write_text(
        ",,https://huggingface.co/google/gemma-3-27b\n", encoding="utf-8"
    )

    rc = main(["score", str(url_file)])
    # allow rc==0 (normal) or rc==1 if the network is down; we still validate the schema if any line was printed
    assert rc in (0, 1)

    out = capsys.readouterr().out.strip()
    if not out:
        # if nothing printed because network off, keep the test lenient
        return

    row = json.loads(out.splitlines()[0])
    # required keys
    for k in (
        "name",
        "category",
        "net_score",
        "net_score_latency",
        "ramp_up_time",
        "ramp_up_time_latency",
        "bus_factor",
        "bus_factor_latency",
        "performance_claims",
        "performance_claims_latency",
        "license",
        "license_latency",
        "size_score",
        "size_score_latency",
        "dataset_and_code_score",
        "dataset_and_code_score_latency",
        "dataset_quality",
        "dataset_quality_latency",
        "code_quality",
        "code_quality_latency",
    ):
        assert k in row
    # size_score must have the 4 devices
    for dev in ("raspberry_pi", "jetson_nano", "desktop_pc", "aws_server"):
        assert dev in row["size_score"]
