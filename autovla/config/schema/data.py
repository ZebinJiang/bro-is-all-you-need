"""AutoVLA 数据与加载配置结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

from autovla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_choice,
    require_int,
    require_non_empty_str,
    require_number,
    require_positive_int,
    require_schema_version,
    require_str_tuple,
)


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    """描述一个显式本地数据集及其后端路由。"""

    name: str
    backend: str
    root: str
    split: str = "train"
    weight: float = 1.0
    embodiment: str | None = None
    sample_count: int | None = None
    image_keys: tuple[str, ...] = ()
    language_key: str = "language"
    state_key: str = "state"
    action_key: str = "action"
    action_mask_key: str = "action_mask"

    def __post_init__(self) -> None:
        """校验数据集身份、局部路径和字段映射。"""
        for field_name in (
            "name",
            "backend",
            "root",
            "split",
            "language_key",
            "state_key",
            "action_key",
            "action_mask_key",
        ):
            require_non_empty_str(getattr(self, field_name), f"dataset.{field_name}")
        weight = require_number(self.weight, "dataset.weight")
        if weight <= 0.0:
            raise ValueError("dataset.weight must be positive")
        if self.embodiment is not None:
            require_non_empty_str(self.embodiment, "dataset.embodiment")
        if self.sample_count is not None:
            require_positive_int(self.sample_count, "dataset.sample_count")
        if self.image_keys:
            require_str_tuple(self.image_keys, "dataset.image_keys")


@dataclass(frozen=True, slots=True)
class DataLoaderConfig:
    """描述框架中立批加载参数,不导入 PyTorch。"""

    batch_size: int = 1
    num_workers: int = 0
    drop_last: bool = False
    pin_memory: bool = False
    persistent_workers: bool = False
    prefetch_factor: int = 2

    def __post_init__(self) -> None:
        """校验加载器并发和批大小参数。"""
        require_positive_int(self.batch_size, "data.loader.batch_size")
        workers = require_int(self.num_workers, "data.loader.num_workers")
        if workers < 0:
            raise ValueError("data.loader.num_workers must be non-negative")
        require_bool(self.drop_last, "data.loader.drop_last")
        require_bool(self.pin_memory, "data.loader.pin_memory")
        require_bool(self.persistent_workers, "data.loader.persistent_workers")
        require_positive_int(self.prefetch_factor, "data.loader.prefetch_factor")
        if self.persistent_workers and workers == 0:
            raise ValueError("persistent_workers requires num_workers > 0")


@dataclass(frozen=True, slots=True)
class DatasetMixConfig:
    """描述确定性数据集混合与批平衡策略。"""

    strategy: str = "weighted"
    seed: int = 0
    balance_by: str = "dataset"

    def __post_init__(self) -> None:
        """校验混合策略和随机种子。"""
        require_choice(self.strategy, "data.mix.strategy", ("weighted", "balanced"))
        seed = require_int(self.seed, "data.mix.seed")
        if seed < 0:
            raise ValueError("data.mix.seed must be non-negative")
        require_choice(self.balance_by, "data.mix.balance_by", ("dataset", "embodiment"))


@dataclass(frozen=True, slots=True)
class DataConfig(BaseConfig):
    """描述数据源、加载、混合和归一化选择。

    Args:
        schema_version: 数据配置段版本。M1 仅接受 ``"1.0"``。
        name: 数据配置名称,不能为空。
        root: 数据根目录字符串,不能为空;M1 不要求该目录真实存在。
        required_modalities: 样本必须包含的图像模态名称。
        backend: 显式数据后端键;``None`` 表示未选择,不是默认后端。
    """

    name: str = "local-debug-data"
    root: str = "datasets/working/local_debug"
    required_modalities: tuple[str, ...] = ("front",)
    backend: str | None = None
    datasets: tuple[DatasetConfig, ...] = ()
    loader: DataLoaderConfig = field(default_factory=DataLoaderConfig)
    mix: DatasetMixConfig = field(default_factory=DatasetMixConfig)
    normalization: str | None = None

    def __post_init__(self) -> None:
        """校验数据配置构造器不变量。"""
        require_schema_version(self.schema_version, "data.schema_version")
        require_non_empty_str(self.name, "data.name")
        require_non_empty_str(self.root, "data.root")
        require_str_tuple(self.required_modalities, "data.required_modalities")
        if self.backend is not None:
            require_non_empty_str(self.backend, "data.backend")
        names = tuple(dataset.name for dataset in self.datasets)
        if len(set(names)) != len(names):
            raise ValueError("data.datasets names must be unique")
        if self.normalization is not None:
            require_non_empty_str(self.normalization, "data.normalization")


__all__ = ["DataConfig", "DataLoaderConfig", "DatasetConfig", "DatasetMixConfig"]
