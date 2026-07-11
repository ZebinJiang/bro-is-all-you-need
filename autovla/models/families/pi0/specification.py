"""Pi0 specification-only 模型族。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.families.specification import ModelFamilySpec


@dataclass(frozen=True, slots=True)
class Pi0ModelSpec(ModelFamilySpec):
    """描述未来 Pi0 适配边界,不声明 OpenPI runtime 支持。"""


PI0_SPEC = Pi0ModelSpec(
    family_key="pi0",
    display_name="Pi0",
    factory_path=None,
    optional_extra=None,
    runtime_supported=False,
    local_files_only=True,
    action_horizon=None,
    max_state_dim=None,
    max_action_dim=None,
    supported_precisions=("bfloat16",),
    capabilities=("processor_contract", "flow_action_contract", "checkpoint_adapter_contract"),
    source_status="specification_only",
    validation_status="runtime_not_implemented",
)

__all__ = ["PI0_SPEC", "Pi0ModelSpec"]
