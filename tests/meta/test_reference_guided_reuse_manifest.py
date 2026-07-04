"""Reference-guided reuse manifest 治理测试。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REQUIRED_REFERENCES = {
    "dexbotic",
    "fluxvla",
    "isaac_groot",
    "lerobot",
    "openpi",
    "qwen_qwen_vl",
    "starvla",
    "vla_foundry",
    "webdataset",
}


def test_reference_reuse_manifest_records_no_copied_code() -> None:
    """复用 manifest 必须覆盖所有参考, 且本 tranche 不复制/改写上游代码。"""
    manifest = yaml.safe_load(Path("third_party/reuse_manifest.yaml").read_text())
    schema = json.loads(Path("third_party/reuse_manifest.schema.json").read_text())

    rows = manifest["references"]
    ids = {row["reference_id"] for row in rows}

    assert set(schema["required_reference_ids"]) == REQUIRED_REFERENCES
    assert ids >= REQUIRED_REFERENCES
    for row in rows:
        if row["reference_id"] in REQUIRED_REFERENCES:
            assert row["copied_code"] is False
            assert row["adapted_code"] is False
            assert row["dependency_added"] is False
            assert row["model_weights_used"] is False
            assert row["dataset_artifacts_used"] is False
            assert row["whole_repo_rejection_reason"]
