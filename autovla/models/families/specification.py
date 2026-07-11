"""依赖轻量的模型族静态规范。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelFamilySpec:
    """描述可列举但不触发运行时导入的模型族。"""

    family_key: str
    display_name: str
    factory_path: str | None
    optional_extra: str | None
    runtime_supported: bool
    local_files_only: bool
    action_horizon: int | None
    max_state_dim: int | None
    max_action_dim: int | None
    supported_precisions: tuple[str, ...]
    capabilities: tuple[str, ...]
    source_status: str
    validation_status: str

    def __post_init__(self) -> None:
        """校验规范字段与 runtime 声明一致。"""
        if not self.family_key.strip() or not self.display_name.strip():
            raise ValueError("model family key and display name must not be empty")
        if self.runtime_supported and (self.factory_path is None or self.optional_extra is None):
            raise ValueError("runtime-supported family requires factory_path and optional_extra")
        if not self.capabilities or not self.supported_precisions:
            raise ValueError("model family capabilities and precision list must not be empty")


__all__ = ["ModelFamilySpec"]
