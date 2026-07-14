"""M4 配置驱动模块化 runner 集成测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from autovla.config.loader import load_yaml
from autovla.core.types import ModelInput, NumericArray
from autovla.training.contracts import ActionPolicy, LossAdapter
from autovla.training.losses import MaskedActionLoss
from autovla.training.registry import create_action_policy, create_loss_adapter
from autovla.training.runner import run_modular_training_dry_run
from autovla.training.state import TrainingState


def _config(backend: str):
    """加载规范 preset 并允许显式后端覆盖。"""
    return load_yaml(
        "configs/training/modular_skeleton_webdataset.yaml",
        overrides=(f"data.backend={backend}",),
    )


def _payload(path: Path) -> dict[str, object]:
    """读取稳定 JSON object。"""
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_moves_should_preserve_import_identity() -> None:
    """验证旧 Training 路径与新 Core 路径指向同一对象。"""
    from autovla.core.runtime import EnvProfile as CoreEnvProfile
    from autovla.core.runtime import RuntimePlan as CoreRuntimePlan
    from autovla.core.types.training import TrainingBatch as CoreTrainingBatch
    from autovla.training.contracts import TrainingBatch
    from autovla.training.runtime import EnvProfile, RuntimePlan

    assert TrainingBatch is CoreTrainingBatch
    assert RuntimePlan is CoreRuntimePlan
    assert EnvProfile is CoreEnvProfile


@pytest.mark.parametrize("metric", ("1.0", True, object()))
def test_training_state_rejects_non_numeric_runtime_metrics(metric: float) -> None:
    """持久化指标拒绝数字字符串、bool 和任意对象。"""

    with pytest.raises(TypeError, match="accumulated_loss must be an int or float"):
        TrainingState(accumulated_loss=metric)
    with pytest.raises(TypeError, match="best_metric must be an int or float"):
        TrainingState(best_metric=metric)


def test_both_backends_should_execute_same_runner_path(tmp_path: Path) -> None:
    """验证双后端两步输出在规范批、损失和 mask 统计上等价。"""
    results = [
        run_modular_training_dry_run(_config(backend), output_dir=tmp_path / backend)
        for backend in ("webdataset_tar", "robodm_container_v1")
    ]
    manifests = [_payload(result.manifest_path) for result in results]

    assert [result.backend_key for result in results] == [
        "webdataset_tar",
        "robodm_container_v1",
    ]
    assert all(result.step_count == 2 for result in results)
    assert results[0].canonical_batch_fingerprints == results[1].canonical_batch_fingerprints
    assert manifests[0]["losses"] == manifests[1]["losses"]
    assert manifests[0]["valid_action_elements"] == manifests[1]["valid_action_elements"]
    assert manifests[0]["model_metadata_key"] == "test_double"
    assert manifests[1]["native_compatible"] is False
    assert all(manifest["weights_written"] is False for manifest in manifests)


def test_modular_runner_should_predict_before_external_loss_once_per_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 runner 每步先预测再调用一次外部损失。"""
    policy = create_action_policy("deterministic_test_policy_v1", seed=11)
    loss_adapter = create_loss_adapter("masked_action_mse_v1")
    policy_type = type(policy)
    loss_type = type(loss_adapter)
    original_predict = policy_type.predict_actions
    original_compute = loss_type.compute
    calls: list[str] = []

    def predict_spy(self: ActionPolicy, batch: ModelInput) -> NumericArray:
        """记录规范策略产品的预测调用并转发。"""
        calls.append("predict")
        return original_predict(self, batch)

    def loss_spy(
        self: LossAdapter,
        prediction: object,
        target: object,
        action_mask: object,
    ) -> MaskedActionLoss:
        """记录规范损失产品的调用并转发。"""
        calls.append("loss")
        return original_compute(self, prediction, target, action_mask)

    monkeypatch.setattr(policy_type, "predict_actions", predict_spy)
    monkeypatch.setattr(loss_type, "compute", loss_spy)

    result = run_modular_training_dry_run(
        _config("webdataset_tar"),
        output_dir=tmp_path / "spy",
    )

    assert result.step_count == 2
    assert calls == ["predict", "loss", "predict", "loss"]


def test_modular_runner_should_fail_closed_before_heavy_runtime(tmp_path: Path) -> None:
    """验证 metadata-only 模型、部署和未知后端无法执行。"""
    loaded_before = set(sys.modules)
    with pytest.raises(ValueError, match="metadata-only"):
        run_modular_training_dry_run(
            load_yaml(
                "configs/training/modular_skeleton_webdataset.yaml",
                overrides=("model.registry_key=gr00t_n1d6_metadata",),
            ),
            output_dir=tmp_path / "model",
        )
    with pytest.raises(ValueError, match=r"deployment\.enabled"):
        run_modular_training_dry_run(
            load_yaml(
                "configs/training/modular_skeleton_webdataset.yaml",
                overrides=("deployment.enabled=true",),
            ),
            output_dir=tmp_path / "deployment",
        )
    with pytest.raises(ValueError, match=r"unknown data\.backend"):
        _config("missing")
    newly_loaded = set(sys.modules) - loaded_before
    for name in ("torch", "transformers", "gr00t", "jax", "flax", "openpi", "wandb"):
        assert name not in newly_loaded
