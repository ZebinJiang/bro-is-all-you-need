"""AutoVLA 泛型注册表。"""

from __future__ import annotations

from typing import Generic, TypeVar

from autovla.core.registry.errors import DuplicateRegistrationError, UnknownRegistrationError

T = TypeVar("T")


class Registry(Generic[T]):
    """按名称保存同一领域对象的轻量注册表。

    M1 注册表是急切、实例级、确定性排序的结构,不执行懒加载、父作用域查找或对象构建。

    Args:
        name: 注册表领域名称,仅用于错误信息和调试。
    """

    def __init__(self, name: str) -> None:
        """创建一个空注册表。"""
        if not name.strip():
            raise ValueError("registry name must not be empty")
        self._name = name
        self._items: dict[str, T] = {}

    @property
    def name(self) -> str:
        """返回注册表领域名称。"""
        return self._name

    def register(self, name: str, item: T, *, overwrite: bool = False) -> None:
        """注册一个对象。

        Args:
            name: 对象名称,去除空白后不能为空。
            item: 要保存的对象。
            overwrite: 为 ``True`` 时允许替换已有同名对象。

        Raises:
            DuplicateRegistrationError: 当名称已存在且未允许覆盖时抛出。
        """
        if not name.strip():
            raise ValueError("registry key must not be empty")
        if name in self._items and not overwrite:
            raise DuplicateRegistrationError(
                f"{name!r} is already registered in registry {self._name!r}"
            )
        self._items[name] = item

    def get(self, name: str) -> T:
        """按名称返回已注册对象。

        Args:
            name: 需要查询的对象名称。

        Raises:
            UnknownRegistrationError: 当名称不存在时抛出。
        """
        try:
            return self._items[name]
        except KeyError as exc:
            raise UnknownRegistrationError(
                f"{name!r} is not registered in registry {self._name!r}"
            ) from exc

    def names(self) -> tuple[str, ...]:
        """返回按字典序排序的注册名称。"""
        return tuple(sorted(self._items))

    def items(self) -> tuple[tuple[str, T], ...]:
        """返回按名称排序的 ``(name, item)`` 元组。"""
        return tuple((name, self._items[name]) for name in self.names())

    def __contains__(self, name: object) -> bool:
        """判断名称是否已注册。"""
        return name in self._items

    def __len__(self) -> int:
        """返回已注册对象数量。"""
        return len(self._items)
