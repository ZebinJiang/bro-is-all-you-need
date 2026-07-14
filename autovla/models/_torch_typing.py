"""隔离 PyTorch 动态 stub 与 AutoVLA 严格类型边界。"""

from __future__ import annotations

from typing import Protocol, cast


class _CooperativeModuleInitializer(Protocol):
    """描述 MRO 中下一个已绑定模块初始化器。"""

    def __call__(self) -> None:
        """按 cooperative super 语义初始化当前实例。"""
        ...


def initialize_torch_module(cooperative_super: object) -> None:
    """调用已绑定的 cooperative super 初始化器并隔离动态 stub。"""

    raw_initializer: object = cooperative_super.__init__
    initializer = cast(_CooperativeModuleInitializer, raw_initializer)
    initializer()


__all__ = ["initialize_torch_module"]
