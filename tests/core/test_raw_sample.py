"""AutoVLA 原始样本契约测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from autovla.core.types.sample import BatchSample, RawSample


def _legacy_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "images": {
            "front": np.zeros((4, 4, 3), dtype=np.uint8),
            "wrist": np.ones((2, 2, 3), dtype=np.uint8),
        },
        "instruction": "pick up the block",
        "actions": np.zeros((2, 7), dtype=np.float32),
        "state": np.zeros((7,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-000"},
    }
    payload.update(overrides)
    return payload


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.zeros((2, 7), dtype=np.float32),
        "state": np.zeros((7,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-direct"},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_create_raw_sample_from_legacy_dict() -> None:
    """验证旧字典能转换为 RawSample 且核心字段被保留。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict
    from autovla.core.types.sample import RawSample

    sample = from_legacy_dict(_legacy_payload())

    assert isinstance(sample, RawSample)
    assert sample.language == "pick up the block"
    assert set(sample.images) == {"front", "wrist"}
    assert sample.actions is not None
    assert sample.actions.shape == (2, 7)
    assert sample.state is not None
    assert sample.state.shape == (7,)
    assert sample.robot_tag == "debug-arm"
    assert sample.metadata["episode_id"] == "ep-000"


def test_raw_sample_should_own_array_copies_and_mark_them_readonly() -> None:
    """验证 RawSample 复制数组输入并将内部数组设为只读。"""
    image = np.zeros((2, 2, 3), dtype=np.uint8)
    actions = np.zeros((2, 7), dtype=np.float32)
    state = np.zeros((7,), dtype=np.float32)

    sample = _raw_sample(images={"front": image}, actions=actions, state=state)
    image[0, 0, 0] = 255
    actions[0, 0] = 99.0
    state[0] = 11.0

    assert sample.images["front"][0, 0, 0] == 0
    assert sample.actions is not None
    assert sample.actions[0, 0] == 0.0
    assert sample.state is not None
    assert sample.state[0] == 0.0
    assert sample.images["front"].flags.writeable is False
    assert sample.actions.flags.writeable is False
    assert sample.state.flags.writeable is False


def test_raw_sample_should_own_metadata_copy() -> None:
    """验证 RawSample 复制元数据并暴露只读映射。"""
    metadata: dict[str, Any] = {"episode_id": "ep-direct"}
    sample = _raw_sample(metadata=metadata)
    metadata["episode_id"] = "mutated"

    assert sample.metadata["episode_id"] == "ep-direct"
    with pytest.raises(TypeError):
        sample.metadata["new"] = "value"  # type: ignore[index]


def test_should_validate_required_modalities() -> None:
    """验证缺失必需图像模态时返回清晰错误。"""
    from autovla.core.types.modality import validate_required_modalities
    from autovla.core.types.sample import RawSample

    sample = RawSample(
        images={"front": np.zeros((4, 4, 3), dtype=np.uint8)},
        language="pick up the block",
        actions=np.zeros((2, 7), dtype=np.float32),
        state=np.zeros((7,), dtype=np.float32),
        robot_tag="debug-arm",
    )

    with pytest.raises(ValueError, match="wrist"):
        validate_required_modalities(sample, ("front", "wrist"))


def test_should_reject_invalid_action_shape() -> None:
    """验证一维动作数组会被拒绝。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict

    with pytest.raises(ValueError, match="action shape"):
        from_legacy_dict(_legacy_payload(actions=np.zeros((7,), dtype=np.float32)))


def test_should_preserve_robot_tag_metadata() -> None:
    """验证机器人标识会同步写入元数据且保留已有元数据。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict

    sample = from_legacy_dict(
        _legacy_payload(
            robot_tag="libero",
            metadata={"episode_id": "ep-001"},
        )
    )

    assert sample.robot_tag == "libero"
    assert sample.metadata["robot_tag"] == "libero"
    assert sample.metadata["episode_id"] == "ep-001"


def test_should_preserve_top_level_episode_id_metadata() -> None:
    """验证顶层 episode_id 会补入缺省元数据。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict

    sample = from_legacy_dict(
        _legacy_payload(
            episode_id="ep-top",
            metadata={"source": "legacy"},
        )
    )

    assert sample.metadata["episode_id"] == "ep-top"
    assert sample.metadata["source"] == "legacy"


def test_legacy_adapter_should_keep_compat_unknown_robot_tag() -> None:
    """验证 legacy adapter 默认兼容缺失 robot_tag 的旧样本。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict

    payload = _legacy_payload(robot_tag=None, metadata={})
    del payload["robot_tag"]
    sample = from_legacy_dict(payload)

    assert sample.robot_tag == "unknown"
    assert sample.metadata["robot_tag"] == "unknown"


def test_legacy_adapter_should_support_strict_robot_tag() -> None:
    """验证 strict 模式拒绝缺失 robot_tag 的旧样本。"""
    from autovla.core.compat.legacy_sample import from_legacy_dict

    payload = _legacy_payload(robot_tag=None, metadata={})
    del payload["robot_tag"]
    with pytest.raises(ValueError, match="robot_tag"):
        from_legacy_dict(payload, require_robot_tag=True)


def test_should_create_batch_sample_from_raw_samples() -> None:
    """验证 BatchSample 会保留输入的原始样本顺序。"""
    first = _raw_sample(metadata={"episode_id": "ep-001"})
    second = _raw_sample(language="place the block", metadata={"episode_id": "ep-002"})

    batch = BatchSample(samples=(first, second))

    assert batch.samples == (first, second)


def test_should_reject_empty_batch_sample() -> None:
    """验证空批样本会被拒绝。"""
    with pytest.raises(ValueError, match="samples"):
        BatchSample(samples=())


def test_should_report_batch_size() -> None:
    """验证 batch_size 直接反映批内样本数量。"""
    batch = BatchSample(samples=(_raw_sample(), _raw_sample(language="move the block")))

    assert batch.batch_size == 2


def test_should_preserve_batch_metadata() -> None:
    """验证批级元数据按输入映射透传。"""
    metadata: dict[str, Any] = {"source": "unit", "indices": (0, 1)}

    batch = BatchSample(samples=(_raw_sample(),), metadata=metadata)

    assert batch.metadata is metadata
    assert batch.metadata["indices"] == (0, 1)
