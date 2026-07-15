"""M10 家族中立装配与闭合模型动物园契约测试。"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar, cast

import pytest

from autovla.assets import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ModelAssetBundle,
    ModelAssetManifest,
    ResolvedModelAsset,
)
from autovla.data.transforms import TransformPlan
from autovla.models.assembly import ModelAssemblyPlan, resolve_model_assembly
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


class _VerifiedBundle:
    """模拟已完成自身校验的结构化资产协议。"""

    family_key = "gr00t_n1d6"
    revision = "2" * 40
    root = Path("/verified/gr00t_n1d6")
    manifest: ClassVar[dict[str, ModelAssetManifest]] = {}
    assets_by_role: ClassVar[dict[str, ResolvedModelAsset]] = {}
    checkpoint_candidates: tuple[Path, ...] = ()
    tokenizer_or_processor_assets: tuple[Path, ...] = ()
    backbone_assets: tuple[Path, ...] = ()
    provenance: tuple[AssetProvenanceRecord, ...] = ()
    license_records: tuple[AssetLicenseRecord, ...] = ()
    fingerprint = "3" * 64

    def validate(self) -> None:
        """验证测试资产根和家族身份。"""

        if not self.root.is_absolute() or self.family_key != "gr00t_n1d6":
            raise ValueError("invalid verified bundle")


def test_shared_assembly_import_is_family_neutral_and_lightweight() -> None:
    """通用装配导入不得加载家族实现或重型运行时。"""

    script = """
import sys
import autovla.models.assembly.plan
forbidden_prefixes = (
    'autovla.assets.bundles',
    'autovla.assets.registry',
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


def test_generic_asset_protocol_and_assembly_plan_bind_verified_identities() -> None:
    """装配只消费通用配置和资产协议, 并绑定其稳定身份。"""

    bundle = _VerifiedBundle()
    assert isinstance(bundle, ModelAssetBundle)
    plan = resolve_model_assembly(
        "gr00t_n1d6",
        config=_ConfigIdentity(),
        asset_bundle=bundle,
        transform_plan=TransformPlan(),
        precision=PrecisionSupport.BFLOAT16,
        topology=TopologySupport.SINGLE_GPU,
    )
    assert isinstance(plan, ModelAssemblyPlan)
    assert plan.asset_bundle is bundle
    assert len(plan.provenance_fingerprint) == 64


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
