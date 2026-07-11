"""GR00T N1.6.1 本地模型工厂。"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig
from autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling import LocalEagleModel
from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import LocalEagleProcessor
from autovla.models.families.gr00t_n1d6.action_head import Gr00tN1d6ActionHead
from autovla.models.families.gr00t_n1d6.backbone import EagleVisionLanguageBackbone
from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter
from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
from autovla.models.families.gr00t_n1d6.model import Gr00tN1d6Model
from autovla.models.families.gr00t_n1d6.processor import Gr00tN1d6Processor
from autovla.models.outputs import CheckpointLoadReport


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Components:
    """返回同一配置构造的模型、处理器和可选加载证据。"""

    model: Gr00tN1d6Model
    processor: Gr00tN1d6Processor
    checkpoint_report: CheckpointLoadReport | None


class Gr00tN1d6ModelFactory:
    """从现有本地资产直接构造 owned Eagle 和 GR00T 组件。"""

    def __call__(self, config: Gr00tN1d6Config) -> Gr00tN1d6Components:
        """构造模型;仅在显式 checkpoint_path 存在时执行本地加载。"""
        self._require_dependencies()
        if config.eagle_asset_path is None:
            raise ValueError("eagle_asset_path is required for GR00T N1.6.1 construction")
        asset_root = Path(config.eagle_asset_path).expanduser().resolve(strict=True)
        if not asset_root.is_dir():
            raise ValueError("eagle_asset_path must be an existing local directory")
        eagle_config = LocalEagleConfig.from_local_json(asset_root / "config.json")
        eagle_processor = LocalEagleProcessor.from_local_assets(asset_root, eagle_config)
        eagle_model = LocalEagleModel(
            eagle_config,
            retained_language_layers=config.retained_language_layers,
        )
        backbone = EagleVisionLanguageBackbone(config, eagle_model)
        action_head = Gr00tN1d6ActionHead(config)
        model = Gr00tN1d6Model(backbone, action_head)
        processor = Gr00tN1d6Processor(config, eagle_processor)
        checkpoint_report = None
        if config.checkpoint_path is not None:
            checkpoint_report = Gr00tN1d6CheckpointAdapter().load_local(
                model,
                config.checkpoint_path,
                strictness="allow_known_optional",
            )
        return Gr00tN1d6Components(
            model=model,
            processor=processor,
            checkpoint_report=checkpoint_report,
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
