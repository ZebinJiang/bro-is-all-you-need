"""Pi0-FAST 规范命名空间;属性按需加载。"""

from importlib import import_module

__all__ = ["PI0_FAST_SPEC", "Pi0FastModelSpec"]


def __getattr__(name: str) -> object:
    """惰性解析静态规范。"""

    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module("autovla.models.families.pi0_fast.specification"), name)
