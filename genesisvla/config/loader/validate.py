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
        schema_version=_str_value(data, "schema_version", default.schema_version, "schema_version"),
        name=_str_value(data, "name", default.name, "name"),
        seed=_int_value(data, "seed", default.seed, "seed"),
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
    seed = _require_int(config.seed, "seed")
    batch_size = _require_int(config.runner.batch_size, "runner.batch_size")
    max_steps = _require_int(config.runner.max_steps, "runner.max_steps")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if batch_size <= 0:
        raise ValueError("runner.batch_size must be positive")
    if max_steps <= 0:
        raise ValueError("runner.max_steps must be positive")
    if not config.data.required_modalities:
        raise ValueError("data.required_modalities must not be empty")
    modalities = cast(tuple[object, ...], config.data.required_modalities)
    for index, modality in enumerate(modalities):
        if not isinstance(modality, str):
            raise ValueError(f"data.required_modalities[{index}] must be a string")
        if not modality.strip():
            raise ValueError(f"data.required_modalities[{index}] must not be empty")
    return config
