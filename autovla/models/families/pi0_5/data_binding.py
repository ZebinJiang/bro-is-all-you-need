# ruff: noqa: RUF002
"""Pi0.5 对共享 DatasetModelBinding 的家族输入 schema 投影。"""

from __future__ import annotations

from autovla.data.binding.contracts import ModelInputSchema, PhysicalFeatureSpec
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.source_map import OPENPI_REVISION


def build_pi05_model_input_schema(
    config: Pi05Config,
    *,
    embodiment_id: str,
    state_features: tuple[PhysicalFeatureSpec, ...],
    action_features: tuple[PhysicalFeatureSpec, ...],
    sample_rate_hz: float,
    normalization_stats_fingerprint: str,
    action_mode: str,
) -> ModelInputSchema:
    """用显式物理语义构造 Pi0.5 输入 schema。

    本函数不猜测 state/action 单位、坐标系、机器人身份或统计量。调用方必须
    从 dataset binding 收据提供这些值；未知语义将由共享兼容性判定失败关闭。
    """

    return ModelInputSchema(
        family_id=config.family_key,
        version="openpi-pi0.5",
        source_pin=OPENPI_REVISION,
        embodiment_id=embodiment_id,
        projector_id="pi0_5_explicit_physical_projection",
        camera_names=("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb"),
        language_semantics="natural_language_task_instruction_with_discrete_state_tokens",
        state_features=state_features,
        action_features=action_features,
        state_dimension=config.state_dimension,
        action_dimension=config.action_dimension,
        sample_rate_hz=sample_rate_hz,
        history=1,
        horizon=config.action_horizon,
        action_mode=action_mode,
        normalization_axes=(0,),
        normalization_stats_fingerprint=normalization_stats_fingerprint,
        padding_policy="right_zero_padding_with_strict_state_action_and_camera_masks",
        mask_fields=("camera_mask", "state_mask", "action_mask", "temporal_mask"),
    )


__all__ = ["build_pi05_model_input_schema"]
