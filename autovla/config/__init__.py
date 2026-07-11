"""AutoVLA 严格配置公共接口。"""

from autovla.config.composition import compose_mapping
from autovla.config.errors import (
    ConfigurationCompositionError,
    ConfigurationError,
    ConfigurationOverrideError,
    UnknownConfigurationFieldError,
)
from autovla.config.loader import (
    build_experiment_config,
    export_resolved_yaml,
    load_yaml,
    merge_cli,
    resolved_config_fingerprint,
    to_resolved_dict,
    validate,
)
from autovla.config.overrides import apply_dotted_overrides
from autovla.config.schema import (
    CheckpointConfig,
    DataConfig,
    DataLoaderConfig,
    DatasetConfig,
    DatasetMixConfig,
    DeploymentConfig,
    DistributedConfig,
    ExperimentConfig,
    LearningRateSchedulerConfig,
    LoggingConfig,
    ModelConfig,
    OptimizationConfig,
    PrecisionConfig,
    TrainingConfig,
)

__all__ = [
    "CheckpointConfig",
    "ConfigurationCompositionError",
    "ConfigurationError",
    "ConfigurationOverrideError",
    "DataConfig",
    "DataLoaderConfig",
    "DatasetConfig",
    "DatasetMixConfig",
    "DeploymentConfig",
    "DistributedConfig",
    "ExperimentConfig",
    "LearningRateSchedulerConfig",
    "LoggingConfig",
    "ModelConfig",
    "OptimizationConfig",
    "PrecisionConfig",
    "TrainingConfig",
    "UnknownConfigurationFieldError",
    "apply_dotted_overrides",
    "build_experiment_config",
    "compose_mapping",
    "export_resolved_yaml",
    "load_yaml",
    "merge_cli",
    "resolved_config_fingerprint",
    "to_resolved_dict",
    "validate",
]
