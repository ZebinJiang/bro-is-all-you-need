"""GR00T N1.7 单一规范装配工厂。"""

from __future__ import annotations

import importlib
import importlib.util
import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.assembly import (
    AssemblyEvidenceIdentity,
    CheckpointLoadEvidence,
    CheckpointShapeMismatch,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.families.gr00t_n1d7.assets import Gr00tN1d7AssetBundle

if TYPE_CHECKING:
    from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
    from autovla.models.families.gr00t_n1d7.backbone import (
        CosmosReason2VisionLanguageBackbone,
    )
    from autovla.models.families.gr00t_n1d7.checkpoint import Gr00tN1d7CheckpointAdapter
    from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
    from autovla.models.families.gr00t_n1d7.model import Gr00tN1d7Model
    from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor


def _require_modules(names: tuple[str, ...]) -> None:
    """在进入参数初始化前一次性报告缺失的隔离运行依赖。"""

    missing = tuple(name for name in names if importlib.util.find_spec(name) is None)
    if missing:
        raise OptionalDependencyError(
            "GR00T N1.7 requires the model-gr00t-n1d7 runtime profile; " f"missing={missing}"
        )


def _family_request(
    request: ModelAssemblyRequest,
) -> tuple["Gr00tN1d7Config", Gr00tN1d7AssetBundle]:
    """校验唯一请求中的配置与双资产包。"""

    from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config

    if not isinstance(request, ModelAssemblyRequest):
        raise TypeError("N1.7 factory requires ModelAssemblyRequest")
    if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
        raise TypeError("request must carry Gr00tN1d7Config")
    if not isinstance(request.asset_bundle, Gr00tN1d7AssetBundle):
        raise TypeError("request must carry a verified GR00T N1.7 asset bundle")
    return request.config, request.asset_bundle


def _statistics(path: Path) -> Mapping[str, Mapping[str, object]]:
    """有界读取 processor 使用的 per-embodiment 统计量。"""

    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("statistics.json must be a bounded local regular file")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("statistics.json must contain an object")
    output: dict[str, Mapping[str, object]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not isinstance(value, Mapping):
            raise ValueError("statistics entries must be string-keyed mappings")
        output[name] = cast(Mapping[str, object], value)
    return output


def _transformers_module() -> object:
    """延迟导入隔离 profile 中的 Transformers。"""

    _require_modules(("torch", "transformers", "safetensors"))
    return importlib.import_module("transformers")


def _qwen_processor(bundle: Gr00tN1d7AssetBundle) -> object:
    """仅从 gated Cosmos 本地根构造 Qwen3-VL processor。"""

    transformers = _transformers_module()
    auto_processor = transformers.AutoProcessor
    return auto_processor.from_pretrained(
        str(bundle.backbone_assets[0]),
        local_files_only=True,
        trust_remote_code=False,
    )


def _qwen_model(config: "Gr00tN1d7Config", bundle: Gr00tN1d7AssetBundle) -> object:
    """由本地 Cosmos config 构造截断 16 层且不下载权重的 Qwen3-VL。"""

    transformers = _transformers_module()
    auto_config = transformers.AutoConfig
    auto_model = transformers.AutoModelForImageTextToText
    qwen_config = auto_config.from_pretrained(
        str(bundle.backbone_assets[0]),
        local_files_only=True,
        trust_remote_code=False,
    )
    text_config = getattr(qwen_config, "text_config", None)
    if text_config is None:
        raise ValueError("Cosmos config must expose Qwen3-VL text_config")
    text_config.num_hidden_layers = config.retained_language_layers
    qwen_config._attn_implementation = "flash_attention_2"
    return auto_model.from_config(qwen_config, attn_implementation="flash_attention_2")


class Gr00tN1d7ModelFactory:
    """构造 processor、Qwen3-VL、动作头、模型并严格加载同一 checkpoint。"""

    def build_processor(self, request: ModelAssemblyRequest, /) -> "Gr00tN1d7Processor":
        """从同一请求的 Cosmos 与统计资产构造 processor。"""

        config, bundle = _family_request(request)
        from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor

        return Gr00tN1d7Processor(
            config,
            cast(object, _qwen_processor(bundle)),
            statistics=_statistics(bundle.root / "statistics.json"),
        )

    def build_backbone(
        self, request: ModelAssemblyRequest, /
    ) -> "CosmosReason2VisionLanguageBackbone":
        """在请求初始化上下文中构造唯一 Qwen3-VL 骨干。"""

        config, bundle = _family_request(request)
        from torch import nn

        from autovla.models.families.gr00t_n1d7.backbone import (
            CosmosReason2VisionLanguageBackbone,
        )

        with request.initialization_context_factory():
            model = _qwen_model(config, bundle)
            if not isinstance(model, nn.Module):
                raise TypeError("Transformers Qwen3-VL construction must return nn.Module")
            return CosmosReason2VisionLanguageBackbone(config, model)

    def build_action_head(self, request: ModelAssemblyRequest, /) -> "Gr00tN1d7ActionHead":
        """在请求初始化上下文中构造 embodiment-conditioned 动作头。"""

        config, _ = _family_request(request)
        from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead

        with request.initialization_context_factory():
            return Gr00tN1d7ActionHead(config)

    def architecture_components(
        self,
        request: ModelAssemblyRequest,
    ) -> tuple[
        "Gr00tN1d7Processor",
        "CosmosReason2VisionLanguageBackbone",
        "Gr00tN1d7ActionHead",
        "Gr00tN1d7Model",
        "Gr00tN1d7CheckpointAdapter",
    ]:
        """在调用方初始化上下文内建立唯一参数图, 不加载权重。"""

        config, bundle = _family_request(request)
        _require_modules(("torch", "transformers", "safetensors"))
        from torch import nn

        from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
        from autovla.models.families.gr00t_n1d7.backbone import (
            CosmosReason2VisionLanguageBackbone,
        )
        from autovla.models.families.gr00t_n1d7.checkpoint import Gr00tN1d7CheckpointAdapter
        from autovla.models.families.gr00t_n1d7.model import Gr00tN1d7Model
        from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor

        processor = Gr00tN1d7Processor(
            config,
            cast(object, _qwen_processor(bundle)),
            statistics=_statistics(bundle.root / "statistics.json"),
        )
        qwen_model = _qwen_model(config, bundle)
        if not isinstance(qwen_model, nn.Module):
            raise TypeError("Transformers Qwen3-VL construction must return nn.Module")
        backbone = CosmosReason2VisionLanguageBackbone(config, qwen_model)
        action_head = Gr00tN1d7ActionHead(config)
        model = Gr00tN1d7Model(config, backbone, action_head)
        return processor, backbone, action_head, model, Gr00tN1d7CheckpointAdapter()

    def __call__(
        self,
        request: ModelAssemblyRequest,
        /,
    ) -> ModelAssemblyResult[
        "Gr00tN1d7Processor",
        "CosmosReason2VisionLanguageBackbone",
        "Gr00tN1d7ActionHead",
        "Gr00tN1d7Model",
        "Gr00tN1d7CheckpointAdapter",
        object,
    ]:
        """沿 canonical plan 构造、严格加载并生成装配证据。"""

        config, bundle = _family_request(request)
        plan = resolve_model_assembly(request)
        # 唯一初始化上下文覆盖全部参数分配, 兼容 ZeRO-3 构造边界。
        with request.initialization_context_factory():
            processor, backbone, action_head, model, adapter = self.architecture_components(request)
        report = adapter.load_local(
            model,
            bundle.root,
            strictness="strict",
            device=next(model.parameters()).device,
            config=config,
        )
        state = model.state_dict()
        loaded_parameter_count = sum(state[key].numel() for key in report.mapped_keys)
        identity = AssemblyEvidenceIdentity.from_plan(plan)
        trainable = sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        )
        frozen = sum(
            parameter.numel() for parameter in model.parameters() if not parameter.requires_grad
        )
        return ModelAssemblyResult(
            plan,
            processor,
            backbone,
            action_head,
            model,
            adapter,
            None,
            CheckpointLoadEvidence(
                identity,
                adapter.adapter_identity,
                bundle.fingerprint,
                report.strictness,
                loaded_parameter_count,
                report.missing_keys,
                report.unexpected_keys,
                tuple(
                    CheckpointShapeMismatch(key, (), tuple(state[key].shape))
                    for key in report.shape_mismatches
                    if key in state
                ),
            ),
            TuningFreezeEvidence(
                identity,
                "artifact_precedence_qwen_visual_language_and_action_head",
                tuple(
                    name
                    for name, enabled in (
                        ("backbone.language", config.tune_language),
                        ("backbone.visual", config.tune_visual),
                        ("action_head.projectors", config.tune_projectors),
                        ("action_head.diffusion_model", config.tune_diffusion_model),
                        ("action_head.vlln", config.tune_vlln),
                    )
                    if enabled
                ),
                tuple(
                    name
                    for name, enabled in (
                        ("backbone.language", config.tune_language),
                        ("backbone.visual", config.tune_visual),
                        ("action_head.projectors", config.tune_projectors),
                        ("action_head.diffusion_model", config.tune_diffusion_model),
                        ("action_head.vlln", config.tune_vlln),
                    )
                    if not enabled
                ),
                trainable,
                frozen,
            ),
        )


__all__ = ["Gr00tN1d7ModelFactory"]
