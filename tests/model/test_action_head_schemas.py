"""Action-head schema substrate 测试。"""

from __future__ import annotations

from autovla.models.action_heads import (
    ActionHeadKind,
    ContinuousActionChunkSpec,
    DiscreteActionTokenSpec,
    FlowMatchingActionHeadSpec,
    NormalizationPolicySpec,
)
from autovla.models.embodiment import ActionFieldSpec, CameraViewSpec, EmbodimentSpec


def test_action_head_specs_serialize_without_runtime_claims() -> None:
    """Action schema 行必须是 metadata-only, 不声称 runtime 可用。"""
    flow = FlowMatchingActionHeadSpec(
        name="pi0-roadmap-flow",
        output=ContinuousActionChunkSpec(action_horizon=16, action_dim=7),
        normalization=NormalizationPolicySpec(policy="roadmap_metadata_only"),
    )
    token = DiscreteActionTokenSpec(vocab_size=1024, token_horizon=32)

    assert ActionHeadKind.FLOW_MATCHING_CONTINUOUS.value == "flow_matching_continuous_action"
    assert flow.to_table_row()["runtime_status"] == "runtime_not_loaded"
    assert token.to_table_row()["action_kind"] == "autoregressive_discrete_action_token"


def test_embodiment_spec_is_table_shaped() -> None:
    """Embodiment metadata 提供相机和 action 字段, 不绑定真实机器人。"""
    spec = EmbodimentSpec(
        embodiment_key="so100-metadata",
        display_name="SO100 metadata only",
        cameras=(CameraViewSpec(name="front", modality="rgb", resolution="metadata_only"),),
        actions=(ActionFieldSpec(name="arm", action_dim=7, units="normalized"),),
        tags=("metadata_only",),
    )

    assert spec.to_table_row()["camera_count"] == 1
    assert spec.to_table_row()["action_dim"] == 7
