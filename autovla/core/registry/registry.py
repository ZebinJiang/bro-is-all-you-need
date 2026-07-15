"""AutoVLA 组件注册表与懒工厂元数据。"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar, cast

from autovla.core.registry.errors import (
    DuplicateRegistrationError,
    InvalidImportStringError,
    OptionalDependencyError,
    UnknownRegistrationError,
)

T = TypeVar("T")
R = TypeVar("R")


def _empty_metadata() -> Mapping[str, object]:
    """返回类型明确的空工厂元数据。"""
    return {}


def _validate_name(value: str, *, field_name: str) -> str:
    """校验注册表名称和键使用稳定非空文本。"""
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    return value


@dataclass(frozen=True, slots=True)
class ImportStringFactory(Generic[R]):
    """保存不触发产品导入的组件工厂元数据。

    ``factory_path`` 必须采用 ``package.module:attribute`` 形式。调用
    :meth:`load` 或 :meth:`create` 前只保存字符串和依赖声明,不会导入可选
    运行时模块。
    """

    factory_path: str
    optional_extra: str | None = None
    required_modules: tuple[str, ...] = ()
    description: str = ""
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验导入路径、可选依赖名和不可变元数据。"""
        module_name, separator, attribute_name = self.factory_path.partition(":")
        if not separator or not module_name.strip() or not attribute_name.strip():
            raise InvalidImportStringError(
                "factory_path must use 'package.module:attribute' format"
            )
        if self.optional_extra is not None:
            _validate_name(self.optional_extra, field_name="optional_extra")
        modules: list[str] = []
        for module in self.required_modules:
            modules.append(_validate_name(module, field_name="required_modules item"))
        if len(set(modules)) != len(modules):
            raise ValueError("required_modules must not contain duplicates")
        object.__setattr__(self, "required_modules", tuple(modules))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def load(self) -> Callable[..., R]:
        """检查声明依赖并解析工厂,不构造组件。

        Raises:
            OptionalDependencyError: 选定组件缺少声明依赖时抛出,并给出可
                安装的 extra 名称。
            InvalidImportStringError: 导入目标不存在或不可调用时抛出。
        """
        missing = tuple(
            module for module in self.required_modules if importlib.util.find_spec(module) is None
        )
        if missing:
            suffix = (
                f" Install the '{self.optional_extra}' extra."
                if self.optional_extra is not None
                else " Install the component's declared optional dependencies."
            )
            raise OptionalDependencyError(
                f"factory {self.factory_path!r} requires missing modules "
                f"{', '.join(missing)}.{suffix}"
            )
        module_name, _, attribute_name = self.factory_path.partition(":")
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, attribute_name)
        except (ImportError, AttributeError) as exc:
            raise InvalidImportStringError(f"cannot resolve factory {self.factory_path!r}") from exc
        if not callable(target):
            raise InvalidImportStringError(f"factory target {self.factory_path!r} is not callable")
        return cast(Callable[..., R], target)

    def create(self, *args: object, **kwargs: object) -> R:
        """解析并调用工厂,返回新组件实例。"""
        factory = self.load()
        return factory(*args, **kwargs)


class ComponentRegistry(Generic[T]):
    """按规范键保存组件并在注册时统一管理别名。

    注册表拒绝规范键和别名的所有重复或交叉碰撞。值可以是普通对象,也可
    以 :class:`ImportStringFactory` 保存懒构造元数据;查询注册表本身不会导入
    可选运行时模块。

    Args:
        name: 注册表领域名称,仅用于错误信息和调试。
    """

    def __init__(self, name: str) -> None:
        """创建一个空注册表。"""
        if not name.strip():
            raise ValueError("registry name must not be empty")
        self._name = name
        self._items: dict[str, T] = {}
        self._aliases: dict[str, str] = {}

    @property
    def name(self) -> str:
        """返回注册表领域名称。"""
        return self._name

    def register(self, key: str, value: T, *, aliases: tuple[str, ...] = ()) -> None:
        """注册一个对象。

        Args:
            key: 组件规范键。
            value: 要保存的组件或懒工厂元数据。
            aliases: 指向规范键的显式兼容别名。

        Raises:
            DuplicateRegistrationError: 当名称已存在且未允许覆盖时抛出。
        """
        canonical = _validate_name(key, field_name="registry key")
        alias_values = tuple(
            _validate_name(alias, field_name="registry alias") for alias in aliases
        )
        if len(set(alias_values)) != len(alias_values):
            raise DuplicateRegistrationError(
                f"duplicate aliases supplied for {canonical!r} in registry {self._name!r}"
            )
        candidates = (canonical, *alias_values)
        for candidate in candidates:
            if candidate in self._items or candidate in self._aliases:
                raise DuplicateRegistrationError(
                    f"{candidate!r} collides in registry {self._name!r}"
                )
        if canonical in alias_values:
            raise DuplicateRegistrationError(f"canonical key {canonical!r} cannot also be an alias")
        self._items[canonical] = value
        self._aliases.update({alias: canonical for alias in alias_values})

    def resolve_key(self, key: str) -> str:
        """把规范键或别名解析为规范键。"""
        if key in self._items:
            return key
        try:
            return self._aliases[key]
        except KeyError as exc:
            choices = ", ".join(self.names(include_aliases=True)) or "<empty>"
            raise UnknownRegistrationError(
                f"{key!r} is not registered in registry {self._name!r}; "
                f"available keys: {choices}"
            ) from exc

    def get(self, key: str) -> T:
        """按名称返回已注册对象。

        Args:
            name: 需要查询的对象名称。

        Raises:
            UnknownRegistrationError: 当名称不存在时抛出。
        """
        return self._items[self.resolve_key(key)]

    def names(self, *, include_aliases: bool = False) -> tuple[str, ...]:
        """返回按字典序排序的规范键,可选包含别名。"""
        names = set(self._items)
        if include_aliases:
            names.update(self._aliases)
        return tuple(sorted(names))

    def items(self) -> tuple[tuple[str, T], ...]:
        """返回按名称排序的 ``(name, item)`` 元组。"""
        return tuple((name, self._items[name]) for name in self.names())

    def __contains__(self, name: object) -> bool:
        """判断名称是否已注册。"""
        return name in self._items or name in self._aliases

    def __len__(self) -> int:
        """返回已注册对象数量。"""
        return len(self._items)


# 保留历史名称的对象身份,避免形成第二套注册表实现。
Registry = ComponentRegistry

__all__ = ["ComponentRegistry", "ImportStringFactory", "Registry"]
