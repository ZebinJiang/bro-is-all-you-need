"""AutoVLA 严格配置构造与跨段校验。"""

from __future__ import annotations

import types
import warnings
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import MISSING, fields, is_dataclass, replace
from difflib import get_close_matches
from enum import Enum
from typing import Any, Literal, TypeVar, cast, get_args, get_origin, get_type_hints

from autovla.config.errors import ConfigurationError, UnknownConfigurationFieldError
from autovla.config.schema import (
    AccelerationConfig,
    AssetConfig,
    EnvironmentConfig,
    ExperimentConfig,
    RunnerBackend,
    RunnerConfig,
)

C = TypeVar("C")


def _unknown_field(path: str, key: str, allowed: tuple[str, ...]) -> None:
    """构造带近似字段建议的未知字段异常。"""
    dotted = f"{path}.{key}" if path else key
    message = f"unknown config key: {dotted}"
    matches = get_close_matches(key, allowed, n=1, cutoff=0.72)
    if matches:
        suggestion = f"{path}.{matches[0]}" if path else matches[0]
        message = f"{message}; did you mean {suggestion}"
    raise UnknownConfigurationFieldError(message)


def _coerce_scalar(value: object, annotation: type[object], path: str) -> object:
    """严格构造基础标量,不执行字符串或数字隐式转换。"""
    if annotation is bool:
        if not isinstance(value, bool):
            raise ConfigurationError(f"{path} must be a boolean")
        return value
    if annotation is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigurationError(f"{path} must be an integer")
        return value
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigurationError(f"{path} must be a number")
        return float(value)
    if annotation is str:
        if not isinstance(value, str):
            raise ConfigurationError(f"{path} must be a string")
        return value
    return value


def _coerce(value: object, annotation: object, path: str) -> object:
    """依据解析后的类型注解递归构造严格不可变值。"""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        if value not in args or type(value) not in {type(item) for item in args}:
            choices = ", ".join(repr(item) for item in args)
            raise ConfigurationError(f"{path} must be one of: {choices}")
        return value
    if origin in (types.UnionType, getattr(types, "UnionType", object)) or (
        origin is not None and type(None) in args
    ):
        if value is None and type(None) in args:
            return None
        failures: list[Exception] = []
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _coerce(value, candidate, path)
            except (ConfigurationError, TypeError, ValueError) as exc:
                failures.append(exc)
        if failures:
            for failure in failures:
                if isinstance(failure, UnknownConfigurationFieldError):
                    raise failure
            raise ConfigurationError(f"{path} has an invalid value") from failures[-1]
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ConfigurationError(f"{path} must be a list of strings")
        item_type = args[0] if args else object
        values = cast(list[object] | tuple[object, ...], value)
        return tuple(
            _coerce(item, item_type, f"{path}[{index}]") for index, item in enumerate(values)
        )
    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, Mapping):
            raise ConfigurationError(f"{path} must be a mapping")
        return _build(annotation, cast(Mapping[str, object], value), path)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            return annotation(value)
        except (TypeError, ValueError) as exc:
            choices = ", ".join(str(item.value) for item in annotation)
            raise ConfigurationError(f"{path} must be one of: {choices}") from exc
    if annotation in (bool, int, float, str):
        return _coerce_scalar(value, cast(type[object], annotation), path)
    return value


def _build(config_type: type[C], data: Mapping[str, object], path: str) -> C:
    """递归构造一个 dataclass 配置并拒绝所有未知字段。"""
    config_fields = {item.name: item for item in fields(cast(Any, config_type))}
    allowed = tuple(name for name in config_fields if not name.startswith("_"))
    for key in data:
        if key not in allowed:
            _unknown_field(path, str(key), allowed)
    hints = get_type_hints(config_type)
    values: dict[str, object] = {}
    for name, field_info in config_fields.items():
        if name in data:
            dotted = f"{path}.{name}" if path else name
            values[name] = _coerce(data[name], hints[name], dotted)
        elif field_info.default is MISSING and field_info.default_factory is MISSING:
            dotted = f"{path}.{name}" if path else name
            raise ConfigurationError(f"missing required config field: {dotted}")
    try:
        return config_type(**values)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(str(exc)) from exc


def _path_value(data: Mapping[str, object], path: tuple[str, ...]) -> tuple[bool, object | None]:
    """读取显式规范路径并区分缺失值与显式 ``None``。"""
    current: Mapping[str, object] = data
    for index, part in enumerate(path):
        if part not in current:
            return False, None
        value = current[part]
        if index == len(path) - 1:
            return True, value
        if not isinstance(value, Mapping):
            raise ConfigurationError(f"{'.'.join(path[: index + 1])} must be a mapping")
        current = cast(Mapping[str, object], value)
    return False, None


def _set_path(data: dict[str, object], path: tuple[str, ...], value: object) -> None:
    """在普通配置字典中创建或设置一个规范嵌套路径。"""
    current = data
    for index, part in enumerate(path[:-1]):
        child = current.get(part)
        if child is None:
            next_mapping: dict[str, object] = {}
            current[part] = next_mapping
            current = next_mapping
            continue
        if not isinstance(child, dict):
            raise ConfigurationError(f"{'.'.join(path[: index + 1])} must be a mapping")
        current = cast(dict[str, object], child)
    current[path[-1]] = value


def _translate_value(
    data: dict[str, object],
    *,
    legacy_path: str,
    canonical_path: tuple[str, ...],
    value: object,
) -> None:
    """写入规范值并拒绝显式双输入冲突。"""
    exists, canonical_value = _path_value(data, canonical_path)
    if exists and canonical_value != value:
        raise ConfigurationError(
            f"conflicting legacy and canonical config values: {legacy_path}={value!r} "
            f"but {'.'.join(canonical_path)}={canonical_value!r}"
        )
    _set_path(data, canonical_path, value)


def _legacy_precision(config: AccelerationConfig) -> str:
    """把旧加速开关确定性映射到规范精度模式。"""
    value = config.mixed_precision.lower()
    if not config.enabled:
        if value != "none":
            raise ConfigurationError(
                "acceleration.mixed_precision must be 'none' when acceleration.enabled is false"
            )
        return "float32"
    if value in {"bf16", "bfloat16"}:
        return "bfloat16"
    if value in {"fp16", "float16"}:
        return "float16"
    raise ConfigurationError(
        "enabled acceleration.mixed_precision must be one of bf16, bfloat16, fp16, float16"
    )


def _translate_legacy_sections(
    data: Mapping[str, object],
) -> tuple[dict[str, object], RunnerConfig, AssetConfig]:
    """把旧 runner/acceleration 输入翻译为唯一规范配置。

    旧字段仅作为输入别名。映射字段进入 Data/Training 后从规范值派生读取
    视图,未有规范归属的旧适配器字段保存在冻结兼容状态中。
    """
    output = deepcopy(dict(data))
    run_value = output.get("run")
    if run_value is not None and not isinstance(run_value, Mapping):
        raise ConfigurationError("run must be a mapping")
    run = {} if run_value is None else dict(cast(Mapping[str, object], run_value))
    for legacy_name in ("name", "seed"):
        if legacy_name in output:
            value = output.pop(legacy_name)
            if legacy_name in run and run[legacy_name] != value:
                raise ConfigurationError(f"conflicting legacy and canonical run.{legacy_name}")
            run[legacy_name] = value
    if run:
        output["run"] = run

    assets_value = output.pop("assets", None)
    assets_compatibility = AssetConfig()
    if assets_value is not None:
        if not isinstance(assets_value, Mapping):
            raise ConfigurationError("assets must be a mapping")
        assets_compatibility = _build(
            AssetConfig,
            cast(Mapping[str, object], assets_value),
            "assets",
        )

    environment_value = output.pop("environment", None)
    if environment_value is not None:
        if not isinstance(environment_value, Mapping):
            raise ConfigurationError("environment must be a mapping")
        environment = _build(
            EnvironmentConfig,
            cast(Mapping[str, object], environment_value),
            "environment",
        )
        _translate_value(
            output,
            legacy_path="environment.precision",
            canonical_path=("topology", "precision", "mode"),
            value=environment.precision,
        )
    runner_value = output.pop("runner", None)
    runner_compatibility = RunnerConfig()
    if runner_value is not None:
        if not isinstance(runner_value, Mapping):
            raise ConfigurationError("runner must be a mapping")
        runner_data = cast(Mapping[str, object], runner_value)
        runner_compatibility = _build(RunnerConfig, runner_data, "runner")
        if runner_compatibility.device != "cuda":
            warnings.warn(
                "legacy runner.device is metadata-only and no longer selects a model runtime; "
                "canonical production training remains CUDA-only",
                DeprecationWarning,
                stacklevel=3,
            )
        backend_map = {
            RunnerBackend.LOCAL: "single_gpu",
            RunnerBackend.DDP: "distributed_data_parallel",
            RunnerBackend.DEEPSPEED: "deepspeed",
        }
        if "backend" in runner_data:
            try:
                strategy_key = backend_map[runner_compatibility.backend]
            except KeyError as exc:
                raise ConfigurationError(
                    f"runner.backend {runner_compatibility.backend.value!r} has no canonical "
                    "TrainingStrategy mapping"
                ) from exc
            _translate_value(
                output,
                legacy_path="runner.backend",
                canonical_path=("training", "distributed", "strategy_key"),
                value=strategy_key,
            )
        mappings = (
            ("batch_size", ("data", "loader", "batch_size")),
            ("max_steps", ("training", "max_steps")),
            ("learning_rate", ("training", "optimization", "learning_rate")),
            (
                "grad_accumulation_steps",
                ("training", "gradient_accumulation_steps"),
            ),
        )
        for legacy_name, canonical_path in mappings:
            if legacy_name in runner_data:
                _translate_value(
                    output,
                    legacy_path=f"runner.{legacy_name}",
                    canonical_path=canonical_path,
                    value=getattr(runner_compatibility, legacy_name),
                )

    acceleration_value = output.pop("acceleration", None)
    if acceleration_value is not None:
        if not isinstance(acceleration_value, Mapping):
            raise ConfigurationError("acceleration must be a mapping")
        acceleration_data = cast(Mapping[str, object], acceleration_value)
        acceleration = _build(
            AccelerationConfig,
            acceleration_data,
            "acceleration",
        )
        _translate_value(
            output,
            legacy_path="acceleration",
            canonical_path=("training", "precision", "mode"),
            value=_legacy_precision(acceleration),
        )
    training_value = output.get("training")
    if training_value is not None:
        if not isinstance(training_value, Mapping):
            raise ConfigurationError("training must be a mapping")
        training = dict(cast(Mapping[str, object], training_value))
        promotions = {
            "optimization": ("optimization",),
            "distributed": ("topology", "distributed"),
            "precision": ("topology", "precision"),
            "checkpoint": ("checkpoint",),
            "logging": ("telemetry", "logging"),
        }
        for legacy_name, canonical_path in promotions.items():
            if legacy_name in training:
                _translate_value(
                    output,
                    legacy_path=f"training.{legacy_name}",
                    canonical_path=canonical_path,
                    value=training.pop(legacy_name),
                )
        output["training"] = training
    return output, runner_compatibility, assets_compatibility


def build_experiment_config(data: Mapping[str, object]) -> ExperimentConfig:
    """从普通映射构造并校验唯一实验配置根。"""
    translated, runner_compatibility, assets_compatibility = _translate_legacy_sections(data)
    config = _build(ExperimentConfig, translated, "")
    return validate(
        replace(
            config,
            _runner_compatibility=runner_compatibility,
            _assets_compatibility=assets_compatibility,
        )
    )


def validate(config: ExperimentConfig) -> ExperimentConfig:
    """执行跨段能力和本地安全约束并返回同一对象。"""
    datasets = config.data.datasets
    if datasets and config.data.backend is not None:
        if any(dataset.backend != config.data.backend for dataset in datasets):
            raise ConfigurationError(
                "data.backend compatibility field cannot override per-dataset backend keys"
            )
    if config.topology.distributed.world_size > 1 and config.data.loader.num_workers < 0:
        raise ConfigurationError("distributed data loader worker count must be non-negative")
    if config.model.checkpoint_path is not None and not config.model.local_files_only:
        raise ConfigurationError("model checkpoint paths must remain local-only")
    if config.model.asset_key is not None and config.model.checkpoint_path is not None:
        raise ConfigurationError(
            "model.asset_key and legacy model.checkpoint_path are mutually exclusive"
        )
    if not config.checkpoint.save_optimizer:
        raise ConfigurationError("production training checkpoints require save_optimizer=true")
    distributed = config.topology.distributed
    if distributed.strategy_key in {
        "distributed_data_parallel",
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
    } and (config.topology.precision.mode != "bfloat16"):
        raise ConfigurationError(
            "production DDP and DeepSpeed require training.precision.mode=bfloat16"
        )
    if distributed.strategy_key.startswith("deepspeed_zero_"):
        deepspeed = distributed.deepspeed
        if deepspeed is None:
            raise ConfigurationError("deepspeed strategy requires training.distributed.deepspeed")
        if not deepspeed.bf16_enabled or deepspeed.fp16_enabled:
            raise ConfigurationError("production DeepSpeed requires bf16 enabled and fp16 disabled")
    if config.model.registry_key == "gr00t_n1d6" and config.model.architecture_variant not in {
        "official_n1d6",
        "reduced_runtime",
    }:
        raise ConfigurationError(
            "gr00t_n1d6 requires model.architecture_variant official_n1d6 or reduced_runtime"
        )
    if config.run.intent != "training":
        return config
    if config.model.architecture_variant == "reduced_runtime":
        if config.model.asset_key is not None:
            raise ConfigurationError("reduced_runtime forbids model.asset_key")
        if config.model.checkpoint_path is not None:
            raise ConfigurationError(
                "reduced_runtime uses random initialization and forbids model.checkpoint_path"
            )
        if config.model.eagle_asset_path is None:
            raise ConfigurationError(
                "reduced_runtime requires explicit local model.eagle_asset_path"
            )
    elif config.model.registry_key == "gr00t_n1d6":
        if config.model.asset_key is None and config.model.checkpoint_path is None:
            raise ConfigurationError(
                "official gr00t_n1d6 requires model.asset_key='gr00t_n1d6' or one legacy "
                "checkpoint_path migration input"
            )
        if config.model.asset_key not in {None, "gr00t_n1d6"}:
            raise ConfigurationError("official gr00t_n1d6 requires asset key gr00t_n1d6")
        if config.model.eagle_asset_path is None:
            raise ConfigurationError(
                "official gr00t_n1d6 requires explicit local model.eagle_asset_path because "
                "Eagle revision/license metadata is unresolved"
            )
    return config


__all__ = ["build_experiment_config", "validate"]
