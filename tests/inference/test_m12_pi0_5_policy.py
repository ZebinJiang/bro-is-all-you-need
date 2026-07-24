"""M12 Pi0.5 无标签策略会话的聚焦测试。"""

# ruff: noqa: RUF002

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.factory import Pi05ModelFactory
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.normalization import (
    Pi05FeatureReceipt,
    Pi05IdentitySemanticTransform,
    Pi05NormalizationReceipt,
    Pi05SemanticNormalizationPlan,
)
from autovla.models.families.pi0_5.policy import (
    Pi05InferenceRequest,
    Pi05PolicyBundle,
)
from autovla.models.outputs import ActionPrediction, ModelInputBatch
from autovla.models.readiness import (
    DeepSpeedStage,
    DistributedStrategyKind,
    PrecisionMode,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeOperation,
    RuntimeTopology,
    RuntimeValidationKey,
)


def _plan() -> Pi05SemanticNormalizationPlan:
    """构造两维动作的恒等语义计划。"""

    transform = Pi05IdentitySemanticTransform()
    features = tuple(
        Pi05FeatureReceipt(f"joint_{index}", "rad", "robot_base", f"joint/{index}")
        for index in range(2)
    )
    receipt = Pi05NormalizationReceipt(
        embodiment="test_arm",
        state_features=features,
        action_features=features,
        statistics_source="verified-local-norm-stats.json",
        statistics_fingerprint="a" * 64,
        semantic_transform_id=transform.identity,
    )
    return Pi05SemanticNormalizationPlan(
        receipt=receipt,
        state_q01=np.full(2, -1.0, dtype=np.float32),
        state_q99=np.full(2, 1.0, dtype=np.float32),
        action_q01=np.array([10.0, 20.0], dtype=np.float32),
        action_q99=np.array([12.0, 24.0], dtype=np.float32),
        semantic_transform=transform,
    )


def _runtime_evidence(
    operation: RuntimeOperation = RuntimeOperation.PREDICTION,
) -> RuntimeEvidenceReceipt:
    """构造完整且通过的测试运行身份。"""

    key = RuntimeValidationKey(
        family_key="pi0_5",
        definition_fingerprint=PI05_SPEC.fingerprint,
        operation=operation,
        runtime_profile_fingerprint="1" * 64,
        runtime_lock_fingerprint="2" * 64,
        environment_fingerprint="3" * 64,
        asset_fingerprint="4" * 64,
        checkpoint_fingerprint="5" * 64,
        data_binding_fingerprint="6" * 64,
        data_backend="canonical_batch",
        source_sha="7" * 40,
        command_fingerprint="8" * 64,
        evidence_artifact_fingerprint="9" * 64,
        strategy=DistributedStrategyKind.SINGLE_GPU,
        deepspeed_stage=DeepSpeedStage.NONE,
        topology=RuntimeTopology(1, 1, 1, "h800"),
        precision=PrecisionMode.BF16,
    )
    return RuntimeEvidenceReceipt(
        receipt_id=f"pi05-{operation.value}",
        validation_key=key,
        evidence_kind=RuntimeEvidenceKind.RUNTIME,
        artifact_fingerprint="9" * 64,
        passed=True,
    )


class _FakeProcessor:
    """实现无标签会话所需的最小处理器协议。"""

    def __init__(self, plan: Pi05SemanticNormalizationPlan) -> None:
        """绑定测试配置和计划。"""

        self.config = Pi05Config(action_horizon=4)
        self.normalization_plan = plan
        self.fingerprint = "processor-fixture"
        self.actions_seen = False

    def prepare_observation(self, **kwargs: object) -> ModelInputBatch:
        """返回不含动作字段的最小模型输入。"""

        state = np.asarray(kwargs["state"])
        batch_size = state.shape[0]
        tensor_state = torch.zeros((batch_size, 1, 32), dtype=torch.float32)
        return ModelInputBatch(
            images={
                name: torch.zeros((batch_size, 3, 1, 1), dtype=torch.float32)
                for name in (
                    "base_0_rgb",
                    "left_wrist_0_rgb",
                    "right_wrist_0_rgb",
                )
            },
            input_ids=torch.ones((batch_size, 1), dtype=torch.long),
            attention_mask=torch.ones((batch_size, 1), dtype=torch.bool),
            state=tensor_state,
            embodiment_ids=torch.zeros(batch_size, dtype=torch.long),
            camera_order=(
                "base_0_rgb",
                "left_wrist_0_rgb",
                "right_wrist_0_rgb",
            ),
            metadata={"image_masks": torch.ones((batch_size, 3), dtype=torch.bool)},
        )


class _FakeModel:
    """返回固定归一化动作并记录输入中不存在训练标签。"""

    def __init__(self, config: Pi05Config) -> None:
        """保存共享配置。"""

        self.config = config
        self.labels_seen = False

    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """返回零归一化动作，验证 actions/action_mask 都为空。"""

        del generator
        self.labels_seen = batch.actions is not None or batch.action_mask is not None
        values = torch.zeros(
            (batch.batch_size, self.config.action_horizon, self.config.action_dimension),
            dtype=torch.float32,
        )
        return ActionPrediction(values, torch.ones_like(values, dtype=torch.bool))


def test_factory_policy_bundle_requires_explicit_verified_runtime_identity() -> None:
    """工厂只能从同一装配对象和显式真实运行收据构造策略包。"""

    plan = _plan()
    processor = _FakeProcessor(plan)
    model = _FakeModel(processor.config)
    result = SimpleNamespace(processor=processor, model=model)
    bundle = Pi05ModelFactory.build_policy_bundle(
        result,  # type: ignore[arg-type]
        verified_runtime_identity=_runtime_evidence(),
    )
    assert isinstance(bundle, Pi05PolicyBundle)
    assert bundle.normalization_plan is plan
    with pytest.raises(ValueError, match="prediction family"):
        Pi05ModelFactory.build_policy_bundle(
            result,  # type: ignore[arg-type]
            verified_runtime_identity=_runtime_evidence(RuntimeOperation.DECODE),
        )
    failed = replace(_runtime_evidence(), passed=False)
    with pytest.raises(ValueError, match="passed non-historical"):
        Pi05ModelFactory.build_policy_bundle(
            result,  # type: ignore[arg-type]
            verified_runtime_identity=failed,
        )


def test_session_runs_label_free_prepare_predict_decode_inverse_trim_and_evidence() -> None:
    """会话按固定五阶段输出物理动作并支持 reset/close。"""

    plan = _plan()
    processor = _FakeProcessor(plan)
    model = _FakeModel(processor.config)
    bundle = Pi05PolicyBundle(processor, model, plan, _runtime_evidence())
    session = bundle.new_session(device=torch.device("cuda"), dtype=torch.bfloat16)
    request = Pi05InferenceRequest(
        request_id="request-1",
        images={"base_0_rgb": np.zeros((1, 2, 2, 3), dtype=np.uint8)},
        language=("pick",),
        state=np.zeros((1, 2), dtype=np.float32),
        embodiment=("test_arm",),
        physical_action_horizon=2,
    )
    result = session.run(request)
    assert not model.labels_seen
    assert result.actions.shape == (1, 2, 2)
    np.testing.assert_allclose(
        result.actions,
        np.array([[[11.0, 22.0], [11.0, 22.0]]], dtype=np.float32),
        atol=2e-6,
    )
    assert result.evidence.steps == ("prepare", "predict", "decode", "inverse", "trim")
    assert session.evidence() is result.evidence
    session.reset()
    with pytest.raises(RuntimeError, match="no completed"):
        session.evidence()
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.prepare(request)


def test_inference_request_surface_contains_no_action_labels() -> None:
    """家族请求字段不得重新引入 actions 或 action_mask。"""

    fields = set(Pi05InferenceRequest.__dataclass_fields__)
    assert "actions" not in fields
    assert "action_mask" not in fields
