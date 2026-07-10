"""M4 训练组件的规范 Registry 工厂命名空间。"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from autovla.core.registry import Registry
from autovla.core.runtime import RuntimePlan
from autovla.models.family import ModelFamilySpec
from autovla.models.registry import get_model_family_spec
from autovla.training.contracts import (
    ActionPolicy,
    BatchAdapter,
    CheckpointAdapter,
    LossAdapter,
)
from autovla.training.test_components import (
    DeterministicTestPolicy,
    DisabledDeploymentHook,
    ManifestOnlyCheckpointAdapter,
    MaskedActionMseAdapter,
    TestDoubleBatchAdapter,
)

BatchAdapterFactory = Callable[[int, int], BatchAdapter]
PolicyFactory = Callable[[int], ActionPolicy]
LossFactory = Callable[[], LossAdapter]
CheckpointFactory = Callable[[], CheckpointAdapter]
RuntimePlanFactory = Callable[[], RuntimePlan]
DeploymentHookFactory = Callable[[], DisabledDeploymentHook]
ModelFamilyFactory = Callable[[], ModelFamilySpec]

BATCH_ADAPTER_FACTORIES: Registry[BatchAdapterFactory] = Registry("batch-adapter-factories")
POLICY_FACTORIES: Registry[PolicyFactory] = Registry("policy-factories")
LOSS_FACTORIES: Registry[LossFactory] = Registry("loss-factories")
CHECKPOINT_FACTORIES: Registry[CheckpointFactory] = Registry("checkpoint-factories")
RUNTIME_PLAN_FACTORIES: Registry[RuntimePlanFactory] = Registry("runtime-plan-factories")
DEPLOYMENT_HOOK_FACTORIES: Registry[DeploymentHookFactory] = Registry("deployment-hook-factories")
MODEL_FAMILY_FACTORIES: Registry[ModelFamilyFactory] = Registry("model-family-factories")

BATCH_ADAPTER_FACTORIES.register(
    "test_double_batch_v1",
    lambda action_horizon, action_dim: TestDoubleBatchAdapter(
        action_horizon=action_horizon,
        action_dim=action_dim,
    ),
)
POLICY_FACTORIES.register(
    "deterministic_test_policy_v1", lambda seed: DeterministicTestPolicy(seed=seed)
)
LOSS_FACTORIES.register("masked_action_mse_v1", MaskedActionMseAdapter)
CHECKPOINT_FACTORIES.register("manifest_only_v1", ManifestOnlyCheckpointAdapter)
RUNTIME_PLAN_FACTORIES.register(
    "local_cpu_dry_run_v1",
    lambda: RuntimePlan(mode="local_cpu_smoke"),
)
DEPLOYMENT_HOOK_FACTORIES.register("disabled_deployment_v1", DisabledDeploymentHook)
for _model_key in ("test_double", "gr00t_n1d6_metadata", "pi0_metadata", "pi05_metadata"):
    MODEL_FAMILY_FACTORIES.register(
        _model_key,
        cast(ModelFamilyFactory, lambda key=_model_key: get_model_family_spec(key)),
    )


def create_batch_adapter(key: str, *, action_horizon: int, action_dim: int) -> BatchAdapter:
    """构造并校验规范 BatchAdapter 产品。"""
    product = cast(object, BATCH_ADAPTER_FACTORIES.get(key)(action_horizon, action_dim))
    if not isinstance(product, BatchAdapter):
        raise TypeError(f"batch adapter factory {key!r} returned a non-BatchAdapter product")
    return product


def create_action_policy(key: str, *, seed: int) -> ActionPolicy:
    """构造并校验规范 ActionPolicy 产品。"""
    product = cast(object, POLICY_FACTORIES.get(key)(seed))
    if not isinstance(product, ActionPolicy):
        raise TypeError(f"policy factory {key!r} returned a non-ActionPolicy product")
    return product


def create_loss_adapter(key: str) -> LossAdapter:
    """构造并校验规范 LossAdapter 产品。"""
    product = cast(object, LOSS_FACTORIES.get(key)())
    if not isinstance(product, LossAdapter):
        raise TypeError(f"loss factory {key!r} returned a non-LossAdapter product")
    return product


def create_checkpoint_adapter(key: str) -> CheckpointAdapter:
    """构造并校验规范 CheckpointAdapter 产品。"""
    product = cast(object, CHECKPOINT_FACTORIES.get(key)())
    if not isinstance(product, CheckpointAdapter):
        raise TypeError(f"checkpoint factory {key!r} returned a non-CheckpointAdapter product")
    return product


__all__ = [
    "BATCH_ADAPTER_FACTORIES",
    "CHECKPOINT_FACTORIES",
    "DEPLOYMENT_HOOK_FACTORIES",
    "LOSS_FACTORIES",
    "MODEL_FAMILY_FACTORIES",
    "POLICY_FACTORIES",
    "RUNTIME_PLAN_FACTORIES",
    "DisabledDeploymentHook",
    "create_action_policy",
    "create_batch_adapter",
    "create_checkpoint_adapter",
    "create_loss_adapter",
]
