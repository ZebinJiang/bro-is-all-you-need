"""Reference-guided backend bakeoff CLI 表格测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REQUIRED_TABLES = {
    "action_family_schema_table",
    "backend_environment_table",
    "backend_io_table",
    "backend_latency_table",
    "backend_probe_matrix",
    "batch_balance_plan_table",
    "dataset_preview_table",
    "missing_telemetry_table",
    "reuse_license_table",
    "source_mix_plan_table",
}


def test_bakeoff_cli_emits_all_prompt_tables_as_csv_and_markdown(tmp_path: Path) -> None:
    """CLI 必须把 probe/mix/balance/schema/reuse 都写成表。"""
    output_dir = tmp_path / "out"
    command = [
        sys.executable,
        "-m",
        "autovla.dataloader.perf",
        "bakeoff",
        "--backend",
        "synthetic,raw_zjh,lerobot_local,webdataset_tar",
        "--input-root",
        str(tmp_path / "missing"),
        "--output-dir",
        str(output_dir),
        "--max-samples",
        "4",
        "--max-files",
        "8",
        "--max-bytes-read",
        "4096",
        "--table-format",
        "json,csv,md",
        "--allow-missing-input-root",
    ]

    completed = subprocess.run(command, check=False, text=True, capture_output=True)

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((output_dir / "backend_bakeoff_raw.json").read_text())
    assert set(payload["tables"]) >= REQUIRED_TABLES
    for table in REQUIRED_TABLES:
        assert (output_dir / f"{table}.csv").is_file()
        assert (output_dir / f"{table}.md").is_file()
    assert payload["tables"]["source_mix_plan_table"]["rows"]
    assert payload["tables"]["batch_balance_plan_table"]["rows"]
    assert payload["tables"]["action_family_schema_table"]["rows"]
