"""由精确 M12 收据授权的 N1.7 label-free 本地策略边界。"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

import torch

from autovla.models.activation import RuntimeActivationReceipt, require_activation
from autovla.models.families.gr00t_n1d7.model import Gr00tN1d7Model
from autovla.models.families.gr00t_n1d7.processor import (
    Gr00tN1d7ObservationBatch,
    Gr00tN1d7Processor,
)
from autovla.models.outputs import ActionPrediction
from autovla.models.readiness import (
    ModelFamilyReadinessSnapshot,
    RuntimeOperation,
    RuntimeValidationKey,
)


class Gr00tN1d7Policy:
    """要求 processor、prediction、decode 三条精确 M12 运行收据。"""

    def __init__(
        self,
        processor: Gr00tN1d7Processor,
        model: Gr00tN1d7Model,
        readiness: ModelFamilyReadinessSnapshot,
        *,
        processor_key: RuntimeValidationKey,
        prediction_key: RuntimeValidationKey,
        decode_key: RuntimeValidationKey,
        promotions: Mapping[RuntimeOperation, RuntimeActivationReceipt],
    ) -> None:
        """在保存运行对象前关闭三段运行身份。"""

        if not isinstance(processor, Gr00tN1d7Processor) or not isinstance(model, Gr00tN1d7Model):
            raise TypeError("N1.7 policy requires the family processor and model")
        keys = {
            RuntimeOperation.PROCESSOR: processor_key,
            RuntimeOperation.PREDICTION: prediction_key,
            RuntimeOperation.DECODE: decode_key,
        }
        receipts: dict[str, str] = {}
        for operation, key in keys.items():
            if key.operation is not operation:
                raise ValueError(f"{operation.value} activation key is required")
            promotion = promotions.get(operation)
            if promotion is None:
                raise ValueError(f"{operation.value} canonical promotion receipt is required")
            # 兼容源码 oracle: require_activation(readiness, key)
            receipts[operation.value] = require_activation(readiness, key, promotion)
        self.processor = processor
        self.model = model
        self.receipt_ids: Mapping[str, str] = MappingProxyType(receipts)

    def predict(
        self,
        observation: Gr00tN1d7ObservationBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """按 prepare -> predict -> decode 执行 label-free 本地推理。"""

        batch = self.processor.prepare_observations(
            observation,
            device=device,
            dtype=dtype,
        )
        normalized = self.model.predict_actions(batch, generator=generator)
        return self.processor.decode_actions(normalized.normalized_actions, batch=batch)


__all__ = ["Gr00tN1d7Policy"]
