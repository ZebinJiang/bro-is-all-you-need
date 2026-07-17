"""由规范装配结果投影出的家族中立模型运行包。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from autovla.models.assembly.contracts import (
    CheckpointLoadEvidence,
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    TuningFreezeEvidence,
)
from autovla.models.families.specification import ModelFamilyDefinition

ProcessorT = TypeVar("ProcessorT")
BackboneT = TypeVar("BackboneT")
ActionHeadT = TypeVar("ActionHeadT")
ModelT = TypeVar("ModelT")
CheckpointAdapterT = TypeVar("CheckpointAdapterT")
PolicyBundleT = TypeVar("PolicyBundleT")


@dataclass(frozen=True, slots=True)
class ModelRuntimeBundle(
    Generic[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
):
    """绑定训练消费的真实对象、运行档案和唯一装配证据。

    该对象只持有 ``ModelAssemblyResult`` 的引用,不会复制参数、移动张量或
    导入 Torch。处理器、模型、checkpoint 适配器和调优/冻结计划均从唯一
    装配结果读取,从而避免形成第二套构造栈。
    """

    assembly_result: ModelAssemblyResult[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
    family_definition: ModelFamilyDefinition
    runtime_profile_identity: str
    asset_evidence: ModelRuntimeAssetEvidence

    def __post_init__(self) -> None:
        """拒绝计划、家族、运行档案或资产证据身份漂移。"""

        if not isinstance(self.assembly_result, ModelAssemblyResult):
            raise TypeError("assembly_result must be ModelAssemblyResult")
        if not isinstance(self.family_definition, ModelFamilyDefinition):
            raise TypeError("family_definition must be ModelFamilyDefinition")
        if self.assembly_result.plan.definition is not self.family_definition:
            raise ValueError("runtime bundle must retain the assembly plan family definition")
        if not self.runtime_profile_identity.strip():
            raise ValueError("runtime_profile_identity must not be empty")
        if type(self.asset_evidence) is not ModelRuntimeAssetEvidence:
            raise TypeError("asset_evidence must be ModelRuntimeAssetEvidence")
        if (
            self.asset_evidence.asset_bundle_fingerprint
            != self.assembly_result.plan.asset_bundle_fingerprint
        ):
            raise ValueError("runtime asset evidence drifted from assembly plan")

    @property
    def processor(self) -> ProcessorT:
        """返回装配结果中的真实处理器对象。"""

        return self.assembly_result.processor

    @property
    def model(self) -> ModelT:
        """返回模型对象,但不在元数据导入路径检查或导入 Torch。"""

        return self.assembly_result.model

    @property
    def checkpoint_adapter(self) -> CheckpointAdapterT:
        """返回装配结果中的 checkpoint 适配器。"""

        return self.assembly_result.checkpoint_adapter

    @property
    def checkpoint_evidence(self) -> CheckpointLoadEvidence:
        """返回唯一装配结果中的 checkpoint 加载证据。"""

        return self.assembly_result.checkpoint_load

    @property
    def tuning_freeze_plan(self) -> TuningFreezeEvidence:
        """返回唯一装配结果中的调优和冻结证据。"""

        return self.assembly_result.tuning_freeze


__all__ = ["ModelRuntimeBundle"]
