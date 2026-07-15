"""AutoVLA 模型配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_non_empty_str,
    require_positive_int,
    require_schema_version,
    require_str_tuple,
)

_MODEL_VALIDATION_STATUSES = frozenset(
    {
        "runtime_unverified",
        "inventory_ready_compute_full_verification_required",
        "checkpoint_terms_and_cosmos_license_access_receipts_blocked",
        "checkpoint_gemma_terms_and_conversion_assets_blocked",
        "deferred_by_user_priority",
    }
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
    asset_key: str | None = None
    eagle_asset_path: str | None = None
    checkpoint_path: str | None = None
    optional_extra: str | None = None
    local_files_only: bool = True
    runtime_support: str | None = None
    lifecycle_state: str = "active"
    validation_status: str = "runtime_unverified"
    action_horizon: int | None = None
    action_dim: int | None = None
    max_state_dim: int | None = None
    max_action_dim: int | None = None
    asset_bundle_keys: tuple[str, ...] = ()

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
            "asset_key",
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
        if self.asset_key is not None and self.checkpoint_path is not None:
            raise ValueError(
                "model.asset_key and legacy model.checkpoint_path are mutually exclusive"
            )
        if self.runtime_support is not None:
            require_non_empty_str(self.runtime_support, "model.runtime_support")
            if self.runtime_support not in {
                "executable",
                "architecture_defined_runtime_deferred",
                "asset_required",
                "optional_dependency_required",
                "unsupported",
            }:
                raise ValueError("model.runtime_support is not canonical")
        require_non_empty_str(self.lifecycle_state, "model.lifecycle_state")
        if self.lifecycle_state not in {"active", "DEFERRED_BY_USER_PRIORITY"}:
            raise ValueError("model.lifecycle_state is not canonical")
        require_non_empty_str(self.validation_status, "model.validation_status")
        if self.validation_status not in _MODEL_VALIDATION_STATUSES:
            raise ValueError("model.validation_status is not canonical")
        if self.lifecycle_state == "DEFERRED_BY_USER_PRIORITY" and self.runtime_support != (
            "architecture_defined_runtime_deferred"
        ):
            raise ValueError("deferred model families must remain runtime deferred")
        for name in ("action_horizon", "action_dim", "max_state_dim", "max_action_dim"):
            value = getattr(self, name)
            if value is not None:
                require_positive_int(value, f"model.{name}")
        if self.asset_bundle_keys:
            require_str_tuple(self.asset_bundle_keys, "model.asset_bundle_keys")
