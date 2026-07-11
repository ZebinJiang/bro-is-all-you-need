"""AutoVLA 本地推理与部署钩子契约。"""

from autovla.deployment.hooks import DeploymentHook
from autovla.deployment.policy import InferencePolicy

__all__ = ["DeploymentHook", "InferencePolicy"]
