"""M10 家族中立装配与闭合模型动物园契约测试。"""

from __future__ import annotations

import subprocess
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import pytest

from autovla.assets import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetBundle,
    ModelAssetManifest,
    ResolvedModelAsset,
)
from autovla.data.transforms import TransformPlan
from autovla.models.assembly import (
    ActionHeadFactory,
    AssemblyEvidenceIdentity,
    AssemblyInitializationContextFactory,
    CheckpointAdapterFactory,
    CheckpointLoadEvidence,
    CheckpointShapeMismatch,
    ModelAssemblyPlan,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    ModelFactory,
    ModelProcessorFactory,
    PolicyBundleFactory,
    TuningFreezeEvidence,
    VisionLanguageBackboneFactory,
    resolve_model_assembly,
)
from autovla.models.capabilities import (
    ActionDimensionPolicy,
    ActionDistribution,
    ActionHorizonPolicy,
    ActionRepresentation,
    CheckpointFormat,
    InputCapabilities,
    NormalizationCapabilities,
    NormalizationMode,
    PrecisionSupport,
    RuntimeSupportLevel,
    SideEffectPermissions,
    StateConditioningPolicy,
    StatePolicy,
    SupportState,
    TopologySupport,
)
from autovla.models.families import M10_MODEL_ZOO_CONTRACT
from autovla.models.families.specification import (
    ModelActionContract,
    ModelAssetRequirement,
    ModelCheckpointDefinition,
    ModelInputContract,
    RuntimeEvidenceState,
)
from autovla.models.registry import get


@dataclass(frozen=True, slots=True)
class _ConfigIdentity:
    """提供装配协议需要的最小配置身份。"""

    family_key: str = "gr00t_n1d6"
    fingerprint: str = "1" * 64


@dataclass(slots=True)
class _MutableConfigIdentity:
    """模拟外层计划冻结后仍可能漂移的结构配置。"""

    family_key: str = "gr00t_n1d6"
    fingerprint: str = "1" * 64


class _VerifiedBundle:
    """模拟已完成自身校验的结构化资产协议。"""

    family_key = "gr00t_n1d6"
    revision = "2" * 40
    root = Path("/verified/gr00t_n1d6")
    checkpoint_candidates: tuple[Path, ...] = ()
    tokenizer_or_processor_assets: tuple[Path, ...] = ()
    backbone_assets: tuple[Path, ...] = ()
    provenance: tuple[AssetProvenanceRecord, ...] = ()
    license_records: tuple[AssetLicenseRecord, ...] = ()
    fingerprint = "3" * 64

    def __init__(self) -> None:
        """创建独立的测试清单与资产角色映射。"""

        self.manifest: dict[str, ModelAssetManifest] = {}
        self.assets_by_role: dict[str, ResolvedModelAsset] = {}

    def validate(self) -> None:
        """验证测试资产根和家族身份。"""

        if not self.root.is_absolute() or self.family_key != "gr00t_n1d6":
            raise ValueError("invalid verified bundle")


class _StringComponentFactory:
    """实现共享组件工厂协议并回显请求家族。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> str:
        """返回不触发模型副作用的测试组件。"""

        return request.family_key


class _IdentityContextFactory:
    """提供不执行分布式框架的策略初始化上下文身份。"""

    @property
    def identity(self) -> str:
        """返回测试策略稳定身份。"""

        return "test.strategy.zero3_init.v1"

    def __call__(self) -> AbstractContextManager[None]:
        """禁止本契约测试实际进入初始化上下文。"""

        raise AssertionError("assembly resolution must not execute initialization context")


class _StringModelFactory:
    """实现完整模型工厂协议并返回绑定证据。"""

    def __call__(
        self,
        request: ModelAssemblyRequest,
        /,
    ) -> ModelAssemblyResult[str, str, str, str, str, str]:
        """由规范请求构造纯文本测试结果。"""

        plan = resolve_model_assembly(request)
        identity = AssemblyEvidenceIdentity.from_plan(plan)
        return ModelAssemblyResult(
            plan=plan,
            processor="processor",
            backbone="backbone",
            action_head="action_head",
            model="model",
            checkpoint_adapter="checkpoint_adapter",
            policy_bundle="policy_bundle",
            checkpoint_load=CheckpointLoadEvidence(
                identity=identity,
                adapter_identity="test:checkpoint_adapter",
                checkpoint_fingerprint="4" * 64,
                strictness="strict",
                loaded_parameter_count=1,
                missing_keys=("optional.bias",),
                shape_mismatches=(
                    CheckpointShapeMismatch(
                        key="action_head.weight",
                        checkpoint_shape=(4, 8),
                        model_shape=(4, 16),
                    ),
                ),
                known_optional_missing_keys=("optional.bias",),
            ),
            tuning_freeze=TuningFreezeEvidence(
                identity=identity,
                strategy="action_head_only",
                trainable_components=("action_head",),
                frozen_components=("backbone",),
                trainable_parameter_count=1,
                frozen_parameter_count=1,
            ),
        )


def _assembly_request() -> ModelAssemblyRequest:
    """返回共享请求、计划和结果测试使用的规范输入。"""

    return ModelAssemblyRequest(
        family_key="gr00t_n1d6",
        config=_ConfigIdentity(),
        asset_bundle=_VerifiedBundle(),
        transform_plan=TransformPlan(),
        precision=PrecisionSupport.BFLOAT16,
        topology=TopologySupport.SINGLE_GPU,
    )


def test_shared_assembly_import_is_family_neutral_and_lightweight() -> None:
    """通用装配导入不得加载家族实现或重型运行时。"""

    script = """
import sys
import autovla.models.assembly.plan
forbidden_prefixes = (
    'autovla.assets.bundles',
    'autovla.assets.registry',
    'autovla.models.registry',
    'autovla.models.families.gr00t_n1d6',
    'autovla.models.families.gr00t_n1d7',
    'autovla.models.families.pi0_5',
)
assert not any(name.startswith(forbidden_prefixes) for name in sys.modules)
assert not {'torch', 'transformers', 'jax', 'flax', 'orbax'} & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_closed_family_requirements_project_m9_without_duplicate_implementations() -> None:
    """M9 字段经窄投影形成类型化 M10 要求和稳定指纹。"""

    definition = get("gr00t_n1d6")
    requirements = definition.assembly_requirements
    assert requirements is not None
    assert definition.action.representation is ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK
    assert definition.action.distribution is ActionDistribution.FLOW_MATCHING
    assert definition.action.horizon_policy is ActionHorizonPolicy.FIXED_BY_FAMILY
    assert requirements.checkpoint.checkpoint_format is CheckpointFormat.SAFETENSORS
    assert requirements.runtime_level is RuntimeSupportLevel.ASSET_GATED
    assert requirements.precisions == (PrecisionSupport.BFLOAT16, PrecisionSupport.FLOAT32)
    assert TopologySupport.DEEPSPEED_ZERO_3 in requirements.topologies
    assert len(definition.fingerprint) == 64
    assert definition.to_json_dict()["assembly_requirements"] == requirements.to_json_dict()


def test_request_validates_inputs_and_preserves_resolver_compatibility() -> None:
    """真实请求与历史参数调用解析为相同计划身份。"""

    request = _assembly_request()
    assert isinstance(request.asset_bundle, ModelAssetBundle)
    request_plan = resolve_model_assembly(request)
    compatibility_plan = resolve_model_assembly(
        "gr00t_n1d6",
        config=_ConfigIdentity(),
        asset_bundle=_VerifiedBundle(),
        transform_plan=TransformPlan(),
        precision=PrecisionSupport.BFLOAT16,
        topology=TopologySupport.SINGLE_GPU,
    )
    assert isinstance(request_plan, ModelAssemblyPlan)
    assert request_plan.provenance_fingerprint == compatibility_plan.provenance_fingerprint
    with pytest.raises(ValueError, match="family_key"):
        replace(request, family_key="pi0_5")


def test_result_binds_plan_load_and_tuning_evidence_without_identity_drift() -> None:
    """结果接受同源证据并拒绝配置、资产或变换身份漂移。"""

    result = _StringModelFactory()(_assembly_request())
    assert result.model == "model"
    assert result.checkpoint_load.shape_mismatches[0].key == "action_head.weight"
    with pytest.raises(ValueError, match="must not be None"):
        replace(result, model=cast(str, None))
    drifted = replace(
        result.checkpoint_load.identity,
        transform_plan_fingerprint="5" * 64,
    )
    with pytest.raises(ValueError, match="identity drifted"):
        replace(
            result,
            checkpoint_load=replace(result.checkpoint_load, identity=drifted),
        )


def test_generic_factory_protocols_share_one_typed_request_result_boundary() -> None:
    """组件和完整模型工厂共享请求输入并保留泛型产品类型。"""

    component_factory = _StringComponentFactory()
    processor_factory: ModelProcessorFactory[str] = component_factory
    backbone_factory: VisionLanguageBackboneFactory[str] = component_factory
    action_head_factory: ActionHeadFactory[str] = component_factory
    checkpoint_factory: CheckpointAdapterFactory[str] = component_factory
    policy_factory: PolicyBundleFactory[str] = component_factory
    model_factory: ModelFactory[str, str, str, str, str, str] = _StringModelFactory()
    request = _assembly_request()
    assert (
        processor_factory(request),
        backbone_factory(request),
        action_head_factory(request),
        checkpoint_factory(request),
        policy_factory(request),
    ) == ("gr00t_n1d6",) * 5
    assert model_factory(request).checkpoint_adapter == "checkpoint_adapter"


def test_initialization_context_is_fingerprinted_without_execution() -> None:
    """策略初始化上下文进入计划身份但解析阶段不执行它。"""

    context_factory: AssemblyInitializationContextFactory = _IdentityContextFactory()
    local_plan = resolve_model_assembly(_assembly_request())
    strategy_plan = resolve_model_assembly(
        replace(
            _assembly_request(),
            initialization_context_factory=context_factory,
        )
    )
    assert strategy_plan.initialization_context_factory is context_factory
    assert strategy_plan.initialization_context_identity == context_factory.identity
    assert strategy_plan.provenance_fingerprint != local_plan.provenance_fingerprint


def test_plan_snapshots_identity_and_result_rejects_live_protocol_drift() -> None:
    """内部协议漂移不改变计划指纹,但会关闭结果构造。"""

    config = _MutableConfigIdentity()
    plan = resolve_model_assembly(replace(_assembly_request(), config=config))
    fingerprint = plan.provenance_fingerprint
    identity = AssemblyEvidenceIdentity.from_plan(plan)
    config.fingerprint = "9" * 64
    assert plan.provenance_fingerprint == fingerprint
    with pytest.raises(ValueError, match="input identity drifted"):
        ModelAssemblyResult(
            plan=plan,
            processor="processor",
            backbone="backbone",
            action_head="action_head",
            model="model",
            checkpoint_adapter="checkpoint_adapter",
            policy_bundle=None,
            checkpoint_load=CheckpointLoadEvidence(
                identity=identity,
                adapter_identity="test:checkpoint_adapter",
                checkpoint_fingerprint="4" * 64,
                strictness="strict",
                loaded_parameter_count=1,
            ),
            tuning_freeze=TuningFreezeEvidence(
                identity=identity,
                strategy="full_finetune",
                trainable_components=("model",),
                frozen_components=(),
                trainable_parameter_count=1,
                frozen_parameter_count=0,
            ),
        )


def test_m10_model_zoo_contract_preserves_exact_keys_and_backend_decision() -> None:
    """共享面只声明三个活跃家族和两个显式延后家族。"""

    assert M10_MODEL_ZOO_CONTRACT.active_family_keys == (
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    )
    assert M10_MODEL_ZOO_CONTRACT.deferred_family_keys == ("pi0", "pi0_fast")
    assert M10_MODEL_ZOO_CONTRACT.backend_decision == "NO_BACKEND_WINNER"


def test_public_shared_contracts_fail_closed_on_runtime_type_confusion() -> None:
    """共享契约拒绝 bool/int 混淆、任意对象和错误闭集类型。"""

    invalid_state = cast(StateConditioningPolicy | str, object())
    with pytest.raises((TypeError, ValueError)):
        ModelInputContract(("camera.rgb_0",), cast(int, True), True, invalid_state)
    with pytest.raises(TypeError, match="language_required"):
        ModelInputContract(
            ("camera.rgb_0",),
            224,
            cast(bool, 1),
            StateConditioningPolicy.CONTINUOUS_FEATURES,
        )
    with pytest.raises(ValueError, match="max_language_tokens"):
        ModelInputContract(
            ("camera.rgb_0",),
            224,
            True,
            StateConditioningPolicy.CONTINUOUS_FEATURES,
            max_language_tokens=cast(int, True),
        )
    invalid_representation = cast(ActionRepresentation | str, object())
    with pytest.raises(TypeError, match="representation"):
        ModelActionContract(
            invalid_representation,
            "capability_governed",
            "compatibility_only",
            "capability_governed",
            "none",
        )
    with pytest.raises(TypeError, match="distribution"):
        ModelActionContract(
            "compatibility_only",
            "capability_governed",
            "compatibility_only",
            "capability_governed",
            "none",
            distribution=cast(ActionDistribution, object()),
            dimension_policy=ActionDimensionPolicy.UNVERIFIED,
        )
    with pytest.raises(TypeError, match="required_for_runtime"):
        ModelAssetRequirement("checkpoint", "asset", cast(bool, 1))
    with pytest.raises(TypeError, match="immutable_base_asset"):
        ModelCheckpointDefinition(
            CheckpointFormat.SAFETENSORS,
            "safetensors",
            immutable_base_asset=cast(bool, 1),
        )
    with pytest.raises(TypeError, match="single_gpu_validated"):
        RuntimeEvidenceState(single_gpu_validated=cast(bool, 1))
    with pytest.raises(TypeError, match="statistics_required"):
        NormalizationCapabilities(
            SupportState.SUPPORTED,
            NormalizationMode.IDENTITY,
            cast(bool, 1),
        )
    with pytest.raises(TypeError, match="network"):
        SideEffectPermissions(network=cast(bool, 1))
    with pytest.raises(TypeError, match="language_required"):
        InputCapabilities(
            SupportState.SUPPORTED,
            ("camera.rgb_0",),
            cast(bool, 1),
            StatePolicy.REQUIRED,
        )
    definition = get("gr00t_n1d6")
    with pytest.raises(TypeError, match="local_files_only"):
        replace(definition, local_files_only=cast(bool, 1))
