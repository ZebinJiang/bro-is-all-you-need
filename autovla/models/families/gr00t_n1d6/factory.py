"""GR00T N1.6.1 本地模型工厂。"""

from __future__ import annotations

import importlib.util
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from autovla.assets import (
    GR00T_N1D6_ASSET_SPEC,
    MissingModelAssetError,
    ModelAssetStore,
)
from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.families.gr00t_n1d6.checkpoint import (
    Gr00tN1d6CheckpointAdapter,
    UpstreamCheckpointLayout,
)
from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
from autovla.models.families.gr00t_n1d6.errors import (
    LocalModelAssetError,
    UnresolvedEagleAssetError,
    UnsupportedOfficialRelativeStatisticsError,
)
from autovla.models.families.gr00t_n1d6.model import Gr00tN1d6Model
from autovla.models.families.gr00t_n1d6.processor import Gr00tN1d6Processor
from autovla.models.outputs import CheckpointLoadReport


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Components:
    """返回同一配置构造的模型、处理器和可选加载证据。"""

    model: Gr00tN1d6Model
    processor: Gr00tN1d6Processor
    checkpoint_report: CheckpointLoadReport | None
    base_asset_manifest: Mapping[str, object] | None = None
    upstream_layout: UpstreamCheckpointLayout | None = None


class Gr00tN1d6ModelFactory:
    """从现有本地资产直接构造 owned Eagle 和 GR00T 组件。"""

    def __call__(self, config: Gr00tN1d6Config) -> Gr00tN1d6Components:
        """构造模型;仅在显式 checkpoint_path 存在时执行本地加载。"""
        resolved_asset = config.resolved_model_asset
        upstream_layout = None
        checkpoint_adapter = Gr00tN1d6CheckpointAdapter()
        if config.architecture_variant == "official_n1d6" and config.checkpoint_path is None:
            raise MissingModelAssetError(
                "gr00t_n1d6", "official_n1d6 does not permit random initialization"
            )
        if config.architecture_variant == "official_n1d6":
            checkpoint_root = Path(str(config.checkpoint_path)).expanduser().resolve(strict=False)
            if not (checkpoint_root / ".autovla-asset.json").is_file():
                raise LocalModelAssetError(
                    "checkpoint_path",
                    checkpoint_root,
                    (".autovla-asset.json",),
                    detail=(
                        "legacy path cannot bypass registered manifest, license, containment, "
                        "size, or SHA256 verification"
                    ),
                )
            if (
                checkpoint_root.name != GR00T_N1D6_ASSET_SPEC.revision
                or checkpoint_root.parent.name != GR00T_N1D6_ASSET_SPEC.key
            ):
                raise LocalModelAssetError(
                    "checkpoint_path", checkpoint_root, ("contained key/revision layout",)
                )
            store_root = checkpoint_root.parents[1]
            store = ModelAssetStore(store_root)
            resolved_asset = (
                store.verify(GR00T_N1D6_ASSET_SPEC)
                if resolved_asset is None
                else store.validate_resolved(resolved_asset, GR00T_N1D6_ASSET_SPEC)
            )
            upstream_layout = checkpoint_adapter.inspect_upstream_layout(resolved_asset)
            if (
                upstream_layout.key_count,
                upstream_layout.backbone_key_count,
                upstream_layout.action_head_key_count,
            ) != (1106, 633, 473):
                raise ValueError(
                    "official checkpoint index must contain 1106 keys split as "
                    "backbone=633/action_head=473"
                )
            if any(item.relative_action is not None for item in config.statistics.values()):
                raise UnsupportedOfficialRelativeStatisticsError(
                    "official relative_action statistics are per-horizon [T,D]; current "
                    "processor normalization is one-dimensional, so construction stops before "
                    "GPU allocation until a shape-correct per-horizon path is implemented"
                )
        self._require_dependencies()
        if config.architecture_variant == "reduced_runtime" and config.checkpoint_path is not None:
            raise ValueError("reduced_runtime validation random initialization forbids checkpoint")
        required = (
            "config.json",
            "preprocessor_config.json",
            "processor_config.json",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
            "special_tokens_map.json",
            "chat_template.json",
        )
        # Eagle 的官方完整文件清单与哈希尚未注册;必须在任何文件读取前失败。
        raise UnresolvedEagleAssetError(
            "Eagle production assets require a registered ModelAssetSpec and a freshly "
            "verified ModelAssetStore receipt with complete SHA256 inventory; direct "
            "eagle_asset_path filename consumption is forbidden; required inventory="
            + ",".join(required)
        )

    @staticmethod
    def _require_dependencies() -> None:
        """在构造前给出单一可操作的 optional-extra 错误。"""
        missing = tuple(
            name for name in ("torch", "transformers") if importlib.util.find_spec(name) is None
        )
        if missing:
            raise OptionalDependencyError(
                "GR00T N1.6.1 construction requires missing modules "
                f"{', '.join(missing)}; install the 'model-gr00t-n1d6' extra"
            )


__all__ = ["Gr00tN1d6Components", "Gr00tN1d6ModelFactory"]
