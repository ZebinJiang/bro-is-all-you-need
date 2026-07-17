"""M11 ContractBatchFactory 的确定性、掩码和非声明测试。"""

from __future__ import annotations

import numpy as np
import pytest

from autovla.core.types.training import TrainingBatch
from autovla.data.binding import (
    ContractBatchFactory,
    DatasetCompatibilityLevel,
    evaluate_compatibility,
)
from tests.data.test_m11_dataset_model_binding import (
    DATASET_FINGERPRINT,
    _binding,
)


def test_factory_reuses_canonical_training_batch_and_is_deterministic() -> None:
    """工厂必须复用唯一 TrainingBatch，并对相同输入逐元素确定。"""
    binding = _binding(DatasetCompatibilityLevel.EXACT)
    report = evaluate_compatibility(binding)
    factory = ContractBatchFactory(binding=binding, compatibility_report=report, seed=7)
    first, first_provenance = factory.create_with_provenance(
        batch_size=2,
        image_height=3,
        image_width=5,
    )
    second, second_provenance = factory.create_with_provenance(
        batch_size=2,
        image_height=3,
        image_width=5,
    )
    assert type(first) is TrainingBatch
    assert first_provenance == second_provenance
    assert first_provenance.fingerprint == second_provenance.fingerprint
    assert first.dataset_fingerprint == DATASET_FINGERPRINT
    assert first.transform_fingerprint == binding.fingerprint
    np.testing.assert_array_equal(first.actions, second.actions)
    np.testing.assert_array_equal(first.state, second.state)
    for camera in binding.model_schema.camera_names:
        np.testing.assert_array_equal(first.images[camera], second.images[camera])


def test_factory_preserves_camera_order_padding_and_strict_masks() -> None:
    """相机顺序、模型 padding 和所有 fixture 掩码必须显式且严格 bool。"""
    binding = _binding(DatasetCompatibilityLevel.EXPLICIT_PROJECTION, projected=True)
    report = evaluate_compatibility(binding)
    batch = ContractBatchFactory(binding, report).create(batch_size=2)
    assert tuple(batch.images) == ("primary", "wrist")
    assert batch.state is not None
    assert batch.state.shape == (2, 4)
    assert batch.actions.shape == (2, 3, 4)
    assert batch.action_mask.dtype == np.dtype(np.bool_)
    assert batch.action_mask[:, :, :2].all()
    assert not batch.action_mask[:, :, 2:].any()
    assert np.all(batch.actions[:, :, 2:] == 0.0)

    state_mask = batch.metadata["state_mask"]
    camera_mask = batch.metadata["camera_mask"]
    temporal_mask = batch.metadata["temporal_mask"]
    assert isinstance(state_mask, np.ndarray)
    assert isinstance(camera_mask, np.ndarray)
    assert isinstance(temporal_mask, np.ndarray)
    assert state_mask.dtype == camera_mask.dtype == temporal_mask.dtype == np.dtype(np.bool_)
    assert state_mask.shape == (2, 4)
    assert state_mask[:, :2].all()
    assert not state_mask[:, 2:].any()
    assert camera_mask.shape == (2, 2) and camera_mask.all()
    assert temporal_mask.shape == (2, 3) and temporal_mask.all()
    assert state_mask.flags.writeable is False


def test_factory_provenance_is_prominently_fixture_only_without_overclaim() -> None:
    """即使输入为 exact，合成批也不得升级为真实数据、机器人或质量证据。"""
    binding = _binding(DatasetCompatibilityLevel.EXACT)
    factory = ContractBatchFactory(binding, evaluate_compatibility(binding))
    batch, provenance = factory.create_with_provenance()
    assert provenance.compatibility_level is DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY
    assert provenance.synthetic is True
    assert provenance.real_data_evidence is False
    assert provenance.robot_evidence is False
    assert provenance.model_quality_evidence is False
    embedded = batch.metadata["contract_batch_provenance"]
    assert isinstance(embedded, dict)
    assert embedded["compatibility_level"] == "contract_fixture_only"
    assert embedded["synthetic"] is True
    assert embedded["real_data_evidence"] is False
    assert batch.metadata["compatibility_level"] == "contract_fixture_only"
    assert "no_real_data_evidence" in batch.metadata["non_claims"]
    assert all(source["kind"] == "contract_fixture_only" for source in batch.sample_source)


def test_factory_rejects_incompatible_binding_and_strict_integer_inputs() -> None:
    """不兼容绑定和 bool 等伪整数不能生成零填充伪兼容批。"""
    binding = _binding(DatasetCompatibilityLevel.INCOMPATIBLE)
    with pytest.raises(ValueError, match="incompatible"):
        ContractBatchFactory(binding, evaluate_compatibility(binding))

    exact = _binding(DatasetCompatibilityLevel.EXACT)
    factory = ContractBatchFactory(exact, evaluate_compatibility(exact))
    with pytest.raises(ValueError, match="batch_size"):
        factory.create(batch_size=True)  # type: ignore[arg-type]


def test_different_factory_parameters_change_provenance_fingerprint() -> None:
    """批大小、图像形状或 seed 变化必须改变工厂 provenance。"""
    binding = _binding(DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY)
    report = evaluate_compatibility(binding)
    first = ContractBatchFactory(binding, report, seed=1).provenance(batch_size=1)
    second = ContractBatchFactory(binding, report, seed=2).provenance(batch_size=1)
    third = ContractBatchFactory(binding, report, seed=1).provenance(batch_size=2)
    assert len({first.fingerprint, second.fingerprint, third.fingerprint}) == 3
