"""部署相邻 hook 的类型化懒注册表。"""

from dataclasses import dataclass

from autovla.core.registry import ComponentRegistry, ImportStringFactory


@dataclass(frozen=True, slots=True)
class DeploymentHookRegistration:
    """绑定规范 hook 键和延迟工厂。"""

    key: str
    factory: ImportStringFactory[object]


class DeploymentHookRegistry(ComponentRegistry[DeploymentHookRegistration]):
    """保存本地生命周期 hook, 不拥有 transport。"""


def build_deployment_hook_registry() -> DeploymentHookRegistry:
    """构造 transport-neutral 生命周期 hook 注册表。"""
    registry = DeploymentHookRegistry("autovla-deployment-hooks")
    registry.register(
        "local_lifecycle",
        DeploymentHookRegistration(
            "local_lifecycle",
            ImportStringFactory("autovla.deployment.hooks:DeploymentHook"),
        ),
    )
    return registry


__all__ = [
    "DeploymentHookRegistration",
    "DeploymentHookRegistry",
    "build_deployment_hook_registry",
]
