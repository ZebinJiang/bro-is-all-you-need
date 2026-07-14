"""AutoVLA rank/worker 确定性分区。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PartitionContext:
    """描述 rank 和 worker 的笛卡尔分区。"""

    rank: int = 0
    local_rank: int = 0
    world_size: int = 1
    worker_id: int = 0
    worker_count: int = 1

    def __post_init__(self) -> None:
        """校验进程和 worker 索引范围。"""
        if self.world_size <= 0 or self.worker_count <= 0:
            raise ValueError("world_size and worker_count must be positive")
        if self.rank < 0 or self.rank >= self.world_size:
            raise ValueError("rank must be in [0, world_size)")
        if self.local_rank < 0 or self.local_rank > self.rank:
            raise ValueError("local_rank must be in [0, rank]")
        if self.worker_id < 0 or self.worker_id >= self.worker_count:
            raise ValueError("worker_id must be in [0, worker_count)")

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
