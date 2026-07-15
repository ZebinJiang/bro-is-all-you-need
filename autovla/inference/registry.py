"""本地 policy bundle 的类型化懒注册表。"""

from dataclasses import dataclass

from autovla.core.registry import ComponentRegistry, ImportStringFactory


@dataclass(frozen=True, slots=True)
class PolicyBundleRegistration:
    """绑定规范键和延迟 bundle 工厂。"""

    key: str
    factory: ImportStringFactory[object]


class PolicyBundleRegistry(ComponentRegistry[PolicyBundleRegistration]):
    """保存本地 policy bundle 工厂, 不实例化模型。"""


def build_policy_bundle_registry() -> PolicyBundleRegistry:
    """构造唯一 manifest-reference bundle 注册项。"""
    registry = PolicyBundleRegistry("autovla-policy-bundles")
    registry.register(
        "manifest_reference",
        PolicyBundleRegistration(
            "manifest_reference",
            ImportStringFactory("autovla.inference.bundle:PolicyBundle"),
        ),
    )
    return registry


__all__ = [
    "PolicyBundleRegistration",
    "PolicyBundleRegistry",
    "build_policy_bundle_registry",
]
