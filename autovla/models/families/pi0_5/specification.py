"""Pi0.5 specification-only 模型族。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.families.specification import ModelFamilySpec


@dataclass(frozen=True, slots=True)
class Pi0_5ModelSpec(ModelFamilySpec):
    """描述未来 Pi0.5 适配边界,不导入或声明 OpenPI runtime。"""


PI0_5_SPEC = Pi0_5ModelSpec(
    family_key="pi0_5",
    display_name="Pi0.5",
    factory_path=None,
    optional_extra=None,
    runtime_supported=False,
    local_files_only=True,
    action_horizon=None,
    max_state_dim=None,
    max_action_dim=None,
    supported_precisions=("bfloat16",),
    capabilities=(
        "processor_contract",
        "flow_action_contract",
        "checkpoint_adapter_contract",
        "web_conditioning_specification",
    ),
    source_status="specification_only",
    validation_status="runtime_not_implemented",
)

__all__ = ["PI0_5_SPEC", "Pi0_5ModelSpec"]
