"""GenesisVLA 注册表契约测试。"""

import pytest


def test_should_register_and_get_item() -> None:
    """验证注册表能按名称保存并返回对象。"""
    from genesisvla.core.registry import Registry

    class Dummy:
        pass

    registry: Registry[type[object]] = Registry("frameworks")
    registry.register("dummy", Dummy)

    assert registry.get("dummy") is Dummy
    assert "dummy" in registry.names()


def test_should_reject_duplicate_registry_key() -> None:
    """验证重复注册且未允许覆盖时会抛出错误。"""
    from genesisvla.core.registry import DuplicateRegistrationError, Registry

    class Dummy:
        pass

    registry: Registry[type[object]] = Registry("frameworks")
    registry.register("dummy", Dummy)

    with pytest.raises(DuplicateRegistrationError):
        registry.register("dummy", Dummy)


def test_should_raise_clear_error_for_missing_registry_key() -> None:
    """验证查询缺失键时错误消息包含该键名。"""
    from genesisvla.core.registry import Registry, UnknownRegistrationError

    registry: Registry[type[object]] = Registry("frameworks")

    with pytest.raises(UnknownRegistrationError, match="missing"):
        registry.get("missing")
