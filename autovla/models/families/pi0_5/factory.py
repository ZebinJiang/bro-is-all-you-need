# ruff: noqa: RUF002,RUF003
"""Pi0.5 唯一 ModelAssemblyRequest 到运行对象的生产工厂。"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.assembly import (
    AssemblyEvidenceIdentity,
    CheckpointLoadEvidence,
    ModelAssemblyPlan,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.assembly.runtime import ModelRuntimeBundle
from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.assets import Pi05AssetBundle
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.checkpoint import Pi05CheckpointAdapter
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.model import Pi05Model
from autovla.models.families.pi0_5.processor import Pi05Processor

Float32Array = NDArray[np.float32]


@runtime_checkable
class _TokenizerLike(Protocol):
    """描述工厂接受的本地 tokenizer 最小接口。"""

    def encode(self, text: str, *, add_special_tokens: bool) -> Sequence[int]:
        """把文本编码为 token ID 序列。"""

        ...


class Pi05ModelFactory:
    """构造、严格加载、冻结并返回同一规范装配结果。"""

    def plan(self, request: ModelAssemblyRequest) -> ModelAssemblyPlan:
        """验证类型化配置/资产并通过共享生命周期门。"""

        if type(request.config) is not Pi05Config:
            raise TypeError("Pi0.5 assembly requires Pi05Config")
        if type(request.asset_bundle) is not Pi05AssetBundle:
            raise TypeError("Pi0.5 assembly requires Pi05AssetBundle")
        return resolve_model_assembly(request)

    @staticmethod
    def _require_dependencies() -> None:
        """仅生产参数构造要求 Torch、Transformers 和 safetensors。"""

        missing = tuple(
            name
            for name in ("torch", "transformers", "safetensors")
            if importlib.util.find_spec(name) is None
        )
        if missing:
            raise OptionalDependencyError(
                "Pi0.5 construction requires missing modules "
                f"{', '.join(missing)}; use the model-pi0-5 runtime profile"
            )

    @staticmethod
    def _asset_json(bundle: Pi05AssetBundle, role: str) -> tuple[Path, ...]:
        """仅从已验证 manifest 枚举角色内 JSON，不扫描未声明文件。"""

        asset = bundle.assets_by_role[role]
        paths = tuple(
            asset.root / item.path
            for item in asset.manifest.files
            if Path(item.path).suffix == ".json"
        )
        if not paths or any(not path.is_file() or path.is_symlink() for path in paths):
            raise ValueError(f"Pi0.5 verified role {role!r} lacks local JSON assets")
        return paths

    @classmethod
    def _statistics(cls, bundle: Pi05AssetBundle) -> tuple[Float32Array, Float32Array]:
        """读取唯一包含 q01/q99 的已验证 normalization JSON。"""

        candidates: list[tuple[Float32Array, Float32Array]] = []
        for path in cls._asset_json(bundle, "normalization_statistics"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping) and "q01" in payload and "q99" in payload:
                candidates.append(
                    (
                        np.asarray(payload["q01"], dtype=np.float32),
                        np.asarray(payload["q99"], dtype=np.float32),
                    )
                )
        if len(candidates) != 1:
            raise ValueError("Pi0.5 requires exactly one q01/q99 normalization record")
        return candidates[0]

    @staticmethod
    def _tokenizer(bundle: Pi05AssetBundle) -> _TokenizerLike:
        """从已验证本地根构造 tokenizer，禁止 remote code 与隐式下载。"""

        from transformers import AutoTokenizer

        root = bundle.assets_by_role["gemma_tokenizer"].root
        tokenizer = AutoTokenizer.from_pretrained(
            root,
            local_files_only=True,
            trust_remote_code=False,
        )
        if not isinstance(tokenizer, _TokenizerLike):
            raise TypeError("Pi0.5 tokenizer must expose the local encode protocol")
        return tokenizer

    def build_processor(self, request: ModelAssemblyRequest) -> Pi05Processor:
        """从同一请求的本地 tokenizer 和统计量构造处理器。"""

        self.plan(request)
        config = cast(Pi05Config, request.config)
        bundle = cast(Pi05AssetBundle, request.asset_bundle)
        self._require_dependencies()
        q01, q99 = self._statistics(bundle)
        return Pi05Processor(
            config,
            q01,
            q99,
            tokenizer=self._tokenizer(bundle),
        )

    def build_backbone(self, request: ModelAssemblyRequest) -> Pi05VisionLanguageBackbone:
        """在调用方初始化上下文内构造完整 PaliGemma/SigLIP 前缀。"""

        self.plan(request)
        self._require_dependencies()
        return Pi05VisionLanguageBackbone(cast(Pi05Config, request.config), build_modules=True)

    def build_action_expert(self, request: ModelAssemblyRequest) -> Pi05ActionExpert:
        """在调用方初始化上下文内构造完整 Gemma action expert。"""

        self.plan(request)
        self._require_dependencies()
        return Pi05ActionExpert(cast(Pi05Config, request.config))

    def build_checkpoint_adapter(self, request: ModelAssemblyRequest) -> Pi05CheckpointAdapter:
        """返回 safetensors-only 严格适配器。"""

        self.plan(request)
        return Pi05CheckpointAdapter()

    @staticmethod
    def _tuning_evidence(
        model: Pi05Model,
        identity: AssemblyEvidenceIdentity,
    ) -> TuningFreezeEvidence:
        """从真实 ``requires_grad`` 参数逐元素生成调优/冻结证据。"""

        plan = model.parameter_plan()
        if len(plan["trainable"]) + len(plan["frozen"]) != sum(1 for _ in model.named_parameters()):
            raise RuntimeError("Pi0.5 parameter tuning inventory is incomplete")
        trainable = sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        )
        frozen = sum(
            parameter.numel() for parameter in model.parameters() if not parameter.requires_grad
        )
        return TuningFreezeEvidence(
            identity=identity,
            strategy="freeze_siglip_and_paligemma_tune_gemma_action_expert",
            trainable_components=model.config.trainable_components,
            frozen_components=model.config.frozen_components,
            trainable_parameter_count=trainable,
            frozen_parameter_count=frozen,
        )

    def complete(
        self,
        request: ModelAssemblyRequest,
        *,
        processor: Pi05Processor,
        backbone: Pi05VisionLanguageBackbone,
        action_expert: Pi05ActionExpert,
        model: Pi05Model,
        checkpoint_adapter: Pi05CheckpointAdapter,
        checkpoint_load: CheckpointLoadEvidence,
        tuning_freeze: TuningFreezeEvidence,
    ) -> ModelAssemblyResult[
        Pi05Processor,
        Pi05VisionLanguageBackbone,
        Pi05ActionExpert,
        Pi05Model,
        Pi05CheckpointAdapter,
        object,
    ]:
        """兼容显式证据闭合入口，但仍先通过共享资产/许可门。"""

        plan = self.plan(request)
        if processor.config != request.config:
            raise ValueError("processor config drifted from assembly request")
        if backbone.config != request.config or action_expert.config != request.config:
            raise ValueError("model component config drifted from assembly request")
        if model.config != request.config:
            raise ValueError("model config drifted from assembly request")
        return ModelAssemblyResult(
            plan=plan,
            processor=processor,
            backbone=backbone,
            action_head=action_expert,
            model=model,
            checkpoint_adapter=checkpoint_adapter,
            policy_bundle=None,
            checkpoint_load=checkpoint_load,
            tuning_freeze=tuning_freeze,
        )

    def __call__(
        self,
        request: ModelAssemblyRequest,
    ) -> ModelAssemblyResult[
        Pi05Processor,
        Pi05VisionLanguageBackbone,
        Pi05ActionExpert,
        Pi05Model,
        Pi05CheckpointAdapter,
        object,
    ]:
        """沿唯一共享计划构造模型并严格消费一个本地 safetensors checkpoint。"""

        plan = self.plan(request)
        self._require_dependencies()
        bundle = cast(Pi05AssetBundle, request.asset_bundle)
        config = cast(Pi05Config, request.config)
        q01, q99 = self._statistics(bundle)
        tokenizer = self._tokenizer(bundle)
        # 初始化上下文覆盖全部参数分配，兼容 ZeRO-3 等共享策略。
        with request.initialization_context_factory():
            processor = Pi05Processor(
                config,
                q01,
                q99,
                tokenizer=tokenizer,
            )
            backbone = Pi05VisionLanguageBackbone(config, build_modules=True)
            action_expert = Pi05ActionExpert(config)
            model = Pi05Model(config, backbone, action_expert)
        checkpoint_adapter = Pi05CheckpointAdapter()
        if len(bundle.checkpoint_candidates) != 1:
            raise ValueError("Pi0.5 production assembly requires exactly one safetensors file")
        checkpoint_path = bundle.checkpoint_candidates[0]
        fingerprint, _ = request.load_official_checkpoint(
            model,
            lambda: checkpoint_adapter.load_local(model, checkpoint_path),
        )
        identity = AssemblyEvidenceIdentity.from_plan(plan)
        loaded_parameters = sum(tensor.numel() for tensor in model.state_dict().values())
        return ModelAssemblyResult(
            plan=plan,
            processor=processor,
            backbone=backbone,
            action_head=action_expert,
            model=model,
            checkpoint_adapter=checkpoint_adapter,
            policy_bundle=None,
            checkpoint_load=CheckpointLoadEvidence(
                identity=identity,
                adapter_identity=checkpoint_adapter.identity,
                checkpoint_fingerprint=fingerprint,
                strictness="strict",
                loaded_parameter_count=loaded_parameters,
            ),
            tuning_freeze=self._tuning_evidence(model, identity),
        )

    @staticmethod
    def runtime_bundle(
        result: ModelAssemblyResult[
            Pi05Processor,
            Pi05VisionLanguageBackbone,
            Pi05ActionExpert,
            Pi05Model,
            Pi05CheckpointAdapter,
            object,
        ],
        *,
        runtime_profile_identity: str,
        asset_evidence: ModelRuntimeAssetEvidence,
    ) -> ModelRuntimeBundle[
        Pi05Processor,
        Pi05VisionLanguageBackbone,
        Pi05ActionExpert,
        Pi05Model,
        Pi05CheckpointAdapter,
        object,
    ]:
        """把唯一装配结果投影为共享运行包，不复制模型或参数。"""

        from autovla.models.families.pi0_5.family import PI05_SPEC

        return ModelRuntimeBundle(
            assembly_result=result,
            family_definition=PI05_SPEC,
            runtime_profile_identity=runtime_profile_identity,
            asset_evidence=asset_evidence,
        )


__all__ = ["Pi05ModelFactory"]
