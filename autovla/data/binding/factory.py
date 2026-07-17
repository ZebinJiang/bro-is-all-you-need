"""只生成后端中立 TrainingBatch 合成 fixture 的确定性工厂。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from autovla.core.types.training import TrainingBatch
from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    DatasetCompatibilityReport,
    DatasetModelBinding,
    sha256_fingerprint,
)
from autovla.data.binding.provenance import ContractBatchProvenance


def _strict_positive_int(value: object, name: str) -> int:
    """校验排除 bool 的正整数。"""
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _strict_nonnegative_int(value: object, name: str) -> int:
    """校验排除 bool 的非负整数。"""
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _readonly_bool(value: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """返回拥有内存且只读的严格 bool 数组。"""
    result = np.array(value, dtype=np.bool_, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True, slots=True)
class ContractBatchFactory:
    """生成确定性 TrainingBatch-shaped 合成样本,仅验证形状和契约机械行为。

    该工厂不读取媒体或数据行,不导入模型,不执行设备移动。即使输入绑定是
    ``exact`` 或 ``explicit_projection``,输出 provenance 也固定降格为
    ``contract_fixture_only``,不得作为真实数据、机器人或模型质量证据。
    """

    binding: DatasetModelBinding
    compatibility_report: DatasetCompatibilityReport
    seed: int = 0

    def __post_init__(self) -> None:
        """校验报告属于当前绑定并拒绝 incompatible 输入。"""
        if not isinstance(self.binding, DatasetModelBinding):
            raise TypeError("binding must be DatasetModelBinding")
        if not isinstance(self.compatibility_report, DatasetCompatibilityReport):
            raise TypeError("compatibility_report must be DatasetCompatibilityReport")
        object.__setattr__(self, "seed", _strict_nonnegative_int(self.seed, "seed"))
        if self.compatibility_report.binding_fingerprint != self.binding.fingerprint:
            raise ValueError("compatibility report does not belong to binding")
        if self.compatibility_report.immutable_dataset_fingerprint != (
            self.binding.immutable_dataset_fingerprint
        ):
            raise ValueError("compatibility report changed immutable dataset fingerprint")
        if (
            self.compatibility_report.level is DatasetCompatibilityLevel.INCOMPATIBLE
            or not self.compatibility_report.batch_factory_allowed
        ):
            raise ValueError("incompatible binding cannot create a contract fixture")

    def _factory_fingerprint(self, *, batch_size: int, image_height: int, image_width: int) -> str:
        """把工厂输入参数纳入确定性摘要。"""
        return sha256_fingerprint(
            {
                "binding_fingerprint": self.binding.fingerprint,
                "compatibility_report_fingerprint": self.compatibility_report.fingerprint,
                "seed": self.seed,
                "batch_size": batch_size,
                "image_height": image_height,
                "image_width": image_width,
                "factory_schema": "autovla.contract_batch_factory.v1",
            }
        )

    def provenance(
        self,
        *,
        batch_size: int = 1,
        image_height: int = 4,
        image_width: int = 4,
    ) -> ContractBatchProvenance:
        """返回本次形状参数对应的固定 fixture-only provenance。"""
        batch_size = _strict_positive_int(batch_size, "batch_size")
        image_height = _strict_positive_int(image_height, "image_height")
        image_width = _strict_positive_int(image_width, "image_width")
        return ContractBatchProvenance(
            binding_fingerprint=self.binding.fingerprint,
            dataset_fingerprint=self.binding.immutable_dataset_fingerprint,
            factory_fingerprint=self._factory_fingerprint(
                batch_size=batch_size,
                image_height=image_height,
                image_width=image_width,
            ),
            source_revision=self.binding.model_schema.source_pin,
        )

    def create_with_provenance(
        self,
        *,
        batch_size: int = 1,
        image_height: int = 4,
        image_width: int = 4,
    ) -> tuple[TrainingBatch, ContractBatchProvenance]:
        """构造一个规范 TrainingBatch 和不可升级的合成 provenance。"""
        batch_size = _strict_positive_int(batch_size, "batch_size")
        image_height = _strict_positive_int(image_height, "image_height")
        image_width = _strict_positive_int(image_width, "image_width")
        model = self.binding.model_schema
        provenance = self.provenance(
            batch_size=batch_size,
            image_height=image_height,
            image_width=image_width,
        )

        images: dict[str, NDArray[np.uint8]] = {}
        for camera_index, camera_name in enumerate(model.camera_names):
            # 仅用索引和 seed 生成小型确定性像素,不模拟真实视觉分布。
            base = (self.seed + camera_index * 17) % 256
            values = np.arange(
                batch_size * image_height * image_width * 3,
                dtype=np.uint32,
            ).reshape(batch_size, image_height, image_width, 3)
            images[camera_name] = ((values + base) % 256).astype(np.uint8)

        state = np.zeros((batch_size, model.state_dimension), dtype=np.float32)
        state_mask = np.zeros((batch_size, model.state_dimension), dtype=np.bool_)
        for target_index in self.binding.state_binding.target_indices:
            state[:, target_index] = (
                np.arange(batch_size, dtype=np.float32) + target_index + self.seed / 1000.0
            )
            state_mask[:, target_index] = True

        actions = np.full(
            (batch_size, model.horizon, model.action_dimension),
            self.binding.action_binding.padding_value,
            dtype=np.float32,
        )
        action_mask = np.zeros(actions.shape, dtype=np.bool_)
        batch_axis = np.arange(batch_size, dtype=np.float32)[:, None]
        horizon_axis = np.arange(model.horizon, dtype=np.float32)[None, :]
        for target_index in self.binding.action_binding.target_indices:
            actions[:, :, target_index] = (
                batch_axis + horizon_axis / 100.0 + target_index + self.seed / 1000.0
            )
            action_mask[:, :, target_index] = True

        camera_mask = np.ones((batch_size, len(model.camera_names)), dtype=np.bool_)
        temporal_mask = np.ones((batch_size, model.horizon), dtype=np.bool_)
        timestamps = np.arange(model.horizon, dtype=np.float32)[None, :]
        timestamps = np.repeat(timestamps / model.sample_rate_hz, batch_size, axis=0)
        language = tuple(f"contract fixture {index}" for index in range(batch_size))
        sample_source = tuple(
            {
                "kind": "contract_fixture_only",
                "sample_index": index,
                "synthetic": True,
                "binding_fingerprint": self.binding.fingerprint,
            }
            for index in range(batch_size)
        )
        metadata: dict[str, object] = {
            "contract_batch_provenance": provenance.to_dict(),
            "compatibility_level": DatasetCompatibilityLevel.CONTRACT_FIXTURE_ONLY.value,
            "camera_order": model.camera_names,
            "padding": {
                "state_dimension": model.state_dimension,
                "action_dimension": model.action_dimension,
                "action_horizon": model.horizon,
                "synthetic_padding_only": True,
            },
            "state_mask": _readonly_bool(state_mask),
            "camera_mask": _readonly_bool(camera_mask),
            "temporal_mask": _readonly_bool(temporal_mask),
            "non_claims": (
                "no_real_data_evidence",
                "no_robot_evidence",
                "no_model_quality_evidence",
            ),
        }
        batch = TrainingBatch(
            images=images,
            language=language,
            actions=actions,
            action_mask=action_mask,
            sample_source=sample_source,
            dataset_fingerprint=self.binding.immutable_dataset_fingerprint,
            transform_fingerprint=self.binding.fingerprint,
            statistics_fingerprint=self.binding.normalization_binding.statistics_fingerprint,
            state=state,
            metadata=metadata,
            embodiment=tuple(self.binding.embodiment_id for _ in range(batch_size)),
            timestamps=timestamps,
            dataset_manifest_fingerprint=self.binding.immutable_dataset_fingerprint,
            store_fingerprints=tuple(provenance.factory_fingerprint for _ in range(batch_size)),
            source_fingerprints=tuple(provenance.fingerprint for _ in range(batch_size)),
            schema_fingerprints=tuple(model.fingerprint for _ in range(batch_size)),
        )
        return batch, provenance

    def create(
        self,
        *,
        batch_size: int = 1,
        image_height: int = 4,
        image_width: int = 4,
    ) -> TrainingBatch:
        """只返回规范 TrainingBatch;其 metadata 仍携带完整 fixture provenance。"""
        batch, _ = self.create_with_provenance(
            batch_size=batch_size,
            image_height=image_height,
            image_width=image_width,
        )
        return batch

    def build(
        self,
        *,
        batch_size: int = 1,
        image_height: int = 4,
        image_width: int = 4,
    ) -> TrainingBatch:
        """提供与 ``create`` 等价的显式构建入口。"""
        return self.create(
            batch_size=batch_size,
            image_height=image_height,
            image_width=image_width,
        )


__all__ = ["ContractBatchFactory"]
