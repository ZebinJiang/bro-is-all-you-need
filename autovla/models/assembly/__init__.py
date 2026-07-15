"""模型组装请求、计划、结果和运行时工厂的轻量公共入口。"""

from autovla.models.assembly.contracts import (
    LOCAL_INITIALIZATION_CONTEXT_FACTORY,
    ActionHeadFactory,
    AssemblyEvidenceIdentity,
    AssemblyInitializationContextFactory,
    CheckpointAdapterFactory,
    CheckpointLoadEvidence,
    CheckpointShapeMismatch,
    LocalInitializationContextFactory,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    ModelFactory,
    ModelProcessorFactory,
    PolicyBundleFactory,
    TuningFreezeEvidence,
    VisionLanguageBackboneFactory,
)
from autovla.models.assembly.plan import (
    AssemblyFactories,
    ModelAssemblyPlan,
    ModelConfigIdentity,
    ModelRuntimeSupportError,
    resolve_model_assembly,
)

__all__ = [
    "LOCAL_INITIALIZATION_CONTEXT_FACTORY",
    "ActionHeadFactory",
    "AssemblyEvidenceIdentity",
    "AssemblyFactories",
    "AssemblyInitializationContextFactory",
    "CheckpointAdapterFactory",
    "CheckpointLoadEvidence",
    "CheckpointShapeMismatch",
    "LocalInitializationContextFactory",
    "ModelAssemblyPlan",
    "ModelAssemblyRequest",
    "ModelAssemblyResult",
    "ModelConfigIdentity",
    "ModelFactory",
    "ModelProcessorFactory",
    "ModelRuntimeSupportError",
    "PolicyBundleFactory",
    "TuningFreezeEvidence",
    "VisionLanguageBackboneFactory",
    "resolve_model_assembly",
]
