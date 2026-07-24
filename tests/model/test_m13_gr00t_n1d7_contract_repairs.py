"""M13 GR00T N1.7 家族来源可证的契约修复测试。"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import yaml

from autovla.models.assembly import (
    AssemblyInitializationContextFactory,
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    TrainingAssemblyAdapter,
)
from autovla.models.families.gr00t_n1d7.factory import Gr00tN1d7ModelFactory
from autovla.models.families.gr00t_n1d7.family import GR00T_N1D7_FAMILY
from autovla.models.families.gr00t_n1d7.source_map import SOURCE_MAP

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class _InitializationContext:
    """提供测试所需的最小装配上下文协议。"""

    identity: str = "m13-n1d7-test-context"

    def __call__(self) -> nullcontext[None]:
        """返回无副作用上下文。"""

        return nullcontext()


def _experiment(*, deepspeed_version: str) -> object:
    """构造只覆盖 N1D7 训练适配前置校验的轻量配置。"""

    return SimpleNamespace(
        model=SimpleNamespace(
            registry_key="gr00t_n1d7",
            action_horizon=40,
            max_state_dim=132,
            max_action_dim=132,
        ),
        training=SimpleNamespace(
            distributed=SimpleNamespace(
                strategy_key="deepspeed_zero_3",
                deepspeed=SimpleNamespace(version=deepspeed_version),
            )
        ),
    )


def test_exact_candidate_dependencies_replace_stale_torch_range() -> None:
    """家族声明与 Python 3.12 候选 lock 的关键精确版本一致。"""

    requirements = {
        item.module: item.version_specifier
        for item in GR00T_N1D7_FAMILY.assembly_requirements.dependencies.items
    }
    assert requirements == {
        "torch": "==2.9.0+cu128",
        "transformers": "==4.57.3",
        "safetensors": "==0.7.0",
        "flash_attn": "==2.8.3",
        "deepspeed": "==0.17.6",
    }
    project = (ROOT / "envs/model-gr00t-n1d7/pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = "==3.12.*"' in project
    assert 'required-torch = "2.9.0+cu128"' in project


def test_family_owned_deepspeed_presets_select_only_0176() -> None:
    """ZeRO 1/2/3 家族 preset 均显式选择 0.17.6, 不继承共享默认值。"""

    for stage in (1, 2, 3):
        path = ROOT / f"configs/models/gr00t_n1d7/deepspeed_zero{stage}.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        distributed = payload["training"]["distributed"]
        assert distributed["strategy_key"] == f"deepspeed_zero_{stage}"
        assert distributed["deepspeed"]["version"] == "0.17.6"
        assert distributed["deepspeed"]["zero_stage"] == stage


def test_training_adapter_enforces_exact_deepspeed_then_preserves_asset_gate() -> None:
    """训练适配先拒绝版本漂移, 再保留两个未解决资产 blocker。"""

    factory = Gr00tN1d7ModelFactory()
    context = _InitializationContext()
    assert isinstance(context, AssemblyInitializationContextFactory)
    assert isinstance(factory, TrainingAssemblyAdapter)
    with pytest.raises(ValueError, match=r"exact 0\.17\.6"):
        factory.prepare_training_assembly(_experiment(deepspeed_version="0.19.2"), context)
    with pytest.raises(
        RuntimeError,
        match=r"ASSET_REQUIRED.*CHECKPOINT_LICENSE.*COSMOS_REASON2",
    ):
        factory.prepare_training_assembly(_experiment(deepspeed_version="0.17.6"), context)


def test_runtime_bundle_rejects_caller_supplied_evidence_without_authorized_plan() -> None:
    """旧运行投影入口不能用调用方证据绕过 N1D7 授权资产包。"""

    raw_result = object.__new__(ModelAssemblyResult)
    object.__setattr__(
        raw_result,
        "plan",
        SimpleNamespace(asset_bundle=object()),
    )
    result = cast(
        ModelAssemblyResult[object, object, object, object, object, object],
        raw_result,
    )
    evidence = ModelRuntimeAssetEvidence(
        asset_bundle_fingerprint="a" * 64,
        manifest_fingerprint="b" * 64,
        evidence_ids=("c" * 64,),
    )
    with pytest.raises(TypeError, match=r"authorized N1\.7 asset bundle"):
        Gr00tN1d7ModelFactory.runtime_bundle(
            result,
            runtime_profile_identity="fixture-profile@lock-fingerprint:" + "d" * 64,
            asset_evidence=evidence,
        )


def test_synthetic_fixture_is_deterministic_strict_and_never_runtime_evidence() -> None:
    """fixture 固定 processor/model 形状、hook 和纯合成非声明。"""

    torch = pytest.importorskip("torch", reason="focused tool environment has no Torch runtime")
    from autovla.models.components.flow_matching import FlowMatchingSchedule
    from autovla.models.families.gr00t_n1d7.fixtures import (
        build_synthetic_contract_fixture,
    )

    first = build_synthetic_contract_fixture()
    second = build_synthetic_contract_fixture()
    assert first.synthetic_only is second.synthetic_only is True
    assert first.training_batch.actions.shape == (2, 40, 12)
    assert first.model_batch.actions is not None
    assert first.model_batch.action_mask is not None
    assert first.model_batch.actions.shape == (2, 40, 132)
    assert first.model_batch.action_mask.dtype is torch.bool
    assert first.backbone_output.features.shape == (2, 6, 2048)
    torch.testing.assert_close(first.fixed_noise, second.fixed_noise)
    torch.testing.assert_close(first.noise_hook(first.model_batch.actions), first.fixed_noise)
    schedule = FlowMatchingSchedule(
        beta_alpha=1.5,
        beta_beta=1.0,
        time_scale=0.999,
        timestep_buckets=1000,
        inference_steps=4,
    )
    torch.testing.assert_close(
        first.time_hook(2, torch.device("cpu"), torch.float32, schedule),
        first.fixed_flow_time,
    )
    assert SOURCE_MAP["backbone"]["consumed_role"] == "local_config_processor_tokenizer_only"
