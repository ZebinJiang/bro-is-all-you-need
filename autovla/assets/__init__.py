"""不导入 Torch、Transformers 或网络 SDK 的模型资产公共 API。"""

from autovla.assets.bundles import (
    EAGLE_SUPPORT_SUBDIRECTORY,
    GR00T_N1D6_BUNDLE_REQUIREMENTS,
    Gr00tModelAssetBundle,
    ModelAssetBundleRequirement,
    VerifiedModelAssetBundle,
)
from autovla.assets.contracts import (
    AssetLicenseRecord,
    AssetProvenanceRecord,
    ImmutableJsonValue,
    ModelAssetAcquisition,
    ModelAssetBundle,
    ModelAssetFile,
    ModelAssetManifest,
    ModelAssetProvider,
    ModelAssetSpec,
    ResolvedModelAsset,
)
from autovla.assets.errors import (
    MissingModelAssetError,
    ModelAssetConfigurationError,
    ModelAssetContainmentError,
    ModelAssetError,
    ModelAssetIntegrityError,
    ModelAssetLockError,
    ModelAssetProviderError,
    StaleModelAssetLockError,
)
from autovla.assets.providers import HuggingFaceModelAssetProvider, LocalModelAssetProvider
from autovla.assets.registry import (
    DEFAULT_MODEL_ASSET_REGISTRY,
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
    ModelAssetRegistry,
)
from autovla.assets.store import ModelAssetResolver, ModelAssetStore, resolve_model_asset_root

__all__ = [
    "DEFAULT_MODEL_ASSET_REGISTRY",
    "EAGLE_SUPPORT_SUBDIRECTORY",
    "GR00T_N1D6_ASSET_SPEC",
    "GR00T_N1D6_BUNDLE_REQUIREMENTS",
    "GR00T_N1D6_EAGLE_SUPPORT_SPEC",
    "AssetLicenseRecord",
    "AssetProvenanceRecord",
    "Gr00tModelAssetBundle",
    "HuggingFaceModelAssetProvider",
    "ImmutableJsonValue",
    "LocalModelAssetProvider",
    "MissingModelAssetError",
    "ModelAssetAcquisition",
    "ModelAssetBundle",
    "ModelAssetBundleRequirement",
    "ModelAssetConfigurationError",
    "ModelAssetContainmentError",
    "ModelAssetError",
    "ModelAssetFile",
    "ModelAssetIntegrityError",
    "ModelAssetLockError",
    "ModelAssetManifest",
    "ModelAssetProvider",
    "ModelAssetProviderError",
    "ModelAssetRegistry",
    "ModelAssetResolver",
    "ModelAssetSpec",
    "ModelAssetStore",
    "ResolvedModelAsset",
    "StaleModelAssetLockError",
    "VerifiedModelAssetBundle",
    "resolve_model_asset_root",
]
