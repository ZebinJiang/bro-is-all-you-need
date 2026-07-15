"""本地推理和 policy bundle 的轻量公共接口。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.inference.bundle import PolicyBundle, PolicyBundleManifest
    from autovla.inference.contracts import InferenceRequest, InferenceResult
    from autovla.inference.registry import PolicyBundleRegistry, build_policy_bundle_registry
    from autovla.inference.session import InferenceSession

_EXPORTS = {
    "InferenceRequest": ("autovla.inference.contracts", "InferenceRequest"),
    "InferenceResult": ("autovla.inference.contracts", "InferenceResult"),
    "InferenceSession": ("autovla.inference.session", "InferenceSession"),
    "PolicyBundle": ("autovla.inference.bundle", "PolicyBundle"),
    "PolicyBundleManifest": ("autovla.inference.bundle", "PolicyBundleManifest"),
    "PolicyBundleRegistry": ("autovla.inference.registry", "PolicyBundleRegistry"),
    "build_policy_bundle_registry": (
        "autovla.inference.registry",
        "build_policy_bundle_registry",
    ),
}

__all__ = (
    "InferenceRequest",
    "InferenceResult",
    "InferenceSession",
    "PolicyBundle",
    "PolicyBundleManifest",
    "PolicyBundleRegistry",
    "build_policy_bundle_registry",
)


def __getattr__(name: str) -> object:
    """按需导入本地契约, 不加载模型运行时。"""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
