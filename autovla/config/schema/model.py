"""AutoVLA 模型配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_non_empty_str,
    require_schema_version,
)


@dataclass(frozen=True, slots=True)
class ModelConfig(BaseConfig):
    """描述模型身份与注册键,不负责实例化模型。

    Args:
        schema_version: 模型配置段版本。M1 仅接受 ``"1.0"``。
        name: 人类可读模型名称,不能为空。
        registry_key: 后续注册表查找使用的模型键,不能为空。
    """

    name: str = "unconfigured-model"
    registry_key: str = "unconfigured-model"
    architecture_variant: str | None = None
    processor_key: str | None = None
    eagle_asset_path: str | None = None
    checkpoint_path: str | None = None
    optional_extra: str | None = None
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """校验模型配置构造器不变量。"""
        require_schema_version(self.schema_version, "model.schema_version")
        require_non_empty_str(self.name, "model.name")
        require_non_empty_str(self.registry_key, "model.registry_key")
        if self.architecture_variant is not None:
            require_non_empty_str(self.architecture_variant, "model.architecture_variant")
            if self.architecture_variant not in {"official_n1d6", "reduced_runtime"}:
                raise ValueError(
                    "model.architecture_variant must be official_n1d6 or reduced_runtime"
                )
        for field_name in (
            "processor_key",
            "eagle_asset_path",
            "checkpoint_path",
            "optional_extra",
        ):
            value = getattr(self, field_name)
            if value is not None:
                require_non_empty_str(value, f"model.{field_name}")
        require_bool(self.local_files_only, "model.local_files_only")
        if not self.local_files_only:
            raise ValueError("model.local_files_only must remain true")
