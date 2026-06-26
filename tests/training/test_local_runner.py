"""M3 本地运行器 smoke 契约测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import numpy as np
import pytest

from genesisvla.core.types import ActionMask, FrameworkOutput, ModelInput
from genesisvla.dataloader import CollatedBatch, collate_raw_samples_typed
from genesisvla.testing.fixtures import TinyLeRobotFixture, tiny_lerobot_fixture
from genesisvla.training import (
    CheckpointManifest,
    DeterministicActionFramework,
    LocalRunner,
    LocalRunnerConfig,
    ResumeSpec,
    collated_batch_to_model_input,
    masked_action_mse,
    read_checkpoint_manifest,
    validate_action_mask,
    write_checkpoint_manifest,
)


def _tiny_batch(tmp_path: Path) -> tuple[TinyLeRobotFixture, CollatedBatch]:
    """返回 tiny fixture 的 typed batch。"""
    fixture = tiny_lerobot_fixture(tmp_path / "tiny_lerobot_v3")
    return fixture, collate_raw_samples_typed(fixture.samples)


def _statistics_fingerprint(fixture: TinyLeRobotFixture) -> str:
    """从 M2 统计量 JSON 表示中派生非空 checksum。"""
    checksum = fixture.statistics.to_json_dict()["checksum"]
    assert isinstance(checksum, str)
    assert checksum
    return checksum


def _action_mask_from_metadata(
    model_input: ModelInput,
    expected_shape: tuple[int, int, int],
) -> ActionMask:
    """从 ModelInput metadata 中收窄 action mask 类型。"""
    mask = model_input.metadata["action_mask"]
    assert isinstance(mask, np.ndarray)
    typed_mask = cast(ActionMask, mask)
    assert typed_mask.dtype == np.bool_
    assert typed_mask.shape == expected_shape
    return typed_mask


def test_adapter_should_preserve_collated_batch_fields(tmp_path: Path) -> None:
    """验证 CollatedBatch 会被无损映射到 ModelInput。"""
    fixture, batch = _tiny_batch(tmp_path)

    model_input = collated_batch_to_model_input(
        batch,
        dataset_fingerprint=fixture.statistics.dataset_fingerprint,
        transform_fingerprint=fixture.statistics.transform_fingerprint,
        statistics_fingerprint=_statistics_fingerprint(fixture),
        seed=17,
        epoch=2,
        worker_id=0,
        worker_count=1,
        rank=0,
        world_size=1,
    )

    assert isinstance(model_input, ModelInput)
    assert model_input.batch.batch_size == batch.batch_size
    assert model_input.tensors["actions"].shape == (2, 2, 3)
    assert model_input.tensors["action_horizon"].tolist() == [2, 2]
    assert model_input.tensors["action_dim"].tolist() == [3, 3]
    assert model_input.metadata["dataset_fingerprint"] == fixture.statistics.dataset_fingerprint
    assert model_input.metadata["transform_fingerprint"] == fixture.statistics.transform_fingerprint
    assert model_input.metadata["seed"] == 17
    assert model_input.metadata["epoch"] == 2
    _action_mask_from_metadata(model_input, (2, 2, 3))
    assert model_input.batch.samples[0].language == batch.language[0]
    assert model_input.batch.samples[0].robot_tag == batch.robot_tag[0]
    assert model_input.batch.samples[0].metadata["sample_source"]["dataset"] == "tiny-generated"


def test_masked_action_loss_should_ignore_padding_and_reject_bad_masks() -> None:
    """验证 masked loss 只统计 bool mask 标记的有效动作。"""
    target = np.asarray([[[2.0, 4.0, 99.0], [6.0, 8.0, 99.0]]], dtype=np.float32)
    prediction = np.asarray([[[1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]], dtype=np.float32)
    mask = np.asarray([[[True, True, False], [True, False, False]]], dtype=np.bool_)

    loss = masked_action_mse(prediction, target, mask)

    assert loss.valid_count == 3
    assert loss.value == pytest.approx(((1.0**2) + (3.0**2) + (5.0**2)) / 3.0)
    with pytest.raises(TypeError, match="action_mask"):
        validate_action_mask(np.asarray([[[1, 0, 1], [1, 0, 0]]]), target.shape)
    with pytest.raises(ValueError, match="valid action"):
        masked_action_mse(prediction, target, np.zeros_like(mask))


def test_checkpoint_manifest_should_roundtrip_and_validate_resume(tmp_path: Path) -> None:
    """验证 checkpoint manifest 可往返并拒绝不兼容恢复。"""
    manifest = CheckpointManifest(
        run_id="debug-run",
        step=3,
        epoch=1,
        model_registry_key="deterministic-test-framework",
        runner_config={"max_steps": 3, "seed": 7},
        dataset_fingerprint="dataset-a",
        transform_fingerprint="transform-a",
        statistics_fingerprint="stats-a",
        action_horizon=(2,),
        action_dim=(3,),
        mask_shape=(1, 2, 3),
        valid_action_elements=4,
        sample_source=({"dataset": "tiny-generated", "sample_key": "episode-0"},),
        metrics={"masked_action_mse": 1.25},
    )
    path = tmp_path / "checkpoint" / "manifest.json"

    write_checkpoint_manifest(path, manifest)
    loaded = read_checkpoint_manifest(path)

    assert loaded == manifest
    assert (
        loaded.validate_resume(
            ResumeSpec(
                model_registry_key="deterministic-test-framework",
                dataset_fingerprint="dataset-a",
                transform_fingerprint="transform-a",
                statistics_fingerprint="stats-a",
            )
        )
        == 3
    )
    with pytest.raises(ValueError, match="dataset_fingerprint"):
        loaded.validate_resume(
            ResumeSpec(
                model_registry_key="deterministic-test-framework",
                dataset_fingerprint="dataset-b",
                transform_fingerprint="transform-a",
                statistics_fingerprint="stats-a",
            )
        )


def test_deterministic_framework_should_return_masked_loss(tmp_path: Path) -> None:
    """验证测试框架输出确定性 masked action loss。"""
    fixture, batch = _tiny_batch(tmp_path)
    model_input = collated_batch_to_model_input(
        batch,
        dataset_fingerprint=fixture.statistics.dataset_fingerprint,
        transform_fingerprint=fixture.statistics.transform_fingerprint,
        statistics_fingerprint=_statistics_fingerprint(fixture),
    )
    framework = DeterministicActionFramework(prediction_value=1.0)

    output = framework.forward(model_input)
    action = framework.predict_action(model_input)

    assert isinstance(output, FrameworkOutput)
    assert output.loss == output.losses["action"]
    assert output.metrics["batch_size"] == 2.0
    assert output.metrics["valid_action_elements"] == 8.0
    assert action.values.shape == (2, 3)
    assert action.mask is not None
    assert action.normalized is True


def test_local_runner_config_should_reject_empty_statistics_fingerprint(
    tmp_path: Path,
) -> None:
    """验证 runner 配置继续拒绝空 statistics fingerprint。"""
    with pytest.raises(ValueError, match="statistics_fingerprint"):
        LocalRunnerConfig(
            run_id="tiny-run",
            run_root=tmp_path / "runs",
            max_steps=2,
            seed=11,
            model_registry_key="deterministic-test-framework",
            dataset_fingerprint="dataset-a",
            transform_fingerprint="transform-a",
            statistics_fingerprint="",
        )


def test_local_runner_config_should_reject_non_int_seed(tmp_path: Path) -> None:
    """验证 runner 配置拒绝动态传入的非 int seed。"""
    bad_seeds = (True, "11")
    for bad_seed in bad_seeds:
        with pytest.raises(TypeError, match="seed"):
            LocalRunnerConfig(
                run_id="tiny-run",
                run_root=tmp_path / "runs",
                max_steps=2,
                seed=cast(int, bad_seed),
                model_registry_key="deterministic-test-framework",
                dataset_fingerprint="dataset-a",
                transform_fingerprint="transform-a",
                statistics_fingerprint="stats-a",
            )


def test_local_runner_should_train_evaluate_checkpoint_and_resume(tmp_path: Path) -> None:
    """验证 CPU-only local runner 完成 deterministic smoke。"""
    fixture, batch = _tiny_batch(tmp_path)
    config = LocalRunnerConfig(
        run_id="tiny-run",
        run_root=tmp_path / "runs",
        max_steps=2,
        seed=11,
        model_registry_key="deterministic-test-framework",
        dataset_fingerprint=fixture.statistics.dataset_fingerprint,
        transform_fingerprint=fixture.statistics.transform_fingerprint,
        statistics_fingerprint=_statistics_fingerprint(fixture),
    )
    runner = LocalRunner(
        config=config,
        framework=DeterministicActionFramework(prediction_value=1.0),
        batches=(batch,),
    )

    runner.setup()
    train_metrics = runner.train()
    eval_metrics = runner.evaluate()
    checkpoint_path = runner.save_checkpoint(2)
    resumed_step = runner.resume(checkpoint_path)

    assert train_metrics["step"] == 2.0
    assert train_metrics["masked_action_mse"] == eval_metrics["masked_action_mse"]
    assert checkpoint_path == tmp_path / "runs" / "tiny-run" / "checkpoints" / "step-2.json"
    assert checkpoint_path.is_file()
    assert resumed_step == 2
    assert read_checkpoint_manifest(checkpoint_path).sample_source[0]["dataset"] == "tiny-generated"
