"""AutoVLA rank/worker 确定性分区。"""

from dataclasses import dataclass
from typing import cast


@dataclass(frozen=True, slots=True)
class PartitionContext:
    """描述 rank 和 worker 的笛卡尔分区。"""

    rank: int = 0
    local_rank: int = 0
    world_size: int = 1
    node_rank: int = 0
    local_world_size: int = 1
    launcher: str = "direct"
    strategy: str = "single_gpu"
    worker_id: int = 0
    worker_count: int = 1

    def __post_init__(self) -> None:
        """校验进程和 worker 索引范围。"""
        integer_fields = (
            self.rank,
            self.local_rank,
            self.world_size,
            self.node_rank,
            self.local_world_size,
            self.worker_id,
            self.worker_count,
        )
        if any(type(value) is not int for value in integer_fields):
            raise TypeError("partition rank and worker facts must be built-in integers")
        if self.world_size <= 0 or self.local_world_size <= 0 or self.worker_count <= 0:
            raise ValueError("world_size, local_world_size, and worker_count must be positive")
        if self.rank < 0 or self.rank >= self.world_size:
            raise ValueError("rank must be in [0, world_size)")
        if self.world_size % self.local_world_size != 0:
            raise ValueError("world_size must be divisible by local_world_size")
        node_count = self.world_size // self.local_world_size
        if self.node_rank < 0 or self.node_rank >= node_count:
            raise ValueError("node_rank must be in [0, node_count)")
        if self.local_rank < 0 or self.local_rank >= self.local_world_size:
            raise ValueError("local_rank must be in [0, local_world_size)")
        if self.rank != self.node_rank * self.local_world_size + self.local_rank:
            raise ValueError("rank must match node_rank and local_rank")
        if self.worker_id < 0 or self.worker_id >= self.worker_count:
            raise ValueError("worker_id must be in [0, worker_count)")
        launcher = cast(object, self.launcher)
        strategy = cast(object, self.strategy)
        if not isinstance(launcher, str) or not launcher:
            raise ValueError("launcher must be non-empty text")
        if not isinstance(strategy, str) or not strategy:
            raise ValueError("strategy must be non-empty text")

    @property
    def partition_index(self) -> int:
        """返回合并 rank/worker 后的稳定分区索引。"""
        return self.rank * self.worker_count + self.worker_id

    @property
    def partition_count(self) -> int:
        """返回全局分区总数。"""
        return self.world_size * self.worker_count

    def global_position(self, local_position: int) -> int:
        """把局部序号映射为不重叠全局序号。"""
        if local_position < 0:
            raise ValueError("local_position must be non-negative")
        return self.partition_index + local_position * self.partition_count


__all__ = ["PartitionContext"]
