"""GR00T N1.7 单一规范装配工厂。"""

from __future__ import annotations

import importlib
import importlib.util
import json
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.assembly import (
    AssemblyEvidenceIdentity,
    CheckpointLoadEvidence,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    ModelRuntimeBundle,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.assembly.contracts import (
    RuntimeAssemblyBundle,
    RuntimeAssemblyInput,
    assemble_runtime_bundle,
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


@runtime_checkable
class _FromPretrained(Protocol):
    """描述 Transformers 本地资产构造入口。"""

    def from_pretrained(self, *args: object, **kwargs: object) -> object:
        """从本地资产返回动态运行对象。"""

        ...


@runtime_checkable
class _FromConfig(Protocol):
    """描述 Transformers 本地配置构造入口。"""

    def from_config(self, config: object, **kwargs: object) -> object:
        """从已验证配置返回动态模型对象。"""

        ...


@runtime_checkable
class _QwenTextConfigLike(Protocol):
    """描述工厂覆写的 Qwen 文本层数。"""

    num_hidden_layers: int


@runtime_checkable
class _QwenProcessorLike(Protocol):
    """描述 N1.7 processor 消费的最小 Qwen 接口。"""

    tokenizer: object

    def __call__(self, **kwargs: object) -> Mapping[str, object]:
        """返回本地 Qwen processor 编码映射。"""

        ...


def _require_modules(names: tuple[str, ...]) -> None:
    """在进入参数初始化前一次性报告缺失的隔离运行依赖。"""

    missing = tuple(name for name in names if importlib.util.find_spec(name) is None)
    if missing:
        raise OptionalDependencyError(
            f"GR00T N1.7 requires the model-gr00t-n1d7 runtime profile; missing={missing}"
        )


def _family_request(
    request: ModelAssemblyRequest,
) -> tuple["Gr00tN1d7Config", Gr00tN1d7AssetBundle]:
    """校验唯一请求中的配置与双资产包。"""

    from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config

    if not isinstance(cast(object, request), ModelAssemblyRequest):
        raise TypeError("N1.7 factory requires ModelAssemblyRequest")
    if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
        raise TypeError("request must carry Gr00tN1d7Config")
    if not isinstance(request.asset_bundle, Gr00tN1d7AssetBundle):
        raise TypeError("request must carry a verified GR00T N1.7 asset bundle")
    if request.config.cosmos_revision != request.asset_bundle.cosmos_revision:
        raise ValueError("config Cosmos revision must exactly match the verified asset receipt")
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


def _processor_metadata(
    path: Path,
) -> tuple[Mapping[str, Mapping[str, object]], Mapping[str, object]]:
    """读取官方 ``processor_kwargs.modality_configs`` 嵌套结构。"""

    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("processor_config.json must be a bounded local regular file")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("processor_config.json must contain an object")
    processor_kwargs = raw.get("processor_kwargs")
    if not isinstance(processor_kwargs, Mapping):
        raise ValueError("processor_config.json must contain processor_kwargs")
    modality_configs = processor_kwargs.get("modality_configs")
    if not isinstance(modality_configs, Mapping):
        raise ValueError("processor_kwargs must contain nested modality_configs")
    typed_modalities: dict[str, Mapping[str, object]] = {}
    for embodiment, modalities in modality_configs.items():
        if not isinstance(embodiment, str) or not isinstance(modalities, Mapping):
            raise ValueError("modality_configs must map embodiment names to mappings")
        typed_modalities[embodiment] = cast(Mapping[str, object], modalities)
    settings = {
        key: value
        for key, value in processor_kwargs.items()
        if isinstance(key, str)
        and key
        in {
            "clip_outliers",
            "apply_sincos_state_encoding",
            "exclude_state",
            "use_mean_std",
            "use_percentiles",
            "use_relative_action",
        }
    }
    if processor_kwargs.get("model_name") not in (None, "nvidia/Cosmos-Reason2-2B"):
        raise ValueError("processor model_name must identify Cosmos-Reason2-2B")
    return typed_modalities, settings


def _transformers_module() -> ModuleType:
    """延迟导入隔离 profile 中的 Transformers。"""

    _require_modules(("torch", "transformers", "safetensors", "diffusers"))
    return importlib.import_module("transformers")


def _qwen_processor(bundle: Gr00tN1d7AssetBundle) -> _QwenProcessorLike:
    """仅从 gated Cosmos 本地根构造 Qwen3-VL processor。"""

    transformers = _transformers_module()
    auto_processor = getattr(transformers, "AutoProcessor", None)
    if not isinstance(auto_processor, _FromPretrained):
        raise TypeError("Transformers must expose AutoProcessor.from_pretrained")
    processor = auto_processor.from_pretrained(
        str(bundle.backbone_assets[0]),
        local_files_only=True,
        trust_remote_code=False,
    )
    if not isinstance(processor, _QwenProcessorLike):
        raise TypeError("Qwen processor must expose tokenizer and callable encoding")
    return processor


def _qwen_model(config: "Gr00tN1d7Config", bundle: Gr00tN1d7AssetBundle) -> object:
    """由本地 Cosmos config 构造截断 16 层且不下载权重的 Qwen3-VL。"""

    transformers = _transformers_module()
    auto_config = getattr(transformers, "AutoConfig", None)
    auto_model = getattr(transformers, "AutoModelForImageTextToText", None)
    if not isinstance(auto_config, _FromPretrained):
        raise TypeError("Transformers must expose AutoConfig.from_pretrained")
    if not isinstance(auto_model, _FromConfig):
        raise TypeError("Transformers must expose AutoModelForImageTextToText.from_config")
    qwen_config = auto_config.from_pretrained(
        str(bundle.backbone_assets[0]),
        local_files_only=True,
        trust_remote_code=False,
    )
    text_config = getattr(qwen_config, "text_config", None)
    if text_config is None:
        raise ValueError("Cosmos config must expose Qwen3-VL text_config")
    if not isinstance(text_config, _QwenTextConfigLike):
        raise ValueError("Cosmos text_config must expose num_hidden_layers")
    text_config.num_hidden_layers = config.retained_language_layers
    attention_field = "_attn_implementation"
    setattr(qwen_config, attention_field, "flash_attention_2")
    return auto_model.from_config(qwen_config, attn_implementation="flash_attention_2")


class Gr00tN1d7ModelFactory:
    """构造 processor、Qwen3-VL、动作头、模型并严格加载同一 checkpoint。"""

    def build_processor(self, request: ModelAssemblyRequest, /) -> "Gr00tN1d7Processor":
        """从同一请求的 Cosmos 与统计资产构造 processor。"""

        config, bundle = _family_request(request)
        from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor

        modality_configs, processor_settings = _processor_metadata(
            bundle.root / "processor_config.json"
        )
        return Gr00tN1d7Processor(
            config,
            _qwen_processor(bundle),
            statistics=_statistics(bundle.root / "statistics.json"),
            modality_configs=modality_configs,
            processor_settings=processor_settings,
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
        _require_modules(("torch", "transformers", "safetensors", "diffusers"))
        from torch import nn

        from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
        from autovla.models.families.gr00t_n1d7.backbone import (
            CosmosReason2VisionLanguageBackbone,
        )
        from autovla.models.families.gr00t_n1d7.checkpoint import Gr00tN1d7CheckpointAdapter
        from autovla.models.families.gr00t_n1d7.model import Gr00tN1d7Model
        from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor

        modality_configs, processor_settings = _processor_metadata(
            bundle.root / "processor_config.json"
        )
        processor = Gr00tN1d7Processor(
            config,
            _qwen_processor(bundle),
            statistics=_statistics(bundle.root / "statistics.json"),
            modality_configs=modality_configs,
            processor_settings=processor_settings,
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
        report = request.load_official_checkpoint(
            model,
            lambda: adapter.load_local(
                model,
                bundle.root,
                strictness="strict",
                device=next(model.parameters()).device,
                config=config,
            ),
            partitioned_loader=lambda: adapter.partitioned_load(
                model,
                bundle.root,
                strictness="strict",
                config=config,
            ),
        )
        loaded_parameter_count = report.provenance.get("loaded_element_count")
        if type(loaded_parameter_count) is not int or loaded_parameter_count < 0:
            raise RuntimeError("N1.7 checkpoint report lacks a valid loaded element count")
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
                (),
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

    def build_runtime_bundle(
        self,
        request: ModelAssemblyRequest,
        /,
        *,
        runtime: RuntimeAssemblyInput,
    ) -> RuntimeAssemblyBundle[object, object, object, object, object, object]:
        """通过 family-neutral caller 消费 exact runtime 与授权资产证据。"""

        return assemble_runtime_bundle(request, self, runtime)

    @staticmethod
    def runtime_bundle(
        result: ModelAssemblyResult[
            "Gr00tN1d7Processor",
            "CosmosReason2VisionLanguageBackbone",
            "Gr00tN1d7ActionHead",
            "Gr00tN1d7Model",
            "Gr00tN1d7CheckpointAdapter",
            object,
        ],
        *,
        runtime_profile_identity: str,
        asset_evidence: ModelRuntimeAssetEvidence,
    ) -> ModelRuntimeBundle[
        "Gr00tN1d7Processor",
        "CosmosReason2VisionLanguageBackbone",
        "Gr00tN1d7ActionHead",
        "Gr00tN1d7Model",
        "Gr00tN1d7CheckpointAdapter",
        object,
    ]:
        """用调用方显式运行身份投影共享 bundle, 不推断 profile。"""

        return ModelRuntimeBundle(
            assembly_result=result,
            family_definition=result.plan.definition,
            runtime_profile_identity=runtime_profile_identity,
            asset_evidence=asset_evidence,
        )


__all__ = ["Gr00tN1d7ModelFactory"]
