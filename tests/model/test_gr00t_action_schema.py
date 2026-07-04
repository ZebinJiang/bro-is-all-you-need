"""GR00T action schema metadata-only 测试。"""

from __future__ import annotations

import sys

from autovla.models.gr00t.action_schema import build_gr00t_action_schema


def test_gr00t_action_schema_reads_modality_metadata_without_runtime_import() -> None:
    """GR00T schema 只表达 metadata/local-schema, 不导入 GR00T runtime。"""
    before = set(sys.modules)

    schema = build_gr00t_action_schema(
        action_horizon=16,
        action_dim=7,
        modality_fields=("language", "image", "state"),
        embodiment_tags=("so100",),
    )

    assert schema.family_key == "gr00t-roadmap"
    assert schema.status == ("metadata_only", "local_schema_probe_only", "runtime_not_loaded")
    assert schema.to_table_row()["action_kind"] == "diffusion_continuous_action"
    assert "gr00t" not in (set(sys.modules) - before)
