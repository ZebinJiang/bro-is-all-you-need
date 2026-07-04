"""OpenPI / π action schema metadata-only 测试。"""

from __future__ import annotations

import sys

from autovla.models.pi.action_schema import build_pi_action_schema_table


def test_pi_action_schema_table_is_roadmap_only_and_import_safe() -> None:
    """π family schema 不导入 openpi/JAX/Flax, 只发布 roadmap rows。"""
    before = set(sys.modules)

    rows = build_pi_action_schema_table()

    assert [row["family_key"] for row in rows] == [
        "pi0-roadmap",
        "pi0-fast-roadmap",
        "pi05-roadmap",
    ]
    assert rows[0]["action_kind"] == "flow_matching_continuous_action"
    assert rows[1]["action_kind"] == "autoregressive_discrete_action_token"
    assert rows[2]["normalization_policy"] == "roadmap_metadata_only"
    assert not ((set(sys.modules) - before) & {"openpi", "jax", "flax"})
