"""AutoVLA 本地部署相邻契约。"""

from autovla.deployment.contracts import (
    DeploymentSpec,
    ExportManifest,
    RuntimeCompatibilityReport,
)
from autovla.deployment.hooks import DeploymentHook
from autovla.deployment.registry import DeploymentHookRegistry, build_deployment_hook_registry

__all__ = [
    "DeploymentHook",
    "DeploymentHookRegistry",
    "DeploymentSpec",
    "ExportManifest",
    "RuntimeCompatibilityReport",
    "build_deployment_hook_registry",
]
