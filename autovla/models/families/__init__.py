"""AutoVLA 模型族共享契约入口; 导入时不加载家族运行时。"""

from autovla.models.families.specification import (
    M10_MODEL_ZOO_CONTRACT,
    DependencyClass,
    DependencyRequirement,
    ModelAssemblyRequirements,
    ModelAssetRequirement,
    ModelCheckpointDefinition,
    ModelDependencyRequirements,
    ModelFamilyDefinition,
    ModelFamilySpec,
    ModelZooContract,
    RuntimeEvidenceState,
    TransformRequirement,
)

ACTIVE_MODEL_FAMILY_KEYS = ("gr00t_n1d6", "gr00t_n1d7", "pi0_5")

__all__ = [
    "ACTIVE_MODEL_FAMILY_KEYS",
    "M10_MODEL_ZOO_CONTRACT",
    "DependencyClass",
    "DependencyRequirement",
    "ModelAssemblyRequirements",
    "ModelAssetRequirement",
    "ModelCheckpointDefinition",
    "ModelDependencyRequirements",
    "ModelFamilyDefinition",
    "ModelFamilySpec",
    "ModelZooContract",
    "RuntimeEvidenceState",
    "TransformRequirement",
]
