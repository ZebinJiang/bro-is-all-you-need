"""M9 模型族唯一定义、轻量注册和运行时状态测试。"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from autovla.models.assembly import ModelRuntimeSupportError, resolve_model_assembly
from autovla.models.capabilities import (
    ActionDistribution,
    ActionHorizonPolicy,
    ActionRepresentation,
    StateConditioningPolicy,
)
from autovla.models.families.specification import (
    ModelFamilyDefinition,
    ModelFamilySpec,
    RuntimeSupportState,
)
from autovla.models.family import ModelFamilySpec as HistoricalModelFamilySpec
from autovla.models.registry import (
    ModelFamilyLifecycleState,
    get,
    get_model_family_catalog_entry,
    list_model_family_catalog,
    list_model_family_keys,
)


@dataclass(frozen=True, slots=True)
class _DeferredConfigIdentity:
    """提供延后模型族调用所需的最小类型化身份。"""

    family_key: str
    fingerprint: str = "0" * 64


def test_registry_fresh_process_is_lazy_and_lists_active_keys_by_default() -> None:
    """全新解释器只列举三个活跃键且不导入家族或重型模型栈。"""

    script = """
import sys
from autovla.models.registry import list_model_family_keys
assert list_model_family_keys() == ('gr00t_n1d6', 'gr00t_n1d7', 'pi0_5')
assert list_model_family_keys(include_deferred=True) == (
    'gr00t_n1d6', 'gr00t_n1d7', 'pi0', 'pi0_5', 'pi0_fast'
)
forbidden = {'torch', 'transformers', 'jax', 'flax', 'orbax', 'openpi', 'huggingface_hub'}
assert not forbidden.intersection(sys.modules), sorted(forbidden.intersection(sys.modules))
assert not any(name.startswith('autovla.models.families.gr00t_') for name in sys.modules)
assert not any(name.startswith('autovla.models.families.pi0') for name in sys.modules)
print('PASS_LIGHTWEIGHT_CANONICAL_MODEL_REGISTRY')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_LIGHTWEIGHT_CANONICAL_MODEL_REGISTRY"


def test_two_historical_spec_imports_are_one_concrete_type() -> None:
    """两个旧入口严格指向同一个不可变定义类型。"""

    assert ModelFamilySpec is ModelFamilyDefinition
    assert HistoricalModelFamilySpec is ModelFamilyDefinition
    assert isinstance(get("gr00t_n1d6"), ModelFamilyDefinition)


def test_catalog_closes_active_and_deferred_sets_without_runtime_claims() -> None:
    """M10 清单精确区分三活跃、两延后,且状态查询无需运行时工厂。"""

    assert tuple(entry.family_key for entry in list_model_family_catalog()) == (
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    )
    deferred = {
        entry.family_key: entry
        for entry in list_model_family_catalog(include_deferred=True)
        if not entry.active
    }
    assert set(deferred) == {"pi0", "pi0_fast"}
    assert all(
        entry.lifecycle is ModelFamilyLifecycleState.DEFERRED_BY_USER_PRIORITY
        for entry in deferred.values()
    )
    assert get_model_family_catalog_entry("gr00t_n1d7").active


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (
        ("gr00t-n1d6", "gr00t_n1d6"),
        ("gr00t_n1d6_metadata", "gr00t_n1d6"),
        ("pi0-roadmap", "pi0"),
        ("pi0_metadata", "pi0"),
        ("pi0-fast-roadmap", "pi0_fast"),
        ("pi05-roadmap", "pi0_5"),
        ("pi05_metadata", "pi0_5"),
    ),
)
def test_compatibility_alias_warns_and_preserves_definition_identity(
    alias: str, canonical: str
) -> None:
    """metadata/roadmap 别名只警告并返回规范对象。"""

    with pytest.warns(DeprecationWarning, match="deprecated"):
        resolved = get(alias)
    assert resolved is get(canonical)
    assert resolved.family_key == canonical
    assert alias in list_model_family_keys(include_deferred=True, include_aliases=True)


def test_deferred_and_asset_blocked_families_fail_before_side_effects() -> None:
    """延后家族和 N1.7 在读取配置、数据、资产或模型前失败。"""

    assert get("gr00t_n1d6").runtime_support is RuntimeSupportState.EXECUTABLE
    for key in ("pi0", "pi0_fast"):
        definition = get(key)
        assert (
            definition.runtime_support is RuntimeSupportState.ARCHITECTURE_DEFINED_RUNTIME_DEFERRED
        )
        assert definition.factories.model is None
        with pytest.raises(ModelRuntimeSupportError) as error:
            resolve_model_assembly(key, config=_DeferredConfigIdentity(key))
        assert error.value.runtime_support is definition.runtime_support
    n1d7 = get("gr00t_n1d7")
    assert n1d7.runtime_support is RuntimeSupportState.ASSET_REQUIRED
    with pytest.raises(ModelRuntimeSupportError):
        resolve_model_assembly("gr00t_n1d7", config=_DeferredConfigIdentity("gr00t_n1d7"))


def test_gr00t_pinned_shape_and_four_step_source_contract() -> None:
    """GR00T 官方定义固定为 50/128/128 envelope。"""

    definition = get("gr00t_n1d6")
    assert definition.shape.to_tuple() == (50, 128, 128)
    assert definition.capabilities.action.fixed_horizon == 50
    assert definition.capabilities.action.fixed_dimension == 128
    assert definition.action.horizon_policy is ActionHorizonPolicy.FIXED_BY_FAMILY
    assert definition.asset_keys == ("gr00t_n1d6", "gr00t_n1d6_eagle_support")
    assert "5dc80c4afd726b34faad1d8f7e007a13b34e4c88" in definition.upstream_reference


def test_pi_architecture_contracts_distinguish_active_pi05_from_deferred_pi() -> None:
    """Pi0.5 提供资产门控工厂,Pi0/Pi0-FAST 保持显式延后。"""

    pi0 = get("pi0")
    fast = get("pi0_fast")
    pi05 = get("pi0_5")
    assert pi0.shape.to_tuple() == fast.shape.to_tuple() == pi05.shape.to_tuple() == (50, 32, 32)
    assert pi0.inputs.max_language_tokens == fast.inputs.max_language_tokens == 48
    assert pi05.inputs.max_language_tokens == 200
    assert pi0.action.representation is ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK
    assert pi0.action.distribution is ActionDistribution.FLOW_MATCHING
    assert fast.action.representation is ActionRepresentation.DISCRETE_TOKEN_SEQUENCE
    assert fast.action.distribution is ActionDistribution.AUTOREGRESSIVE_CATEGORICAL
    assert pi05.inputs.state_conditioning is StateConditioningPolicy.DISCRETE_LANGUAGE_TOKENS
    for definition in (pi0, fast, pi05):
        assert definition.local_files_only is True
        assert "15a9616a00943ada6c20a0f158e3adb39df2ccac" in definition.upstream_reference
    assert pi0.factories.model is fast.factories.model is None
    assert pi05.factories.model == "autovla.models.families.pi0_5.factory:Pi05ModelFactory"
    assert pi05.assembly_requirements is not None
    assert pi05.assembly_requirements.evidence.official_checkpoint_load_validated is False


def test_active_n1d7_source_contract_is_asset_and_license_blocked() -> None:
    """N1.7 活跃来源契约保持 40/132/132 且不声称运行时就绪。"""

    definition = get("gr00t_n1d7")
    assert definition.shape.to_tuple() == (40, 132, 132)
    assert definition.validation_status == "license_cosmos_checkpoint_cuda_fail_closed"
    assert definition.assembly_requirements is not None
    assert definition.assembly_requirements.evidence.source_architecture_complete is True
    assert definition.assembly_requirements.evidence.official_asset_bundle_available is False
