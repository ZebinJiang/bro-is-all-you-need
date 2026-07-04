"""AutoVLA 训练主干的轻量公共契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, TypeAlias, runtime_checkable

import numpy as np

from autovla.core.types import ActionMask, FrameworkOutput, ModelInput, NumericArray

SampleSource: TypeAlias = Mapping[str, object]


def _empty_metadata() -> dict[str, object]:
    """返回空元数据映射。"""
    return {}


def _readonly_numeric(value: object, *, name: str, ndim: int | None = None) -> NumericArray:
    """校验有限数值数组并返回只读副本。"""
    array = np.asarray(value)
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{name} must have rank {ndim}")
    finite = np.isfinite(array)
    if not bool(finite.all()):
        raise ValueError(f"{name} must be finite")
    owned: NumericArray = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


def _readonly_mask(value: object, *, shape: tuple[int, int, int]) -> ActionMask:
    """校验严格 bool action mask 并返回只读副本。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError("action_mask must be bool [B,H,D] without coercion")
    if array.shape != shape:
        raise ValueError(f"action_mask shape must be {shape}, got {array.shape}")
    owned: ActionMask = np.array(array, dtype=np.bool_, copy=True)
    owned.setflags(write=False)
    return owned


def _require_non_empty(value: str, name: str) -> None:
    """校验字符串非空。"""
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _readonly_metadata(value: Mapping[str, object], *, name: str) -> Mapping[str, object]:
    """复制并冻结字符串 key 元数据映射。"""
    frozen: dict[str, object] = {}
    for key, item in value.items():
        key_text = str(key)
        _require_non_empty(key_text, name)
        frozen[key_text] = item
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class TrainingBatch:
    """已经 collate 完成、可交给模型族适配器的训练批。

    该结构刻意保持模型族无关。DataLoader 不应该产生 GR00T、OpenPI 或
    Qwen-action 专用对象; 这些差异由模型族 ``BatchAdapter`` 处理。
    """

    images: Mapping[str, NumericArray]
    language: tuple[str, ...]
    actions: NumericArray
    action_mask: ActionMask
    sample_source: tuple[SampleSource, ...]
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    state: NumericArray | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验 batch 形状、fingerprint 与只读拥有语义。"""
        actions = _readonly_numeric(self.actions, name="actions", ndim=3)
        batch_size, action_horizon, action_dim = actions.shape
        if batch_size <= 0 or action_horizon <= 0 or action_dim <= 0:
            raise ValueError("actions must have positive [B,H,D] shape")
        action_shape = (batch_size, action_horizon, action_dim)
        action_mask = _readonly_mask(self.action_mask, shape=action_shape)
        if len(self.language) != batch_size:
            raise ValueError("language length must match batch size")
        for index, text in enumerate(self.language):
            _require_non_empty(text, f"language[{index}]")
        if len(self.sample_source) != batch_size:
            raise ValueError("sample_source length must match batch size")
        sample_source = tuple(
            _readonly_metadata(source, name=f"sample_source[{index}]")
            for index, source in enumerate(self.sample_source)
        )
        images: dict[str, NumericArray] = {}
        if not self.images:
            raise ValueError("images must not be empty")
        for name, value in self.images.items():
            _require_non_empty(str(name), "image key")
            image = _readonly_numeric(value, name=f"images.{name}")
            if image.shape[0] != batch_size:
                raise ValueError(f"images.{name} first dimension must match batch size")
            images[str(name)] = image
        state = None
        if self.state is not None:
            state = _readonly_numeric(self.state, name="state")
            if state.shape[0] != batch_size:
                raise ValueError("state first dimension must match batch size")
        for field_name in (
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _require_non_empty(getattr(self, field_name), field_name)

        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "action_mask", action_mask)
        object.__setattr__(self, "sample_source", sample_source)
        object.__setattr__(self, "images", MappingProxyType(images))
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "metadata", _readonly_metadata(self.metadata, name="metadata"))

    @property
    def batch_size(self) -> int:
        """返回 batch size。"""
        return int(self.actions.shape[0])

    @property
    def action_horizon(self) -> int:
        """返回动作 horizon。"""
        return int(self.actions.shape[1])

    @property
    def action_dim(self) -> int:
        """返回动作维度。"""
        return int(self.actions.shape[2])


@runtime_checkable
class BatchAdapter(Protocol):
    """模型族把通用 ``TrainingBatch`` 转成 ``ModelInput`` 的协议。"""

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """执行无 IO 的 batch 转换。"""
        ...


@runtime_checkable
class TrainablePolicy(Protocol):
    """训练主干所需的最小策略协议。"""

    def setup(self) -> None:
        """初始化轻量状态, 不得隐藏下载或模型加载。"""
        ...

    def forward_loss(self, batch: ModelInput) -> FrameworkOutput:
        """执行一次可测试的前向损失计算。"""
        ...


@runtime_checkable
class LossAdapter(Protocol):
    """训练损失适配器协议。"""

    def compute(self, prediction: object, target: object, action_mask: object) -> object:
        """根据预测、目标和严格 action mask 返回损失对象。"""
        ...


@runtime_checkable
class CheckpointAdapter(Protocol):
    """checkpoint manifest 适配器协议。"""

    def write_manifest(self, path: object, manifest: object) -> object:
        """写出 JSON manifest, 不得写模型权重。"""
        ...

    def validate_resume(self, manifest: object, expected: object) -> int:
        """校验恢复兼容性并返回 step。"""
        ...
