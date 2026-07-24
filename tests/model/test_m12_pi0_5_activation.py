"""M12 Pi0.5 家族私有源码面和激活阻塞测试。"""

# ruff: noqa: RUF002

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.conversion import OFFICIAL_PI05_CONVERSION_PLAN
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.normalization import (
    Pi05FeatureReceipt,
    Pi05IdentitySemanticTransform,
    Pi05NormalizationReceipt,
    Pi05SemanticNormalizationPlan,
)
from autovla.models.families.pi0_5.processor import Pi05Processor
from autovla.models.families.pi0_5.source_map import (
    OPENPI_REVISION,
    PI05_SOURCE_MAP_FINGERPRINT,
    PI05_SOURCE_RECEIPTS,
)
from autovla.models.families.specification import RuntimeSupportState

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "tests/model/oracles/pi0_5/source_surface.json"


class _RecordingTokenizer:
    """记录官方 prompt 文本并返回固定本地 token。"""

    def __init__(self) -> None:
        """初始化空调用记录。"""

        self.calls: list[tuple[str, bool]] = []

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        """记录编码输入，不读取 tokenizer 资产。"""

        self.calls.append((text, add_special_tokens))
        return [1, 2, 3]


def _features(prefix: str, count: int) -> tuple[Pi05FeatureReceipt, ...]:
    """构造有序、显式的测试物理特征。"""

    return tuple(
        Pi05FeatureReceipt(
            name=f"{prefix}_{index}",
            unit="rad",
            frame="robot_base",
            source=f"observation/{prefix}/{index}",
        )
        for index in range(count)
    )


def _plan(*, state_width: int = 2, action_width: int = 2) -> Pi05SemanticNormalizationPlan:
    """构造恒等语义和对称 quantile 的测试计划。"""

    transform = Pi05IdentitySemanticTransform()
    receipt = Pi05NormalizationReceipt(
        embodiment="test_arm",
        state_features=_features("state", state_width),
        action_features=_features("action", action_width),
        statistics_source="verified-local-norm-stats.json",
        statistics_fingerprint="a" * 64,
        semantic_transform_id=transform.identity,
    )
    return Pi05SemanticNormalizationPlan(
        receipt=receipt,
        state_q01=np.full(state_width, -1.0, dtype=np.float32),
        state_q99=np.full(state_width, 1.0, dtype=np.float32),
        action_q01=np.zeros(action_width, dtype=np.float32),
        action_q99=np.full(action_width, 2.0, dtype=np.float32),
        semantic_transform=transform,
    )


def test_source_oracle_binds_exact_paths_symbols_blobs_and_conversion_manifest() -> None:
    """源码 oracle 必须绑定固定提交、全部 blob 和完整转换计数。"""

    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
    receipts = {item.upstream_path: item.git_blob for item in PI05_SOURCE_RECEIPTS}
    assert oracle["revision"] == OPENPI_REVISION
    assert oracle["source_map_fingerprint"] == PI05_SOURCE_MAP_FINGERPRINT
    assert oracle["blobs"] == receipts
    assert OFFICIAL_PI05_CONVERSION_PLAN.source_leaf_count == 51
    assert OFFICIAL_PI05_CONVERSION_PLAN.logical_rule_count == 55
    assert OFFICIAL_PI05_CONVERSION_PLAN.destination_tensor_count == 811
    assert OFFICIAL_PI05_CONVERSION_PLAN.manifest_identity == oracle["conversion_manifest_identity"]
    with pytest.raises((AttributeError, TypeError)):
        OFFICIAL_PI05_CONVERSION_PLAN.rules += ()  # type: ignore[misc]


def test_normalization_receipt_binds_order_units_frames_source_and_values() -> None:
    """归一化计划身份必须覆盖有序语义、来源和冻结统计值。"""

    plan = _plan()
    assert tuple(item.name for item in plan.receipt.state_features) == (
        "state_0",
        "state_1",
    )
    assert tuple(item.unit for item in plan.receipt.action_features) == ("rad", "rad")
    assert tuple(item.frame for item in plan.receipt.action_features) == (
        "robot_base",
        "robot_base",
    )
    assert plan.receipt.statistics_source == "verified-local-norm-stats.json"
    assert len(plan.receipt.fingerprint) == len(plan.fingerprint) == 64
    with pytest.raises(ValueError, match="read-only"):
        plan.action_q01[0] = 3.0
    changed = Pi05SemanticNormalizationPlan(
        receipt=plan.receipt,
        state_q01=np.full(2, -1.0, dtype=np.float32),
        state_q99=np.full(2, 1.0, dtype=np.float32),
        action_q01=np.full(2, 0.25, dtype=np.float32),
        action_q99=np.full(2, 2.0, dtype=np.float32),
        semantic_transform=plan.semantic_transform,
    )
    assert changed.fingerprint != plan.fingerprint


def test_processor_uses_official_prompt_camera_fallback_resize_pad_and_masks() -> None:
    """无标签处理器必须复现官方 prompt、缺失相机和黑色 pad 行为。"""

    tokenizer = _RecordingTokenizer()
    processor = Pi05Processor(
        Pi05Config(action_horizon=4),
        tokenizer=tokenizer,
        normalization_plan=_plan(),
    )
    base = np.full((1, 2, 4, 3), 255, dtype=np.uint8)
    prepared = processor.prepare_observation(
        images={"base_0_rgb": base},
        image_masks=None,
        language=("pick_object\nnow",),
        state=np.array([[0.0, 1.0]], dtype=np.float32),
        embodiments=("test_arm",),
        sample_source=({"dataset": "fixture"},),
        physical_action_horizon=2,
        device=torch.device("cpu"),
        dtype=torch.float32,
    )
    prompt, add_special_tokens = tokenizer.calls[0]
    state_values = prompt.split("State: ", 1)[1].split(";\nAction:", 1)[0].split()
    assert prompt.startswith("Task: pick object now, State: 127 255 ")
    assert len(state_values) == 32
    assert state_values[2:] == ["128"] * 30
    assert add_special_tokens
    assert prepared.actions is None and prepared.action_mask is None
    assert prepared.input_ids.shape == (1, 200)
    assert prepared.attention_mask[0, :3].all()
    assert not prepared.attention_mask[0, 3:].any()
    masks = prepared.metadata["image_masks"]
    assert torch.equal(masks, torch.tensor([[True, False, False]]))
    assert all(image.shape == (1, 3, 224, 224) for image in prepared.images.values())
    assert torch.all(prepared.images["base_0_rgb"][:, :, :56] == -1)
    assert torch.all(prepared.images["base_0_rgb"][:, :, 56:168] == 1)
    assert torch.all(prepared.images["left_wrist_0_rgb"] == -1)


def test_float_images_remain_in_official_minus_one_to_one_space() -> None:
    """float 图像不得被误判为零到一后再次缩放。"""

    processor = Pi05Processor(Pi05Config(action_horizon=2), normalization_plan=_plan())
    image = np.zeros((1, 3, 224, 224), dtype=np.float32)
    prepared = processor._prepare_image(
        image,
        device=torch.device("cpu"),
        dtype=torch.float32,
        training=False,
    )
    assert torch.count_nonzero(prepared) == 0
    bad = np.full((1, 3, 224, 224), 1.1, dtype=np.float32)
    with pytest.raises(ValueError, match=r"\[-1,1\]"):
        processor._prepare_image(
            bad,
            device=torch.device("cpu"),
            dtype=torch.float32,
            training=False,
        )


def test_family_remains_activation_blocked_without_assets_terms_and_runtime() -> None:
    """源码面完成不得提升资产、checkpoint 或真实运行状态。"""

    requirements = PI05_SPEC.assembly_requirements
    assert PI05_SPEC.runtime_support is RuntimeSupportState.ASSET_REQUIRED
    assert requirements is not None
    assert requirements.checkpoint.conversion_required
    assert requirements.evidence.source_architecture_complete
    assert not requirements.evidence.official_checkpoint_load_validated
    assert not requirements.evidence.runtime_ready
    assert not requirements.evidence.inference_validated
    assert not requirements.evidence.single_gpu_validated
    assert PI05_SPEC.validation_status == (
        "official_source_alignment_static_pass_conversion_a100_oracle_and_runtime_deferred_"
        "pending_checkpoint_gemma_terms_and_exact_data_binding"
    )
    assert {item.role for item in requirements.assets} == {
        "checkpoint",
        "gemma_tokenizer",
        "normalization_statistics",
    }
