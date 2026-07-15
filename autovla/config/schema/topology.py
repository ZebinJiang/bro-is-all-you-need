"""GPU-only 训练拓扑配置。"""

from dataclasses import dataclass, field

from autovla.config.schema.distributed import DistributedConfig, PrecisionConfig


@dataclass(frozen=True, slots=True)
class TopologyConfig:
    """组合唯一活动策略和精度, 不提供 CPU/FSDP 选择。"""

    distributed: DistributedConfig = field(default_factory=DistributedConfig)
    precision: PrecisionConfig = field(default_factory=PrecisionConfig)


__all__ = ["TopologyConfig"]
