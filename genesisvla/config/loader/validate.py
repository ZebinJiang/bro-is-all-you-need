"""GenesisVLA 配置构造与校验。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from genesisvla.config.schema import (
    DataConfig,
    ExperimentConfig,
    ModelConfig,
    RunnerBackend,
    RunnerConfig,
)


def _require_schema_version(version: str, field_name: str) -> None:
    """确认 schema 版本符合 M1 契约。"""
    if version != "1.0":
        raise ValueError(f"{field_name} must be '1.0'")


def _require_non_empty(value: str, field_name: str) -> None:
    """确认字符串字段去除空白后非空。"""
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """读取嵌套配置段并确认它是映射。"""
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a mapping")
    return cast(Mapping[str, Any], value)


def _str_value(data: Mapping[str, Any], key: str, default: str) -> str:
    """读取字符串字段并执行基础类型转换。"""
    return str(data.get(key, default))


def _int_value(data: Mapping[str, Any], key: str, default: int) -> int:
    """读取整数字段并执行基础类型转换。"""
    value = data.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return int(value)


def _tuple_str(data: Mapping[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """读取字符串元组字段,支持 YAML 列表输入。"""
    value = data.get(key, default)
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{key} must be a list of strings")
    values = cast(list[Any] | tuple[Any, ...], value)
    return tuple(str(item) for item in values)


def _model_config(data: Mapping[str, Any]) -> ModelConfig:
    """从普通字典构造模型配置。"""
    default = ModelConfig()
    return ModelConfig(
        schema_version=_str_value(data, "schema_version", default.schema_version),
        name=_str_value(data, "name", default.name),
        registry_key=_str_value(data, "registry_key", default.registry_key),
    )


def _data_config(data: Mapping[str, Any]) -> DataConfig:
    """从普通字典构造数据配置。"""
    default = DataConfig()
    return DataConfig(
        schema_version=_str_value(data, "schema_version", default.schema_version),
        name=_str_value(data, "name", default.name),
        root=_str_value(data, "root", default.root),
        required_modalities=_tuple_str(data, "required_modalities", default.required_modalities),
    )


def _runner_config(data: Mapping[str, Any]) -> RunnerConfig:
    """从普通字典构造运行器配置。"""
    default = RunnerConfig()
    raw_backend = data.get("backend", default.backend)
    if not isinstance(raw_backend, (str, RunnerBackend)):
        raise ValueError("runner.backend must be a string")
    return RunnerConfig(
        schema_version=_str_value(data, "schema_version", default.schema_version),
        backend=RunnerBackend.from_value(raw_backend),
        batch_size=_int_value(data, "batch_size", default.batch_size),
        max_steps=_int_value(data, "max_steps", default.max_steps),
        device=_str_value(data, "device", default.device),
    )


def build_experiment_config(data: Mapping[str, Any]) -> ExperimentConfig:
    """从解析后的普通字典构造顶层实验配置。

    Args:
        data: 已解析的配置字典。

    Returns:
        构造并校验后的 ``ExperimentConfig``。
    """
    default = ExperimentConfig()
    config = ExperimentConfig(
        schema_version=_str_value(data, "schema_version", default.schema_version),
        name=_str_value(data, "name", default.name),
        seed=_int_value(data, "seed", default.seed),
        model=_model_config(_section(data, "model")),
        data=_data_config(_section(data, "data")),
        runner=_runner_config(_section(data, "runner")),
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
    _require_non_empty(config.name, "name")
    _require_non_empty(config.model.name, "model.name")
    _require_non_empty(config.model.registry_key, "model.registry_key")
    _require_non_empty(config.data.name, "data.name")
    _require_non_empty(config.data.root, "data.root")
    _require_non_empty(config.runner.device, "runner.device")
    if config.seed < 0:
        raise ValueError("seed must be non-negative")
    if config.runner.batch_size <= 0:
        raise ValueError("runner.batch_size must be positive")
    if config.runner.max_steps <= 0:
        raise ValueError("runner.max_steps must be positive")
    if not config.data.required_modalities:
        raise ValueError("data.required_modalities must not be empty")
    return config
