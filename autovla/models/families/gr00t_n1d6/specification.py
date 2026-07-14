"""GR00T N1.6.1 依赖轻量规范。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.families.specification import ModelFamilySpec


@dataclass(frozen=True, slots=True)
class Gr00tN1d6ModelSpec(ModelFamilySpec):
    """标记 pinned 源码实现完成且 runtime validation 延后。"""


GR00T_N1D6_SPEC = Gr00tN1d6ModelSpec(
    family_key="gr00t_n1d6",
    display_name="NVIDIA Isaac-GR00T N1.6.1",
    factory_path="autovla.models.families.gr00t_n1d6.factory:Gr00tN1d6ModelFactory",
    optional_extra="model-gr00t-n1d6",
    runtime_supported=True,
    local_files_only=True,
    action_horizon=50,
    max_state_dim=128,
    max_action_dim=128,
    supported_precisions=("bfloat16", "float32"),
    capabilities=(
        "camera_language_state_conditioning",
        "multi_embodiment",
        "masked_flow_matching",
        "local_checkpoint_conversion",
        "registered_immutable_model_asset",
        "four_step_euler_sampling",
    ),
    source_status="source_implementation_complete",
    validation_status="runtime_validation_deferred",
)

__all__ = ["GR00T_N1D6_SPEC", "Gr00tN1d6ModelSpec"]
