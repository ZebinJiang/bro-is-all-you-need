"""模型资产存储与解析配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from autovla.config.schema.base import BaseConfig, require_bool, require_schema_version


@dataclass(frozen=True, slots=True)
class ModelAssetStoreConfig:
    """描述唯一规范模型资产根;空值按受控优先级解析。"""

    root: str | None = "/home/cz-jzb/workspace/vla-flywheel/base_model"

    def __post_init__(self) -> None:
        """要求显式根为非空绝对路径文本。"""

        if self.root is not None:
            if not self.root.strip() or not self.root.startswith("/"):
                raise ValueError("assets.store.root must be an absolute path")


@dataclass(frozen=True, slots=True)
class AssetConfig(BaseConfig):
    """聚合模型资产 store 与严格本地校验策略。"""

    store: ModelAssetStoreConfig = field(default_factory=ModelAssetStoreConfig)
    verify_on_resolve: bool = True

    def __post_init__(self) -> None:
        """校验版本并禁止关闭训练前完整性验证。"""

        require_schema_version(self.schema_version, "assets.schema_version")
        if not isinstance(cast(object, self.store), ModelAssetStoreConfig):
            raise ValueError("assets.store must be a ModelAssetStoreConfig")
        require_bool(self.verify_on_resolve, "assets.verify_on_resolve")
        if not self.verify_on_resolve:
            raise ValueError("assets.verify_on_resolve must remain true")


__all__ = ["AssetConfig", "ModelAssetStoreConfig"]
