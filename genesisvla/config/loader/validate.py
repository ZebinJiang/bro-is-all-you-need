"""GenesisVLA 配置构造与校验。"""

from __future__ import annotations

from collections.abc import Mapping
from difflib import get_close_matches
from typing import Any, cast

from genesisvla.config.schema import (
    AccelerationConfig,
    DataConfig,
    DeploymentConfig,
    ExperimentConfig,
    ModelConfig,
    RunnerBackend,
    RunnerConfig,
)

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "name",
        "seed",
        "model",
        "data",
        "runner",
        "deployment",
        "acceleration",
    }
)
MODEL_KEYS = frozenset({"schema_version", "name", "registry_key"})
DATA_KEYS = frozenset({"schema_version", "name", "root", "required_modalities"})
RUNNER_KEYS = frozenset(
    {
        "schema_version",
        "backend",
        "batch_size",
        "max_steps",
        "device",
        "learning_rate",
        "grad_accumulation_steps",
        "action_horizon",
        "action_dim",
        "timeout",
    }
)
DEPLOYMENT_KEYS = frozenset({"schema_version", "enabled", "timeout"})
ACCELERATION_KEYS = frozenset({"schema_version", "enabled", "mixed_precision"})


def _reject_unknown_keys(
    data: Mapping[str, Any], allowed: frozenset[str], prefix: str = ""
) -> None:
    """拒绝未知配置键,避免 YAML 或 dotlist 拼写错误被静默忽略。"""
    for key in data:
        dotted_key = f"{prefix}.{key}" if prefix else str(key)
        if key not in allowed:
            message = f"unknown config key: {dotted_key}"
            matches = get_close_matches(str(key), tuple(allowed), n=1, cutoff=0.72)
            if matches:
                suggestion = f"{prefix}.{matches[0]}" if prefix else matches[0]
                message = f"{message}; did you mean {suggestion}"
            raise ValueError(message)


def _require_schema_version(version: object, field_name: str) -> None:
    """确认 schema 版本符合 M1 契约。"""
    if not isinstance(version, str):
        raise ValueError(f"{field_name} must be a string")
    if version != "1.0":
        raise ValueError(f"{field_name} must be '1.0'")


def _require_non_empty(value: object, field_name: str) -> None:
    """确认字符串字段去除空白后非空。"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_int(value: object, field_name: str) -> int:
    """确认整数字段不来自 bool、float 或其他隐式可转换类型。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _require_bool(value: object, field_name: str) -> bool:
    """确认布尔字段不来自其他隐式可转换类型。"""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_number(value: object, field_name: str) -> float:
    """确认数字字段不来自 bool、字符串或其他隐式可转换类型。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def _section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """读取嵌套配置段并确认它是映射。"""
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a mapping")
    return cast(Mapping[str, Any], value)


def _str_value(
    data: Mapping[str, Any],
    key: str,
    default: str,
    field_name: str,
) -> str:
    """读取字符串字段,拒绝非字符串值。"""
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _int_value(
    data: Mapping[str, Any],
    key: str,
    default: int,
    field_name: str,
) -> int:
    """读取整数字段,拒绝 bool、float 和字符串等隐式转换。"""
    return _require_int(data.get(key, default), field_name)


def _bool_value(
    data: Mapping[str, Any],
    key: str,
    default: bool,
    field_name: str,
) -> bool:
    """读取布尔字段,拒绝非布尔值。"""
    return _require_bool(data.get(key, default), field_name)


def _number_value(
    data: Mapping[str, Any],
    key: str,
    default: float,
    field_name: str,
) -> float:
    """读取数字字段,拒绝 bool、字符串和其他非数字值。"""
    return _require_number(data.get(key, default), field_name)


def _tuple_str(data: Mapping[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """读取字符串元组字段,拒绝非字符串成员和空字符串。"""
    value = data.get(key, default)
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{key} must be a list of strings")
    values = cast(list[Any] | tuple[Any, ...], value)
    result: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise ValueError(f"{key}[{index}] must be a string")
        if not item.strip():
            raise ValueError(f"{key}[{index}] must not be empty")
        result.append(item)
    return tuple(result)


def _model_config(data: Mapping[str, Any]) -> ModelConfig:
    """从普通字典构造模型配置。"""
    _reject_unknown_keys(data, MODEL_KEYS, "model")
    default = ModelConfig()
    return ModelConfig(
        schema_version=_str_value(
            data, "schema_version", default.schema_version, "model.schema_version"
        ),
        name=_str_value(data, "name", default.name, "model.name"),
        registry_key=_str_value(data, "registry_key", default.registry_key, "model.registry_key"),
    )


def _data_config(data: Mapping[str, Any]) -> DataConfig:
    """从普通字典构造数据配置。"""
    _reject_unknown_keys(data, DATA_KEYS, "data")
    default = DataConfig()
    return DataConfig(
        schema_version=_str_value(
            data, "schema_version", default.schema_version, "data.schema_version"
        ),
        name=_str_value(data, "name", default.name, "data.name"),
        root=_str_value(data, "root", default.root, "data.root"),
        required_modalities=_tuple_str(data, "required_modalities", default.required_modalities),
    )


def _runner_config(data: Mapping[str, Any]) -> RunnerConfig:
    """从普通字典构造运行器配置。"""
    _reject_unknown_keys(data, RUNNER_KEYS, "runner")
    default = RunnerConfig()
    raw_backend = data.get("backend", default.backend)
    if not isinstance(raw_backend, (str, RunnerBackend)):
        raise ValueError("runner.backend must be a string")
    return RunnerConfig(
        schema_version=_str_value(
            data, "schema_version", default.schema_version, "runner.schema_version"
        ),
        backend=RunnerBackend.from_value(raw_backend),
        batch_size=_int_value(data, "batch_size", default.batch_size, "runner.batch_size"),
        max_steps=_int_value(data, "max_steps", default.max_steps, "runner.max_steps"),
        device=_str_value(data, "device", default.device, "runner.device"),
        learning_rate=_number_value(
            data, "learning_rate", default.learning_rate, "runner.learning_rate"
        ),
        grad_accumulation_steps=_int_value(
            data,
            "grad_accumulation_steps",
            default.grad_accumulation_steps,
            "runner.grad_accumulation_steps",
        ),
        action_horizon=_int_value(
            data, "action_horizon", default.action_horizon, "runner.action_horizon"
        ),
        action_dim=_int_value(data, "action_dim", default.action_dim, "runner.action_dim"),
        timeout=_number_value(data, "timeout", default.timeout, "runner.timeout"),
    )


def _deployment_config(data: Mapping[str, Any]) -> DeploymentConfig:
    """从普通字典构造部署占位配置。"""
    _reject_unknown_keys(data, DEPLOYMENT_KEYS, "deployment")
    default = DeploymentConfig()
    return DeploymentConfig(
        schema_version=_str_value(
            data, "schema_version", default.schema_version, "deployment.schema_version"
        ),
        enabled=_bool_value(data, "enabled", default.enabled, "deployment.enabled"),
        timeout=_number_value(data, "timeout", default.timeout, "deployment.timeout"),
    )


def _acceleration_config(data: Mapping[str, Any]) -> AccelerationConfig:
    """从普通字典构造加速占位配置。"""
    _reject_unknown_keys(data, ACCELERATION_KEYS, "acceleration")
    default = AccelerationConfig()
    return AccelerationConfig(
        schema_version=_str_value(
            data, "schema_version", default.schema_version, "acceleration.schema_version"
        ),
        enabled=_bool_value(data, "enabled", default.enabled, "acceleration.enabled"),
        mixed_precision=_str_value(
            data,
            "mixed_precision",
            default.mixed_precision,
            "acceleration.mixed_precision",
        ),
    )


def build_experiment_config(data: Mapping[str, Any]) -> ExperimentConfig:
    """从解析后的普通字典构造顶层实验配置。

    Args:
        data: 已解析的配置字典。

    Returns:
        构造并校验后的 ``ExperimentConfig``。
    """
    _reject_unknown_keys(data, TOP_LEVEL_KEYS)
    default = ExperimentConfig()
    config = ExperimentConfig(
        schema_version=_str_value(data, "schema_version", default.schema_version, "schema_version"),
        name=_str_value(data, "name", default.name, "name"),
        seed=_int_value(data, "seed", default.seed, "seed"),
        model=_model_config(_section(data, "model")),
        data=_data_config(_section(data, "data")),
        runner=_runner_config(_section(data, "runner")),
        deployment=_deployment_config(_section(data, "deployment")),
        acceleration=_acceleration_config(_section(data, "acceleration")),
    )
    return validate(config)


def validate(config: ExperimentConfig) -> ExperimentConfig:
    """校验 M1 顶层配置并返回原对象。

    Args:
        config: 待校验的实验配置。

    Returns:
        校验通过的同一个配置对象。

    Raises:
        ValueError: 当字段违反 M1 schema 约束时抛出。
    """
    _require_schema_version(config.schema_version, "schema_version")
    _require_schema_version(config.model.schema_version, "model.schema_version")
    _require_schema_version(config.data.schema_version, "data.schema_version")
    _require_schema_version(config.runner.schema_version, "runner.schema_version")
    _require_schema_version(config.deployment.schema_version, "deployment.schema_version")
    _require_schema_version(config.acceleration.schema_version, "acceleration.schema_version")
    _require_non_empty(config.name, "name")
    _require_non_empty(config.model.name, "model.name")
    _require_non_empty(config.model.registry_key, "model.registry_key")
    _require_non_empty(config.data.name, "data.name")
    _require_non_empty(config.data.root, "data.root")
    _require_non_empty(config.runner.device, "runner.device")
    _require_non_empty(config.acceleration.mixed_precision, "acceleration.mixed_precision")
    seed = _require_int(config.seed, "seed")
    batch_size = _require_int(config.runner.batch_size, "runner.batch_size")
    max_steps = _require_int(config.runner.max_steps, "runner.max_steps")
    learning_rate = _require_number(config.runner.learning_rate, "runner.learning_rate")
    grad_accumulation_steps = _require_int(
        config.runner.grad_accumulation_steps, "runner.grad_accumulation_steps"
    )
    action_horizon = _require_int(config.runner.action_horizon, "runner.action_horizon")
    action_dim = _require_int(config.runner.action_dim, "runner.action_dim")
    runner_timeout = _require_number(config.runner.timeout, "runner.timeout")
    deployment_timeout = _require_number(config.deployment.timeout, "deployment.timeout")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if batch_size <= 0:
        raise ValueError("runner.batch_size must be positive")
    if max_steps <= 0:
        raise ValueError("runner.max_steps must be positive")
    if learning_rate <= 0:
        raise ValueError("runner.learning_rate must be positive")
    if grad_accumulation_steps <= 0:
        raise ValueError("runner.grad_accumulation_steps must be positive")
    if action_horizon <= 0:
        raise ValueError("runner.action_horizon must be positive")
    if action_dim <= 0:
        raise ValueError("runner.action_dim must be positive")
    if runner_timeout <= 0:
        raise ValueError("runner.timeout must be positive")
    if deployment_timeout <= 0:
        raise ValueError("deployment.timeout must be positive")
    if not config.data.required_modalities:
        raise ValueError("data.required_modalities must not be empty")
    modalities = cast(tuple[object, ...], config.data.required_modalities)
    for index, modality in enumerate(modalities):
        if not isinstance(modality, str):
            raise ValueError(f"data.required_modalities[{index}] must be a string")
        if not modality.strip():
            raise ValueError(f"data.required_modalities[{index}] must not be empty")
    return config
