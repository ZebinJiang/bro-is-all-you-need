"""GR00T processor 的 R3 共享计划与四步动作契约测试。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest

if TYPE_CHECKING:
    from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import (
        LocalEagleProcessor,
    )

torch = pytest.importorskip("torch", reason="GR00T processor contract requires torch")
pytest.importorskip(
    "transformers", reason="local reviewed Eagle processor type requires transformers"
)

semantics = import_module("autovla.core.semantics")
training_types = import_module("autovla.core.types.training")
normalization = import_module("autovla.data.normalization")
relative_actions = import_module("autovla.models.components.relative_actions")
config_module = import_module("autovla.models.families.gr00t_n1d6.config")
processor_module = import_module("autovla.models.families.gr00t_n1d6.processor")

AlignmentMode = semantics.AlignmentMode
AlignmentPolicy = semantics.AlignmentPolicy
TensorLayout = semantics.TensorLayout
TrainingBatch = training_types.TrainingBatch
ConstantFeaturePolicy = normalization.ConstantFeaturePolicy
FeatureStatistics = normalization.FeatureStatistics
RelativeActionKind = relative_actions.RelativeActionKind
RelativeActionPolicy = relative_actions.RelativeActionPolicy
EmbodimentStatistics = config_module.EmbodimentStatistics
Gr00tN1d6Config = config_module.Gr00tN1d6Config
Gr00tN1d6Processor = processor_module.Gr00tN1d6Processor


class _FakeEagleProcessor:
    """仅提供 tokenizer 输出形状,不参与数值变换测试。"""

    def encode(
        self,
        texts: tuple[str, ...],
        *,
        image_count_per_sample: int,
        visual_tokens_per_image: int,
        device: torch.device,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """返回一个文本 token 和声明数量的视觉 token。"""

        length = 1 + image_count_per_sample * visual_tokens_per_image
        return (
            torch.zeros((len(texts), length), dtype=torch.long, device=device),
            torch.ones((len(texts), length), dtype=torch.bool, device=device),
        )


def _statistics():
    """构造物理 ``[29]`` 与 ``[16,29]`` R3 统计。"""

    common = {
        "constant_feature_policy": ConstantFeaturePolicy.IDENTITY,
        "alignment": AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES),
    }
    state = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.feature(),
        mean=np.zeros(29, dtype=np.float32),
        std=np.ones(29, dtype=np.float32),
        **common,
    )
    action = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.feature(),
        mean=np.zeros(29, dtype=np.float32),
        std=np.ones(29, dtype=np.float32),
        **common,
    )
    relative = FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.time_feature(),
        mean=np.zeros((16, 29), dtype=np.float32),
        std=np.ones((16, 29), dtype=np.float32),
        constant_feature_policy=ConstantFeaturePolicy.IDENTITY,
        alignment=AlignmentPolicy(AlignmentMode.EXACT),
    )
    return EmbodimentStatistics(
        state=state,
        action=action,
        relative_action=relative,
        relative_action_policies=(RelativeActionPolicy(RelativeActionKind.JOINT, 0, 0, 29),),
        state_modality_order=("joint_state",),
        action_modality_order=("joint_action",),
        relative_action_modality_order=("joint_action",),
        state_clip=False,
        action_clip=False,
        relative_action_clip=False,
        source_fingerprint="fixture-r3-axis-aware",
    )


def _config():
    """构造官方 envelope 与物理 29 维统计的 processor 配置。"""

    return Gr00tN1d6Config(
        embodiment_ids={"fixture": 0},
        statistics={"fixture": _statistics()},
        use_relative_actions=True,
    )


def _batch():
    """构造真实物理 ``[B,16,29]`` joint 动作 fixture。"""

    state = np.arange(1.0, 30.0, dtype=np.float32)[None, :]
    relative = np.tile(np.arange(3.0, 32.0, dtype=np.float32), (16, 1))
    actions = relative[None, ...] + state[:, None, :]
    mask = np.ones_like(actions, dtype=np.bool_)
    mask[:, -1, -1] = False
    images = {
        name: np.zeros((1, 8, 8, 3), dtype=np.uint8)
        for name in ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")
    }
    return TrainingBatch(
        images=images,
        language=("Move arm.",),
        actions=actions,
        action_mask=mask,
        state=state,
        embodiment=("fixture",),
        sample_source=({"sample_id": "fixture-0"},),
        dataset_fingerprint="dataset",
        transform_fingerprint="physical",
        statistics_fingerprint="fixture-r3-axis-aware",
    )


def test_processor_uses_shared_r3_plan_for_relative_normalize_padding_and_mask() -> None:
    """R3 计划把物理 ``[16,29]`` 填充到官方 ``[50,128]``。"""

    processor = Gr00tN1d6Processor(
        _config(),
        cast("LocalEagleProcessor", _FakeEagleProcessor()),
        visual_tokens_per_image=1,
    )
    batch = _batch()
    prepared = processor.prepare_batch(
        batch,
        device=torch.device("cpu"),
        dtype=torch.float32,
        training=False,
    )
    assert prepared.state.shape == (1, 1, 128)
    assert prepared.actions is not None and prepared.actions.shape == (1, 50, 128)
    assert prepared.action_mask is not None
    assert prepared.action_mask.shape == (1, 50, 128)
    assert prepared.action_mask.dtype == torch.bool
    expected_relative = torch.as_tensor(batch.actions - batch.state[:, None, :])
    torch.testing.assert_close(prepared.actions[:, :16, :29], expected_relative)
    assert bool((prepared.state[:, :, 29:] == 0).all())
    assert bool((prepared.actions[:, 16:, :] == 0).all())
    assert bool((prepared.actions[:, :16, 29:] == 0).all())
    assert not bool(prepared.action_mask[:, 16:, :].any())
    assert not bool(prepared.action_mask[:, :16, 29:].any())
    assert int(prepared.action_mask.sum()) == int(batch.action_mask.sum())
    assert prepared.physical_action_shapes == ((16, 29),)
    stage_names = tuple(stage.name for stage in prepared.transform_plans[0].stages)
    assert stage_names == (
        "relative_action",
        "normalize_state",
        "normalize_actions",
        "pad_state",
        "pad_actions",
        "compose_action_mask",
    )
    assert prepared.metadata["normalization"] == "r3_axis_aware_per_embodiment"


def test_processor_inverse_plan_restores_physical_actions_without_fallback() -> None:
    """逆计划按原始 ``[T,D]`` 恢复动作并保留严格 mask。"""

    processor = Gr00tN1d6Processor(
        _config(),
        cast("LocalEagleProcessor", _FakeEagleProcessor()),
        visual_tokens_per_image=1,
    )
    original = _batch()
    prepared = processor.prepare_batch(
        original,
        device=torch.device("cpu"),
        dtype=torch.float32,
        training=False,
    )
    assert prepared.actions is not None
    prediction = processor.decode_actions(prepared.actions, batch=prepared)
    assert prediction.decoded_actions is not None
    expected = torch.as_tensor(original.actions).masked_fill(
        ~torch.as_tensor(original.action_mask), 0.0
    )
    torch.testing.assert_close(prediction.decoded_actions[:, :16, :29], expected)
    assert bool((prediction.decoded_actions[:, 16:, :] == 0).all())
    assert bool((prediction.decoded_actions[:, :16, 29:] == 0).all())


def test_official_config_fixes_four_euler_steps_and_rejects_dimension_drift() -> None:
    """官方配置固定 50/128/128,缩小运行仍固定 16/8/8。"""

    config = Gr00tN1d6Config()
    assert (
        config.action_horizon,
        config.max_state_dim,
        config.max_action_dim,
        config.num_inference_steps,
    ) == (50, 128, 128, 4)
    with pytest.raises(ValueError, match="pinned architecture mismatch"):
        Gr00tN1d6Config(action_horizon=16)
    reduced = Gr00tN1d6Config.reduced_runtime(eagle_asset_path="local-reduced-eagle")
    assert (reduced.action_horizon, reduced.max_state_dim, reduced.max_action_dim) == (16, 8, 8)


def test_joint_compatibility_policy_exposes_r3_stage_identity() -> None:
    """model-side joint policy 仅转换为 R3 stage,不保留第二套定义。"""

    policy = RelativeActionPolicy(RelativeActionKind.JOINT, 2, 4, 3)
    stage = policy.to_r3_stage()
    assert stage.action_dimensions == (2, 3, 4)
    assert stage.state_indices == (4, 5, 6)
    assert stage.state_feature == "reference_state"
