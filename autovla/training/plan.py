"""训练组合根解析出的不可变执行计划。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import cast

from autovla.config.schema import ExperimentConfig
from autovla.config.schema.data import DataConfig, DatasetConfig
from autovla.data.backends.base import dataset_config_fingerprint
from autovla.models.assembly import ModelAssemblyPlan
from autovla.training.checkpointing.identity import stable_fingerprint
from autovla.training.telemetry.data import DATA_TELEMETRY_SCHEMA


def _text(value: object, name: str) -> str:
    """校验一个精确非空文本身份。"""
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _texts(values: object, name: str) -> tuple[str, ...]:
    """校验一组稳定非空身份。"""
    if type(values) is not tuple:
        raise TypeError(f"{name} must be a tuple")
    raw_values = cast(tuple[object, ...], values)
    if any(type(value) is not str or not value.strip() for value in raw_values):
        raise ValueError(f"{name} must contain non-empty text identities")
    return cast(tuple[str, ...], raw_values)


def _empty_provenance() -> dict[str, str]:
    """返回类型明确的空 provenance 映射。"""
    return {}


def _is_model_assembly_plan(value: object) -> bool:
    """在配置组合边界校验 canonical 模型组装计划。"""
    return type(value) is ModelAssemblyPlan


@dataclass(frozen=True, slots=True)
class DataPlan:
    """冻结数据 manifest、来源、混合、平衡、变换和统计身份。"""

    manifest_fingerprint: str
    source_fingerprints: tuple[str, ...]
    mixture_fingerprint: str
    composition_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str

    def __post_init__(self) -> None:
        """校验所有数据身份。"""
        _texts(
            (
                self.manifest_fingerprint,
                self.mixture_fingerprint,
                self.composition_fingerprint,
                self.transform_fingerprint,
                self.statistics_fingerprint,
            ),
            "data plan",
        )
        sources = _texts(self.source_fingerprints, "data sources")
        if not sources:
            raise ValueError("data plan requires at least one source fingerprint")

    def to_dict(self) -> dict[str, object]:
        """返回稳定身份载荷。"""
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "source_fingerprints": list(self.source_fingerprints),
            "mixture_fingerprint": self.mixture_fingerprint,
            "composition_fingerprint": self.composition_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
            "statistics_fingerprint": self.statistics_fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        """返回数据计划指纹。"""
        return stable_fingerprint(self.to_dict())


@dataclass(frozen=True, slots=True)
class TopologyPlan:
    """冻结活动 GPU 训练策略和 rank 拓扑。"""

    strategy: str
    world_size: int
    precision: str
    zero_stage: int | None = None

    def __post_init__(self) -> None:
        """仅接受 single GPU、DDP 和 DeepSpeed ZeRO 1/2/3。"""
        _text(self.strategy, "topology strategy")
        _text(self.precision, "topology precision")
        if self.strategy not in {
            "single_gpu",
            "distributed_data_parallel",
            "deepspeed_zero_1",
            "deepspeed_zero_2",
            "deepspeed_zero_3",
        }:
            raise ValueError("unsupported active topology strategy")
        if type(self.world_size) is not int or self.world_size <= 0:
            raise ValueError("topology world_size must be a positive integer")
        if self.precision not in {"bfloat16", "float16", "float32"}:
            raise ValueError("unsupported topology precision")
        if self.strategy.startswith("deepspeed_zero_"):
            if type(self.zero_stage) is not int or self.zero_stage not in {1, 2, 3}:
                raise ValueError("DeepSpeed topology requires ZeRO stage 1, 2, or 3")
        elif self.zero_stage is not None:
            raise ValueError("zero_stage belongs only to DeepSpeed")

    @property
    def fingerprint(self) -> str:
        """返回拓扑身份。"""
        return stable_fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """返回可持久化拓扑身份。"""
        return {
            "strategy": self.strategy,
            "world_size": self.world_size,
            "precision": self.precision,
            "zero_stage": self.zero_stage,
        }


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    """冻结优化器、调度器、精度和梯度策略身份。"""

    optimizer: str
    scheduler: str
    precision: str
    gradient_accumulation_steps: int
    gradient_clip_norm: float | None
    fingerprint: str

    def __post_init__(self) -> None:
        """校验优化身份和累积边界。"""
        _texts((self.optimizer, self.scheduler, self.precision, self.fingerprint), "optimization")
        if (
            type(self.gradient_accumulation_steps) is not int
            or self.gradient_accumulation_steps <= 0
        ):
            raise ValueError("gradient accumulation must be a positive integer")
        if self.gradient_clip_norm is not None and (
            type(self.gradient_clip_norm) is not float
            or not math.isfinite(self.gradient_clip_norm)
            or self.gradient_clip_norm <= 0.0
        ):
            raise ValueError("gradient_clip_norm must be a positive finite float or None")

    def to_dict(self) -> dict[str, object]:
        """返回可持久化优化身份。"""
        return {
            "optimizer": self.optimizer,
            "scheduler": self.scheduler,
            "precision": self.precision,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "gradient_clip_norm": self.gradient_clip_norm,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class CheckpointPlan:
    """冻结本地 checkpoint 策略及恢复身份。"""

    backend: str
    directory: str
    resume_identity: str | None
    save_optimizer: bool
    fingerprint: str

    def __post_init__(self) -> None:
        """校验本地路径和精确布尔值。"""
        _texts((self.backend, self.directory, self.fingerprint), "checkpoint")
        if type(self.save_optimizer) is not bool or not self.save_optimizer:
            raise ValueError("production checkpoint plan must save optimizer state")
        if self.resume_identity is not None:
            _text(self.resume_identity, "checkpoint resume identity")

    def to_dict(self) -> dict[str, object]:
        """返回可持久化 checkpoint 策略身份。"""
        return {
            "backend": self.backend,
            "directory": self.directory,
            "resume_identity": self.resume_identity,
            "save_optimizer": self.save_optimizer,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class TelemetryPlan:
    """冻结 logger、callback、rank reduction 和数据遥测身份。"""

    logger_identities: tuple[str, ...]
    callback_identities: tuple[str, ...]
    reduce_across_ranks: bool
    data_telemetry_schema: str
    fingerprint: str

    def __post_init__(self) -> None:
        """校验本地遥测身份。"""
        if not _texts(self.logger_identities, "telemetry loggers"):
            raise ValueError("telemetry plan requires at least one local logger")
        if not _texts(self.callback_identities, "telemetry callbacks"):
            raise ValueError("telemetry plan requires at least one callback")
        _texts((self.data_telemetry_schema, self.fingerprint), "telemetry")
        if type(self.reduce_across_ranks) is not bool:
            raise TypeError("reduce_across_ranks must be bool")

    def to_dict(self) -> dict[str, object]:
        """返回可持久化遥测身份。"""
        return {
            "logger_identities": list(self.logger_identities),
            "callback_identities": list(self.callback_identities),
            "reduce_across_ranks": self.reduce_across_ranks,
            "data_telemetry_schema": self.data_telemetry_schema,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class TrainingPlan:
    """把唯一引擎需要的全部 resolved 身份交给 session/checkpoint。"""

    experiment_fingerprint: str
    data: DataPlan
    model_assembly: ModelAssemblyPlan
    topology: TopologyPlan
    optimization: OptimizationPlan
    checkpoint: CheckpointPlan
    telemetry: TelemetryPlan
    max_steps: int | None
    provenance: Mapping[str, str] = field(default_factory=_empty_provenance)

    def __post_init__(self) -> None:
        """校验 handoff 类型、步数和 provenance。"""
        _text(self.experiment_fingerprint, "experiment fingerprint")
        if type(self.data) is not DataPlan:
            raise TypeError("data must be the canonical DataPlan")
        if not _is_model_assembly_plan(self.model_assembly):
            raise TypeError("model_assembly must be the canonical ModelAssemblyPlan")
        if type(self.topology) is not TopologyPlan:
            raise TypeError("topology must be the canonical TopologyPlan")
        if type(self.optimization) is not OptimizationPlan:
            raise TypeError("optimization must be the canonical OptimizationPlan")
        if type(self.checkpoint) is not CheckpointPlan:
            raise TypeError("checkpoint must be the canonical CheckpointPlan")
        if type(self.telemetry) is not TelemetryPlan:
            raise TypeError("telemetry must be the canonical TelemetryPlan")
        if self.max_steps is not None and (type(self.max_steps) is not int or self.max_steps <= 0):
            raise ValueError("max_steps must be a positive integer")
        raw_provenance = cast(object, self.provenance)
        if not isinstance(raw_provenance, Mapping):
            raise TypeError("training provenance must be a mapping")
        provenance = cast(Mapping[str, str], raw_provenance)
        if any(
            type(key) is not str or type(value) is not str or not key.strip() or not value.strip()
            for key, value in provenance.items()
        ):
            raise ValueError("training provenance identities must not be empty")
        object.__setattr__(self, "provenance", MappingProxyType(dict(provenance)))

    def identity_dict(self) -> dict[str, object]:
        """返回 checkpoint manifest 使用的完整计划身份。"""
        return {
            "experiment": self.experiment_fingerprint,
            "data": self.data.fingerprint,
            "model_assembly": self.model_assembly.provenance_fingerprint,
            "topology": self.topology.fingerprint,
            "optimization": self.optimization.fingerprint,
            "checkpoint": self.checkpoint.fingerprint,
            "telemetry": self.telemetry.fingerprint,
            "max_steps": self.max_steps,
            "provenance": dict(sorted(self.provenance.items())),
        }

    @property
    def fingerprint(self) -> str:
        """返回最终训练实验身份。"""
        return stable_fingerprint(self.identity_dict())

    def to_dict(self) -> dict[str, object]:
        """返回 checkpoint provenance 使用的完整不可变计划载荷。"""
        return {
            "schema_version": "autovla.training_plan.v1",
            "fingerprint": self.fingerprint,
            "identity": self.identity_dict(),
            "experiment_fingerprint": self.experiment_fingerprint,
            "data": self.data.to_dict(),
            "model_assembly": {
                "family": self.model_assembly.definition.family_key,
                "definition": self.model_assembly.definition.fingerprint,
                "asset_bundle": self.model_assembly.asset_bundle.fingerprint,
                "transform_plan": self.model_assembly.transform_plan.fingerprint,
                "precision": self.model_assembly.precision,
                "topology": self.model_assembly.topology,
                "local_files_only": self.model_assembly.local_files_only,
                "provenance_fingerprint": self.model_assembly.provenance_fingerprint,
            },
            "topology": self.topology.to_dict(),
            "optimization": self.optimization.to_dict(),
            "checkpoint": self.checkpoint.to_dict(),
            "telemetry": self.telemetry.to_dict(),
            "max_steps": self.max_steps,
            "provenance": dict(sorted(self.provenance.items())),
        }


def _configured_datasets(config: DataConfig) -> tuple[DatasetConfig, ...]:
    """在无数据 I/O 情况下解析与 DataModule 相同的显式源配置。"""
    if config.datasets:
        return config.datasets
    if config.backend is None:
        raise ValueError("training plan requires at least one explicit data backend")
    return (
        DatasetConfig(
            name=config.name,
            backend=config.backend,
            root=config.root,
            image_keys=config.required_modalities,
        ),
    )


def resolve_training_plan(
    config: ExperimentConfig,
    model_assembly: ModelAssemblyPlan,
) -> TrainingPlan:
    """从严格实验配置和 R4 模型计划解析唯一生产训练计划。"""
    datasets = _configured_datasets(config.data)
    source_fingerprints = tuple(dataset_config_fingerprint(dataset) for dataset in datasets)
    data = DataPlan(
        manifest_fingerprint=stable_fingerprint(asdict(config.data)),
        source_fingerprints=source_fingerprints,
        mixture_fingerprint=stable_fingerprint(asdict(config.data.mix)),
        composition_fingerprint=stable_fingerprint(asdict(config.data.loader)),
        transform_fingerprint=config.transforms.plan_fingerprint,
        statistics_fingerprint=config.transforms.statistics_fingerprint,
    )
    distributed = config.topology.distributed
    zero_stage = None if distributed.deepspeed is None else distributed.deepspeed.zero_stage
    topology = TopologyPlan(
        strategy=distributed.strategy_key,
        world_size=distributed.world_size,
        precision=config.topology.precision.mode,
        zero_stage=zero_stage,
    )
    optimization_payload = {
        "optimization": asdict(config.optimization),
        "precision": config.topology.precision.mode,
        "gradient_accumulation_steps": config.training.gradient_accumulation_steps,
        "gradient_clip_norm": config.training.gradient_clip_norm,
    }
    optimization = OptimizationPlan(
        optimizer=config.optimization.optimizer_key,
        scheduler=config.optimization.scheduler.name,
        precision=config.topology.precision.mode,
        gradient_accumulation_steps=config.training.gradient_accumulation_steps,
        gradient_clip_norm=(
            None
            if config.training.gradient_clip_norm is None
            else float(config.training.gradient_clip_norm)
        ),
        fingerprint=stable_fingerprint(optimization_payload),
    )
    resume_identity = (
        None
        if config.checkpoint.resume_from is None
        else stable_fingerprint({"resume_from": config.checkpoint.resume_from})
    )
    checkpoint = CheckpointPlan(
        backend=(
            "deepspeed_distributed"
            if distributed.strategy_key.startswith("deepspeed_zero_")
            else "local_atomic"
        ),
        directory=config.checkpoint.directory,
        resume_identity=resume_identity,
        save_optimizer=config.checkpoint.save_optimizer,
        fingerprint=stable_fingerprint(asdict(config.checkpoint)),
    )
    logger_identities: list[str] = []
    if config.telemetry.logging.stdout:
        logger_identities.append("local_stdout_json")
    if config.telemetry.logging.jsonl_path is not None:
        logger_identities.append(
            "local_jsonl:" + stable_fingerprint(config.telemetry.logging.jsonl_path)
        )
    if not logger_identities:
        raise ValueError("production data telemetry requires at least one local logger sink")
    telemetry = TelemetryPlan(
        logger_identities=tuple(logger_identities),
        callback_identities=(
            "autovla.data_telemetry",
            "autovla.training.logging",
            "autovla.training.progress",
        ),
        reduce_across_ranks=config.telemetry.reduce_across_ranks,
        data_telemetry_schema=DATA_TELEMETRY_SCHEMA,
        fingerprint=stable_fingerprint(
            {
                "telemetry": asdict(config.telemetry),
                "data_telemetry_schema": DATA_TELEMETRY_SCHEMA,
            }
        ),
    )
    return TrainingPlan(
        experiment_fingerprint=config.fingerprint,
        data=data,
        model_assembly=model_assembly,
        topology=topology,
        optimization=optimization,
        checkpoint=checkpoint,
        telemetry=telemetry,
        max_steps=config.training.max_steps,
        provenance={
            "architecture_variant": config.model.architecture_variant or "unspecified",
            "backend_decision": "NO_BACKEND_WINNER",
            "composition_root": "autovla.cli.train:compose_training_engine",
            "model_family": model_assembly.definition.family_key,
        },
    )


__all__ = [
    "CheckpointPlan",
    "DataPlan",
    "OptimizationPlan",
    "TelemetryPlan",
    "TopologyPlan",
    "TrainingPlan",
    "resolve_training_plan",
]
