# ruff: noqa: RUF002,RUF003
"""Pi0.5 唯一 ModelAssemblyRequest 到运行对象的生产工厂。"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import numpy as np

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.activation import RuntimeActivationReceipt
from autovla.models.assembly import (
    AssemblyEvidenceIdentity,
    AssemblyInitializationContextFactory,
    BaseModelAssetIdentity,
    CheckpointLoadEvidence,
    ModelAssemblyPlan,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    PreparedTrainingAssembly,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.assembly.contracts import (
    RuntimeAssemblyBundle,
    RuntimeAssemblyInput,
    assemble_runtime_bundle,
    logical_parameter_element_count,
)
from autovla.models.assembly.runtime import ModelRuntimeBundle
from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.assets import Pi05AssetBundle
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.checkpoint import Pi05CheckpointAdapter
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.model import Pi05Model
from autovla.models.families.pi0_5.normalization import (
    Pi05IdentitySemanticTransform,
    Pi05NormalizationReceipt,
    Pi05SemanticNormalizationPlan,
)
from autovla.models.families.pi0_5.policy import Pi05PolicyBundle
from autovla.models.families.pi0_5.processor import Pi05Processor, Pi05SentencePieceTokenizer
from autovla.models.readiness import (
    ModelFamilyReadinessSnapshot,
    RuntimeOperation,
    RuntimeValidationKey,
)

if TYPE_CHECKING:
    from autovla.config.schema.experiment import ExperimentConfig


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
        """仅生产参数构造要求 Torch、safetensors 和 SentencePiece。"""

        missing = tuple(
            name
            for name in ("torch", "safetensors", "sentencepiece")
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
    def _normalization_plan(cls, bundle: Pi05AssetBundle) -> Pi05SemanticNormalizationPlan:
        """从已验证 JSON 读取版本化物理语义和 quantile 计划。"""

        candidates: list[Mapping[str, object]] = []
        for path in cls._asset_json(bundle, "normalization_statistics"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(payload, Mapping)
                and payload.get("schema_version") == "autovla.pi0_5.normalization_bundle.v1"
            ):
                candidates.append(cast(Mapping[str, object], payload))
        if len(candidates) != 1:
            raise ValueError("Pi0.5 requires exactly one versioned normalization bundle")
        payload = candidates[0]
        if set(payload) != {"actions", "receipt", "schema_version", "state"}:
            raise ValueError("Pi0.5 normalization bundle fields must be exact")
        raw_receipt = payload["receipt"]
        state = payload["state"]
        actions = payload["actions"]
        if not isinstance(raw_receipt, Mapping):
            raise TypeError("Pi0.5 normalization receipt must be a mapping")
        if not isinstance(state, Mapping) or set(state) != {"q01", "q99"}:
            raise ValueError("Pi0.5 state quantiles must contain exact q01/q99")
        if not isinstance(actions, Mapping) or set(actions) != {"q01", "q99"}:
            raise ValueError("Pi0.5 action quantiles must contain exact q01/q99")
        receipt = Pi05NormalizationReceipt.from_mapping(cast(Mapping[str, object], raw_receipt))
        transform = Pi05IdentitySemanticTransform()
        if receipt.semantic_transform_id != transform.identity:
            raise ValueError(
                "non-identity Pi0.5 embodiment transforms require an explicit family-local adapter"
            )
        return Pi05SemanticNormalizationPlan(
            receipt=receipt,
            state_q01=np.asarray(state["q01"], dtype=np.float32),
            state_q99=np.asarray(state["q99"], dtype=np.float32),
            action_q01=np.asarray(actions["q01"], dtype=np.float32),
            action_q99=np.asarray(actions["q99"], dtype=np.float32),
            semantic_transform=transform,
        )

    @staticmethod
    def _tokenizer(bundle: Pi05AssetBundle) -> _TokenizerLike:
        """从已验证 manifest 的单个 SentencePiece 文件构造 tokenizer。"""

        asset = bundle.assets_by_role["gemma_tokenizer"]
        candidates = tuple(
            asset.root / item.path
            for item in asset.manifest.files
            if Path(item.path).name == "paligemma_tokenizer.model"
        )
        if len(candidates) != 1:
            raise ValueError("Pi0.5 requires exactly one paligemma_tokenizer.model")
        tokenizer = Pi05SentencePieceTokenizer(candidates[0])
        if not isinstance(tokenizer, _TokenizerLike):
            raise TypeError("Pi0.5 tokenizer must expose the local encode protocol")
        return tokenizer

    def prepare_training_assembly(
        self,
        config: "ExperimentConfig",
        initialization_context_factory: AssemblyInitializationContextFactory,
        /,
    ) -> PreparedTrainingAssembly:
        """解析三类本地资产并投影为唯一 Pi0.5 训练装配请求。"""

        from autovla.assets import (
            DEFAULT_MODEL_ASSET_REGISTRY,
            ModelAssetResolver,
            ModelAssetStore,
            VerifiedModelAssetBundle,
        )
        from autovla.config.schema.experiment import ExperimentConfig
        from autovla.data.transforms import TransformPlan
        from autovla.models.capabilities import PrecisionSupport, TopologySupport

        if not isinstance(config, ExperimentConfig):
            raise TypeError("Pi0.5 training assembly requires ExperimentConfig")
        required_keys = (
            "pi0_5_checkpoint",
            "pi0_5_gemma_tokenizer",
            "pi0_5_normalization",
        )
        if config.model.registry_key != "pi0_5":
            raise ValueError("Pi0.5 factory requires model.registry_key=pi0_5")
        if config.model.asset_bundle_keys != required_keys:
            raise ValueError("Pi0.5 requires the exact ordered three-asset bundle")
        if config.model.action_dim not in (None, 32):
            raise ValueError("Pi0.5 action_dim must remain 32")
        if config.model.max_state_dim not in (None, 32):
            raise ValueError("Pi0.5 max_state_dim must remain 32")
        if config.model.max_action_dim not in (None, 32):
            raise ValueError("Pi0.5 max_action_dim must remain 32")
        asset_store = ModelAssetStore(config.assets.store.root)
        resolver = ModelAssetResolver(asset_store, DEFAULT_MODEL_ASSET_REGISTRY)
        checkpoint, tokenizer, normalization = (resolver.resolve(key) for key in required_keys)
        checkpoint_candidates = tuple(
            checkpoint.root / item.path
            for item in checkpoint.manifest.files
            if Path(item.path).suffix == ".safetensors"
        )
        tokenizer_assets = tuple(
            tokenizer.root / item.path
            for item in tokenizer.manifest.files
            if Path(item.path).name == "paligemma_tokenizer.model"
        )
        verified = VerifiedModelAssetBundle(
            family_key="pi0_5",
            revision=checkpoint.manifest.revision,
            root=checkpoint.root,
            assets_by_role={
                "checkpoint": checkpoint,
                "gemma_tokenizer": tokenizer,
                "normalization_statistics": normalization,
            },
            checkpoint_candidates=checkpoint_candidates,
            tokenizer_or_processor_assets=tokenizer_assets,
        )
        family_config = Pi05Config(
            action_horizon=config.model.action_horizon or 50,
        )
        request = ModelAssemblyRequest(
            family_key="pi0_5",
            config=family_config,
            asset_bundle=Pi05AssetBundle.from_verified(verified),
            # q01/q99 与物理语义由 processor 的版本化收据独占消费。
            transform_plan=TransformPlan(),
            precision=PrecisionSupport(config.topology.precision.mode),
            topology=TopologySupport(config.topology.distributed.strategy_key),
            local_files_only=True,
            initialization_context_factory=initialization_context_factory,
        )
        return PreparedTrainingAssembly(
            request,
            BaseModelAssetIdentity(
                key=checkpoint.manifest.key,
                revision=checkpoint.manifest.revision,
                spec_identity_sha256=checkpoint.identity,
            ),
        )

    def build_processor(self, request: ModelAssemblyRequest) -> Pi05Processor:
        """从同一请求的本地 tokenizer 和统计量构造处理器。"""

        self.plan(request)
        config = cast(Pi05Config, request.config)
        bundle = cast(Pi05AssetBundle, request.asset_bundle)
        self._require_dependencies()
        plan = self._normalization_plan(bundle)
        return Pi05Processor(
            config,
            tokenizer=self._tokenizer(bundle),
            normalization_plan=plan,
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
            logical_parameter_element_count(parameter)
            for parameter in model.parameters()
            if parameter.requires_grad
        )
        frozen = sum(
            logical_parameter_element_count(parameter)
            for parameter in model.parameters()
            if not parameter.requires_grad
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
        normalization_plan = self._normalization_plan(bundle)
        tokenizer = self._tokenizer(bundle)
        # 初始化上下文覆盖全部参数分配，兼容 ZeRO-3 等共享策略。
        with request.initialization_context_factory():
            processor = Pi05Processor(
                config,
                tokenizer=tokenizer,
                normalization_plan=normalization_plan,
            )
            backbone = Pi05VisionLanguageBackbone(config, build_modules=True)
            action_expert = Pi05ActionExpert(config)
            model = Pi05Model(config, backbone, action_expert)
        checkpoint_adapter = Pi05CheckpointAdapter()
        if len(bundle.checkpoint_candidates) != 1:
            raise ValueError("Pi0.5 production assembly requires exactly one safetensors file")
        checkpoint_path = bundle.checkpoint_candidates[0]
        fingerprint, loaded_parameters = request.load_official_checkpoint(
            model,
            lambda: checkpoint_adapter.load_local(model, checkpoint_path),
            partitioned_loader=lambda: checkpoint_adapter.partitioned_load(
                model,
                checkpoint_path,
            ),
        )
        identity = AssemblyEvidenceIdentity.from_plan(plan)
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
    def build_policy_bundle(
        result: ModelAssemblyResult[
            Pi05Processor,
            Pi05VisionLanguageBackbone,
            Pi05ActionExpert,
            Pi05Model,
            Pi05CheckpointAdapter,
            object,
        ],
        *,
        readiness: ModelFamilyReadinessSnapshot,
        processor_key: RuntimeValidationKey,
        prediction_key: RuntimeValidationKey,
        decode_key: RuntimeValidationKey,
        promotions: Mapping[RuntimeOperation, RuntimeActivationReceipt],
    ) -> Pi05PolicyBundle:
        """从唯一装配结果和三段 canonical 激活链构造策略包。"""

        plan = result.processor.normalization_plan
        if plan is None:
            raise ValueError("Pi0.5 policy bundle requires a semantic normalization plan")
        if result.model.config != result.processor.config:
            raise ValueError("Pi0.5 policy assembly config drifted")
        return Pi05PolicyBundle(
            processor=result.processor,
            model=result.model,
            normalization_plan=plan,
            readiness=readiness,
            processor_key=processor_key,
            prediction_key=prediction_key,
            decode_key=decode_key,
            promotions=promotions,
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
