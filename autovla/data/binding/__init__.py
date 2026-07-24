"""AutoVLA 数据集—模型物理语义绑定公开面。"""

from autovla.data.binding.compatibility import evaluate_compatibility
from autovla.data.binding.contracts import (
    ActionBinding,
    CameraBinding,
    DatasetCompatibilityLevel,
    DatasetCompatibilityReport,
    DatasetModelBinding,
    DatasetSchema,
    EmbodimentSchema,
    LanguageBinding,
    ModelInputSchema,
    NormalizationBinding,
    PhysicalFeatureSpec,
    StateBinding,
    TemporalBinding,
    canonical_data,
    canonical_serialize,
    sha256_fingerprint,
)
from autovla.data.binding.factory import ContractBatchFactory
from autovla.data.binding.inspection import (
    BoundedDatasetSurface,
    BoundedRealSampleReport,
    inspect_bounded_dataset_surface,
)
from autovla.data.binding.provenance import ContractBatchProvenance
from autovla.data.binding.runtime import (
    BACKEND_DECISION,
    BackendBatchContext,
    BoundTrainingBatch,
    DatasetModelRuntime,
    FamilyBatchProcessor,
    PhysicalBatchProjector,
)

__all__ = [
    "BACKEND_DECISION",
    "ActionBinding",
    "BackendBatchContext",
    "BoundTrainingBatch",
    "BoundedDatasetSurface",
    "BoundedRealSampleReport",
    "CameraBinding",
    "ContractBatchFactory",
    "ContractBatchProvenance",
    "DatasetCompatibilityLevel",
    "DatasetCompatibilityReport",
    "DatasetModelBinding",
    "DatasetModelRuntime",
    "DatasetSchema",
    "EmbodimentSchema",
    "FamilyBatchProcessor",
    "LanguageBinding",
    "ModelInputSchema",
    "NormalizationBinding",
    "PhysicalBatchProjector",
    "PhysicalFeatureSpec",
    "StateBinding",
    "TemporalBinding",
    "canonical_data",
    "canonical_serialize",
    "evaluate_compatibility",
    "inspect_bounded_dataset_surface",
    "sha256_fingerprint",
]
