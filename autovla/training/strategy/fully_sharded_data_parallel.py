"""FSDP2 历史导入兼容层,不包含生产实现。"""


class FullyShardedDataParallelStrategy:
    """拒绝历史 FSDP2 构造并给出唯一迁移路径。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """始终失败,避免历史导入恢复隐藏实现。"""

        del args, kwargs
        raise RuntimeError(
            "FSDP/FSDP2 is unsupported; migrate to deepspeed with zero_stage=3"
        )


__all__ = ["FullyShardedDataParallelStrategy"]
