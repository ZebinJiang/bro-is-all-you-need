"""GR00T-N1D6 dry-run batch adapter。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.core.types import BatchSample, ModelInput, RawSample, TrainingBatch
from autovla.models.gr00t.metadata import GR00T_N1D6_FAMILY_SPEC


@dataclass(frozen=True, slots=True)
class Gr00tN1D6DryRunBatchAdapter:
    """把通用 ``TrainingBatch`` 转成 GR00T dry-run ``ModelInput``。

    该适配器只做形状和元数据转换,不导入 GR00T、torch、transformers 或
    checkpoint/tokenizer 运行时。
    """

    expected_camera_count: int = 3

    def __post_init__(self) -> None:
        """校验 camera 策略。"""
        if self.expected_camera_count <= 0:
            raise ValueError("expected_camera_count must be positive")

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """执行无 IO 的 dry-run 转换。"""
        if len(batch.images) != self.expected_camera_count:
            raise ValueError(
                f"images must contain {self.expected_camera_count} camera views, "
                f"got {len(batch.images)}"
            )
        if batch.action_mask.shape != batch.actions.shape:
            raise ValueError("action_mask must match actions shape")
        samples = tuple(
            RawSample(
                images={name: image[index] for name, image in batch.images.items()},
                language=batch.language[index],
                actions=batch.actions[index],
                state=batch.state[index] if batch.state is not None else None,
                robot_tag="gr00t-n1d6-dryrun",
                metadata={
                    "sample_source": dict(batch.sample_source[index]),
                    "action_mask": batch.action_mask[index],
                },
            )
            for index in range(batch.batch_size)
        )
        tensors = {f"image.{name}": value for name, value in batch.images.items()}
        tensors["actions"] = batch.actions
        if batch.state is not None:
            tensors["state"] = batch.state
        return ModelInput(
            batch=BatchSample(samples=samples, metadata={"source": "gr00t-n1d6-dryrun"}),
            tensors=tensors,
            metadata={
                "family_key": GR00T_N1D6_FAMILY_SPEC.family_key,
                "dataset_fingerprint": batch.dataset_fingerprint,
                "transform_fingerprint": batch.transform_fingerprint,
                "statistics_fingerprint": batch.statistics_fingerprint,
                "action_horizon": batch.action_horizon,
                "action_dim": batch.action_dim,
                "action_mask": batch.action_mask,
                "runtime_status": tuple(GR00T_N1D6_FAMILY_SPEC.runtime_status),
            },
        )
