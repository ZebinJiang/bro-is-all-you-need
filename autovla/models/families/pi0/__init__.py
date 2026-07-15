"""Pi0 规范命名空间;属性按需加载。"""

from importlib import import_module

__all__ = ["PI0_SPEC", "Pi0ModelSpec"]


def __getattr__(name: str) -> object:
    """惰性解析静态规范。"""

    if name not in __all__:
        raise AttributeError(name)
    return getattr(import_module("autovla.models.families.pi0.specification"), name)
