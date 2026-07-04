"""训练 runner dry-run 使用的小型内存 fixture。"""

from __future__ import annotations

import numpy as np

from autovla.training.contracts import TrainingBatch

TINY_DATASET_FINGERPRINT = "autovla-tiny-dataset-v1"
TINY_TRANSFORM_FINGERPRINT = "autovla-tiny-transform-v1"
TINY_STATISTICS_FINGERPRINT = "autovla-tiny-statistics-v1"


def build_tiny_training_batch() -> TrainingBatch:
    """构造 deterministic CPU dry-run 使用的最小 ``TrainingBatch``。"""
    actions = np.full((2, 2, 3), 0.5, dtype=np.float32)
    return TrainingBatch(
        images={
            "camera_0": np.zeros((2, 4, 4, 3), dtype=np.float32),
            "camera_1": np.ones((2, 4, 4, 3), dtype=np.float32),
            "camera_2": np.full((2, 4, 4, 3), 2.0, dtype=np.float32),
        },
        language=("pick cube", "place cube"),
        actions=actions,
        action_mask=np.ones_like(actions, dtype=np.bool_),
        state=np.zeros((2, 7), dtype=np.float32),
        sample_source=({"episode": "tiny-0"}, {"episode": "tiny-1"}),
        dataset_fingerprint=TINY_DATASET_FINGERPRINT,
        transform_fingerprint=TINY_TRANSFORM_FINGERPRINT,
        statistics_fingerprint=TINY_STATISTICS_FINGERPRINT,
        metadata={"fixture": "tiny"},
    )
