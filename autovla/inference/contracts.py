"""本地推理请求和结果值类型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from autovla.core.types.training import NumericArray, TrainingBatch


def _empty_texts() -> dict[str, str]:
    """返回类型明确的空文本映射。"""
    return {}


def _is_training_batch(value: object) -> bool:
    """在外部请求解码边界校验 canonical batch 类型。"""
    return isinstance(value, TrainingBatch)


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """引用 canonical batch 及共享 processor/transform 身份。"""

    request_id: str
    batch: TrainingBatch
    processor_fingerprint: str
    transform_fingerprint: str
    metadata: Mapping[str, str] = field(default_factory=_empty_texts)

    def __post_init__(self) -> None:
        """校验本地请求身份且不执行预测。"""
        for value in (
            self.request_id,
            self.processor_fingerprint,
            self.transform_fingerprint,
        ):
            if not value.strip():
                raise ValueError("inference request identities must not be empty")
        if not _is_training_batch(self.batch):
            raise TypeError("inference request batch must be canonical TrainingBatch")
        if any(not key.strip() or not value.strip() for key, value in self.metadata.items()):
            raise ValueError("inference request metadata must not be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """保存已解码物理动作和可审计会话身份。"""

    request_id: str
    actions: NumericArray
    action_decode_fingerprint: str
    session_fingerprint: str
    provenance: Mapping[str, str] = field(default_factory=_empty_texts)

    def __post_init__(self) -> None:
        """校验动作形状和身份, 不触发 endpoint。"""
        import numpy as np

        for value in (
            self.request_id,
            self.action_decode_fingerprint,
            self.session_fingerprint,
        ):
            if not value.strip():
                raise ValueError("inference result identities must not be empty")
        actions = np.array(self.actions, copy=True)
        if actions.ndim != 3 or min(actions.shape) <= 0 or not np.isfinite(actions).all():
            raise ValueError("inference result actions must be finite [B,H,D]")
        actions.setflags(write=False)
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


__all__ = ["InferenceRequest", "InferenceResult"]
