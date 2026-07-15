"""R5 resolved training plan 和生产遥测身份契约。"""

import io
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast, get_type_hints

import numpy as np
import pytest

import autovla.models.assembly as assembly_module
import autovla.training.plan as training_plan_module
from autovla.cli.train import _resolve_training_assembly
from autovla.config import ExperimentConfig
from autovla.core.types.training import TrainingBatch
from autovla.models.assembly import ModelAssemblyPlan, ModelAssemblyRequest
from autovla.training.plan import DataPlan, OptimizationPlan, TopologyPlan, TrainingPlan
from autovla.training.session import PreparedTrainingSession
from autovla.training.telemetry import DataTelemetryRecord
from autovla.training.telemetry.logger import MetricLogger


def test_plan_identity_and_active_topologies() -> None:
    """计划指纹覆盖数据身份, 且 ModelAssemblyPlan 是唯一 handoff 类型。"""
    data = DataPlan("manifest", ("source",), "mixture", "composition", "transform", "stats")
    assert (
        data.fingerprint
        == DataPlan(
            "manifest", ("source",), "mixture", "composition", "transform", "stats"
        ).fingerprint
    )
    assert get_type_hints(TrainingPlan)["model_assembly"] is ModelAssemblyPlan
    assert TopologyPlan("deepspeed_zero_3", 8, "bfloat16", 3).zero_stage == 3
    with pytest.raises(ValueError):
        TopologyPlan("fully_sharded", 2, "bfloat16")
    with pytest.raises(TypeError):
        DataPlan("manifest", cast(tuple[str, ...], ["source"]), "mix", "batch", "x", "s")
    with pytest.raises(ValueError):
        DataPlan("manifest", (), "mix", "batch", "x", "s")
    with pytest.raises(ValueError):
        OptimizationPlan("adamw", "cosine", "bfloat16", 1, cast(float, True), "fp")


def test_cli_composition_resolves_both_plans_from_same_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """可执行替身证明模型计划先解析,训练计划只消费该结果。"""
    events: list[tuple[str, object]] = []
    request = cast(ModelAssemblyRequest, object())
    config = cast(ExperimentConfig, object())
    model_plan = cast(ModelAssemblyPlan, object())
    training_plan = cast(TrainingPlan, object())

    def resolve_model(value: ModelAssemblyRequest, /) -> ModelAssemblyPlan:
        """记录规范装配请求并返回唯一模型计划。"""
        events.append(("model", value))
        return model_plan

    def resolve_training(
        value: ExperimentConfig,
        resolved_model_plan: ModelAssemblyPlan,
        /,
    ) -> TrainingPlan:
        """记录训练计划只消费同一配置和已解析模型计划。"""
        assert value is config
        events.append(("training", resolved_model_plan))
        return training_plan

    monkeypatch.setattr(assembly_module, "resolve_model_assembly", resolve_model)
    monkeypatch.setattr(training_plan_module, "resolve_training_plan", resolve_training)

    actual_model_plan, actual_training_plan = _resolve_training_assembly(config, request)

    assert actual_model_plan is model_plan
    assert actual_training_plan is training_plan
    assert events == [("model", request), ("training", model_plan)]


def test_checkpoint_path_binds_runtime_data_identity_for_save_and_resume() -> None:
    """生产 manager 在保存和恢复预验证前绑定真实数据兼容身份。"""
    source = Path("autovla/training/checkpointing/manager.py").read_text(encoding="utf-8")

    assert source.count("self._bind_runtime_data_identity(data_module)") == 2
    assert '"runtime_manifest": manifest.fingerprint' in source
    assert '"runtime_transform": manifest.transform_fingerprint' in source
    assert '"runtime_statistics": manifest.statistics_fingerprint' in source
    assert '"runtime_data_identity": runtime_identity' in source
    assert '"data_fingerprints": (manifest.data_fingerprints, self.data_fingerprints)' in source


def test_data_telemetry_contains_rank_source_and_valid_counts() -> None:
    """数据遥测同时携带 counts/weights/timing/rank/fingerprint。"""
    record = DataTelemetryRecord(
        rank=1,
        world_size=2,
        aggregate="rank_local",
        samples_by_dataset={"local": 4},
        batches_by_dataset={"local": 1},
        samples_by_embodiment={"arm": 4},
        batches_by_embodiment={"arm": 1},
        requested_weights={"local": 1.0},
        effective_weights={"local": 1.0},
        balance_deviations={"local": 0.0},
        skipped_by_reason={"decode": 0},
        data_wait_seconds=0.1,
        decode_seconds=0.2,
        collate_seconds=0.05,
        valid_image_elements=12,
        valid_token_elements=8,
        valid_action_elements=16,
        source_fingerprints=("source",),
        transform_fingerprint="transform",
    )
    assert record.to_dict()["valid_action_elements"] == 16
    assert record.fingerprint == record.fingerprint
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord(True, 2, "rank_local")
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord(0, 1, "rank_local", samples_by_dataset={"local": True})
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord(
            0,
            1,
            "rank_local",
            samples_by_dataset=cast(Mapping[str, int], {1: 1}),
        )
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord(0, 1, "rank_local", valid_action_elements=True)


def test_training_batch_telemetry_fingerprint_and_replay_are_deterministic() -> None:
    """canonical batch 生成 dataset/embodiment/valid/source 身份且可严格重放。"""
    batch = TrainingBatch(
        images={"camera.rgb_0": np.zeros((2, 3, 2, 2), dtype=np.float32)},
        language=("pick", "place"),
        actions=np.zeros((2, 2, 3), dtype=np.float32),
        action_mask=np.ones((2, 2, 3), dtype=np.bool_),
        sample_source=(
            {"dataset": "arm_a", "backend": "lerobot_local"},
            {"dataset": "arm_b", "backend": "lerobot_local"},
        ),
        dataset_fingerprint="manifest",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
        embodiment=("gr1", "gr1"),
        source_fingerprints=("source-a", "source-b"),
    )
    record = DataTelemetryRecord.from_training_batch(
        batch,
        rank=0,
        world_size=2,
        fallback_dataset="configured",
        requested_weights={"arm_a": 0.5, "arm_b": 0.5},
        planned_source_fingerprints=("planned",),
        valid_image_elements=24,
        valid_token_elements=5,
        valid_action_elements=12,
    )
    replayed = DataTelemetryRecord.from_dict(record.to_dict())

    assert replayed == record
    assert replayed.fingerprint == record.fingerprint
    assert replayed.samples_by_dataset == {"arm_a": 1, "arm_b": 1}
    assert replayed.samples_by_embodiment == {"gr1": 2}
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord.from_dict({**record.to_dict(), "rank": True})
    with pytest.raises((TypeError, ValueError)):
        DataTelemetryRecord.from_training_batch(
            batch,
            rank=0,
            world_size=2,
            fallback_dataset="configured",
            requested_weights={"arm_a": True},
            planned_source_fingerprints=("planned",),
            valid_image_elements=24,
            valid_token_elements=5,
            valid_action_elements=12,
        )


class _TelemetrySession:
    """模拟两 rank 已有 collect API,不实现训练或优化器行为。"""

    rank = 0
    world_size = 2

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]]:
        """返回两个同配置 rank 的可审计遥测载荷。"""
        raw_record = local_state["data_telemetry"]
        if not isinstance(raw_record, Mapping):
            raise TypeError("test telemetry payload must contain a mapping")
        first = DataTelemetryRecord.from_dict(cast(Mapping[str, object], raw_record))
        second = replace(first, rank=1)
        return {
            "0": dict(local_state),
            "1": {
                **local_state,
                "rank": 1,
                "data_telemetry": second.to_dict(),
            },
        }


def test_metric_logger_applies_configured_cross_rank_data_reduction_and_resume() -> None:
    """logger checkpoint pending 队列并通过既有 session collective 输出 reduced 记录。"""
    stream = io.StringIO()
    logger = MetricLogger(stdout=True, stream=stream)
    record = DataTelemetryRecord(
        rank=0,
        world_size=2,
        aggregate="rank_local",
        samples_by_dataset={"local": 2},
        batches_by_dataset={"local": 1},
        requested_weights={"local": 1.0},
        effective_weights={"local": 1.0},
        balance_deviations={"local": 0.0},
        data_wait_seconds=0.25,
        valid_action_elements=6,
        source_fingerprints=("source",),
        transform_fingerprint="transform",
    )
    logger.queue_data_telemetry(record)
    checkpoint_state = logger.state_dict()
    replay = MetricLogger(stdout=True, stream=stream)
    replay.load_state_dict(checkpoint_state)
    replay.flush_data_telemetry(
        cast(PreparedTrainingSession, _TelemetrySession()),
        reduce_across_ranks=True,
    )
    payload = json.loads(stream.getvalue().splitlines()[-1])

    assert payload["event"] == "data_telemetry"
    assert payload["aggregate"] == "reduced_sum"
    assert payload["samples_by_dataset"] == {"local": 4}
    assert payload["data_wait_seconds"] == 0.5
    assert payload["valid_action_elements"] == 12
    assert replay.state_dict()["pending_data_telemetry"] == []
