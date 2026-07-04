"""开源复用和 license ledger 测试。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_reuse_manifest_should_record_required_reference_families() -> None:
    """验证 DataBackend bakeoff 发布复用/license 决策 ledger。"""
    manifest_path = ROOT / "third_party" / "reuse_manifest.yaml"
    schema_path = ROOT / "third_party" / "reuse_manifest.schema.json"
    plan_path = ROOT / "docs" / "architecture" / "OPEN_SOURCE_REUSE_AND_LICENSE_PLAN.md"
    ledger_path = ROOT / "docs" / "architecture" / "REFERENCE_INTAKE_LEDGER.md"
    foundation_path = ROOT / "docs" / "architecture" / "DATABACKEND_BAKEOFF_FOUNDATION.md"

    assert manifest_path.is_file()
    assert schema_path.is_file()
    assert plan_path.is_file()
    assert ledger_path.is_file()
    assert foundation_path.is_file()

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    reference_ids = {entry["id"] for entry in manifest["references"]}

    assert schema["title"] == "AutoVLA reuse manifest"
    assert {
        "dexbotic",
        "fluxvla",
        "isaac_gr00t",
        "lerobot",
        "openpi_pi_family",
        "qwen_qwen_vl",
        "starvla",
        "vla_foundry",
        "webdataset",
    } <= reference_ids
    assert all(
        entry["reuse_mode"] in {"inspiration", "native_probe"} for entry in manifest["references"]
    )
    assert "No upstream code copied" in plan_path.read_text(encoding="utf-8")
