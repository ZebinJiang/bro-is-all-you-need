"""AutoVLA 分布式和精度配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_bool, require_choice, require_positive_int


@dataclass(frozen=True, slots=True)
class DistributedConfig:
    """描述显式训练策略和进程拓扑。"""

    strategy_key: str = "single_device"
    world_size: int = 1
    device: str = "cpu"
    gradient_as_bucket_view: bool = True
    find_unused_parameters: bool = False
    fsdp_reshard_after_forward: bool = True

    def __post_init__(self) -> None:
        """校验策略名称和世界大小,不执行进程初始化。"""
        require_choice(
            self.strategy_key,
            "training.distributed.strategy_key",
            ("single_device", "distributed_data_parallel", "fully_sharded_data_parallel"),
        )
        require_positive_int(self.world_size, "training.distributed.world_size")
        require_choice(self.device, "training.distributed.device", ("cpu", "cuda"))
        require_bool(self.gradient_as_bucket_view, "distributed.gradient_as_bucket_view")
        require_bool(self.find_unused_parameters, "distributed.find_unused_parameters")
        require_bool(self.fsdp_reshard_after_forward, "distributed.fsdp_reshard_after_forward")
        if self.strategy_key == "single_device" and self.world_size != 1:
            raise ValueError("single_device strategy requires world_size=1")


@dataclass(frozen=True, slots=True)
class PrecisionConfig:
    """描述关闭集合中的训练精度策略。"""

    mode: str = "float32"

    def __post_init__(self) -> None:
        """拒绝未知精度模式,避免静默回退。"""
        require_choice(self.mode, "training.precision.mode", ("float32", "bfloat16", "float16"))


__all__ = ["DistributedConfig", "PrecisionConfig"]
