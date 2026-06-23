"""M2 CPU tiny transform/data contract 端到端测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from genesisvla.dataloader.collate import collate_raw_samples
from genesisvla.dataloader.statistics import FeatureStatistics, load_statistics, save_statistics
from genesisvla.dataloader.transforms import (
    ActionModeTransform,
    ComposeTransform,
    StateActionNormalize,
    StateActionUnnormalize,
    TransformRegistry,
    TransformSpec,
)
from genesisvla.testing.fixtures import tiny_lerobot_fixture


def test_should_run_cpu_tiny_e2e_transform_data_contract(tmp_path: Path) -> None:
    """验证 M2 tiny 数据契约在 CPU 上完成最小闭环。"""
    fixture = tiny_lerobot_fixture()
    action_stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 2.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )
    registry = TransformRegistry()
    registry.register(
        "state_action_normalize",
        lambda _spec: StateActionNormalize(action=action_stats),
    )
    registry.register(
        "action_mode",
        lambda _spec: ActionModeTransform(
            mode="delta",
            reference_frame="previous_action",
            first_step_policy="absolute",
        ),
    )
    config = ComposeTransform.serialize_specs(
        (
            TransformSpec(name="state_action_normalize", params={}),
            TransformSpec(
                name="action_mode",
                params={"mode": "delta", "reference_frame": "previous_action"},
            ),
        )
    )

    transform = ComposeTransform.deserialize(config, registry=registry)
    original = fixture.samples[0]
    transformed = transform(original)
    batch = collate_raw_samples((transformed,))
    cache_path = tmp_path / "statistics.json"
    save_statistics(cache_path, fixture.statistics)
    loaded_statistics = load_statistics(
        cache_path,
        expected_dataset_fingerprint=fixture.statistics.dataset_fingerprint,
        expected_transform_fingerprint=fixture.statistics.transform_fingerprint,
    )
    restored_delta = ActionModeTransform(
        mode="delta",
        reference_frame="previous_action",
        first_step_policy="absolute",
    ).inverse()(transformed)
    restored = StateActionUnnormalize(action=action_stats)(restored_delta)

    assert batch["actions"].shape == (1, 2, 3)
    assert loaded_statistics.checksum
    assert restored.actions is not None
    assert original.actions is not None
    valid = np.asarray([True, True, False])
    np.testing.assert_allclose(restored.actions[:, valid], original.actions[:, valid])
    np.testing.assert_array_equal(restored.actions[:, ~valid], original.actions[:, ~valid])
