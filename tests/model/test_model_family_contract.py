"""M9 模型族唯一定义、轻量注册和运行时状态测试。"""

from __future__ import annotations

import subprocess
import sys
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
from autovla.models.registry import get, list_model_family_keys


def test_registry_fresh_process_is_lightweight_and_lists_only_canonical_keys() -> None:
    """全新解释器列举四个生产键且不导入重型模型栈。"""

    script = """
import sys
from autovla.models.registry import list_model_family_keys
assert list_model_family_keys() == ('gr00t_n1d6', 'pi0', 'pi0_5', 'pi0_fast')
forbidden = {'torch', 'transformers', 'jax', 'flax', 'orbax', 'openpi', 'huggingface_hub'}
assert not forbidden.intersection(sys.modules), sorted(forbidden.intersection(sys.modules))
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
    assert alias in list_model_family_keys(include_aliases=True)


def test_closed_runtime_support_and_pi_fail_before_side_effects() -> None:
    """Pi 三族在读取配置、数据、资产或模型前失败。"""

    assert get("gr00t_n1d6").runtime_support is RuntimeSupportState.EXECUTABLE
    for key in ("pi0", "pi0_fast", "pi0_5"):
        definition = get(key)
        assert (
            definition.runtime_support is RuntimeSupportState.ARCHITECTURE_DEFINED_RUNTIME_DEFERRED
        )
        assert definition.factories.model is None
        with pytest.raises(ModelRuntimeSupportError) as error:
            resolve_model_assembly(key, config=object())
        assert error.value.runtime_support is definition.runtime_support


def test_gr00t_pinned_shape_and_four_step_source_contract() -> None:
    """GR00T 官方定义固定为 50/128/128 envelope。"""

    definition = get("gr00t_n1d6")
    assert definition.shape.to_tuple() == (50, 128, 128)
    assert definition.capabilities.action.fixed_horizon == 50
    assert definition.capabilities.action.fixed_dimension == 128
    assert definition.action.horizon_policy is ActionHorizonPolicy.FIXED_BY_FAMILY
    assert definition.asset_keys == ("gr00t_n1d6", "gr00t_n1d6_eagle_support")
    assert "5dc80c4afd726b34faad1d8f7e007a13b34e4c88" in definition.upstream_reference


def test_pi_architecture_contracts_are_complete_without_runtime_dependency() -> None:
    """Pi 三族保存 pinned 架构差异且不声称可执行。"""

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
        assert definition.factories.model is None
        assert "15a9616a00943ada6c20a0f158e3adb39df2ccac" in definition.upstream_reference
