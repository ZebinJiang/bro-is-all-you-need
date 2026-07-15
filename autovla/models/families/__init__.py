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

__all__ = [
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
