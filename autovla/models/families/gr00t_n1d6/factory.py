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
from autovla.models.families.gr00t_n1d6.errors import LocalModelAssetError
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
        if config.architecture_variant == "official_n1d6" and config.checkpoint_path is None:
            raise LocalModelAssetError(
                "checkpoint_path",
                None,
                (
                    "config.json",
                    "processor_config.json",
                    "statistics.json",
                    "provenance.json",
                    "eagle/",
                    "exactly one complete local weight representation",
                ),
                detail="official_n1d6 does not permit random initialization",
            )
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
        if config.eagle_asset_path is None:
            raise LocalModelAssetError("eagle_asset_path", None, required)
        asset_root = Path(config.eagle_asset_path).expanduser()
        if not asset_root.is_absolute() or not asset_root.is_dir():
            raise LocalModelAssetError("eagle_asset_path", asset_root, required)
        asset_root = asset_root.resolve(strict=False)
        missing = tuple(name for name in required if not (asset_root / name).is_file())
        if missing:
            raise LocalModelAssetError("eagle_asset_path", asset_root, missing)
        try:
            eagle_config = LocalEagleConfig.from_local_json(asset_root / "config.json")
            _validate_eagle_contract(config, eagle_config)
            eagle_processor = LocalEagleProcessor.from_local_assets(asset_root, eagle_config)
            eagle_model = LocalEagleModel(
                eagle_config,
                retained_language_layers=config.retained_language_layers,
            )
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise LocalModelAssetError(
                "eagle_asset_path",
                asset_root,
                required,
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc
        backbone = EagleVisionLanguageBackbone(config, eagle_model)
        action_head = Gr00tN1d6ActionHead(config)
        model = Gr00tN1d6Model(backbone, action_head)
        processor = Gr00tN1d6Processor(
            config,
            eagle_processor,
            visual_tokens_per_image=eagle_config.visual_tokens_per_image,
        )
        checkpoint_report = None
        if config.checkpoint_path is not None:
            try:
                checkpoint_report = Gr00tN1d6CheckpointAdapter().load_local(
                    model,
                    config.checkpoint_path,
                    strictness="allow_known_optional",
                )
            except LocalModelAssetError:
                raise
            except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                raise LocalModelAssetError(
                    "checkpoint_path",
                    config.checkpoint_path,
                    ("complete local checkpoint bundle",),
                    detail=f"{type(exc).__name__}: {exc}",
                ) from exc
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


def _validate_eagle_contract(
    config: Gr00tN1d6Config,
    eagle_config: LocalEagleConfig,
) -> None:
    """要求本地 Eagle 架构与所选 GR00T 变体逐项一致。"""

    text_hidden = eagle_config.text_config.get("hidden_size")
    text_layers = eagle_config.text_config.get("num_hidden_layers")
    vision_image_size = eagle_config.vision_config.get("image_size")
    if text_hidden != config.backbone_embedding_dim:
        raise ValueError("Eagle text hidden_size does not match backbone_embedding_dim")
    if eagle_config.output_size != config.backbone_embedding_dim:
        raise ValueError("Eagle output_size does not match backbone_embedding_dim")
    if type(text_layers) is not int or text_layers < config.retained_language_layers:
        raise ValueError("Eagle text layers do not cover retained_language_layers")
    if vision_image_size != config.image_size:
        raise ValueError("Eagle vision image_size does not match GR00T image_size")
    if eagle_config.visual_tokens_per_image <= 0:
        raise ValueError("Eagle visual token cardinality must be positive")


__all__ = ["Gr00tN1d6Components", "Gr00tN1d6ModelFactory"]
