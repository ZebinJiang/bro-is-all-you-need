"""RoboDM-style 候选 manifest helper。"""

from __future__ import annotations

from collections.abc import Mapping


def build_robodm_manifest(*, sample_count: int, samples_per_container: int) -> Mapping[str, object]:
    """构造 RoboDM-style prototype manifest。"""
    return {
        "candidate_id": "zjh_robodm_container_v1",
        "dependency_mode": "autovla_owned_prototype_no_upstream_package",
        "prototype_only": True,
        "sample_count": sample_count,
        "samples_per_container": samples_per_container,
        "status": "PASS",
    }
