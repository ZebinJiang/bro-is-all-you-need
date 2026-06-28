"""M3 本地 runner dry-run JSON 配置。"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from autovla.training.local_runner import LocalRunnerConfig

DRY_RUN_MODE = "dry-run"

_REQUIRED_FIELDS = frozenset(
    {
        "run_id",
        "seed",
        "model_registry_key",
        "dataset_fingerprint",
        "transform_fingerprint",
        "statistics_fingerprint",
        "action_horizon",
        "action_dim",
        "max_steps",
        "output_dir",
        "mode",
    }
)


class LocalRunnerConfigError(ValueError):
    """表示 dry-run JSON 配置不满足严格字段契约。"""


@dataclass(frozen=True, slots=True)
class LocalRunnerDryRunConfig:
    """本地 runner dry-run 的严格 JSON 配置。"""

    run_id: str
    seed: int
    model_registry_key: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    action_horizon: int
    action_dim: int
    max_steps: int
    output_dir: Path
    mode: str

    def __post_init__(self) -> None:
        """校验构造器入口与 JSON 加载入口保持一致。"""
        _validate_run_id(self.run_id)
        _require_exact_int(self.seed, "seed", positive=False)
        if self.seed < 0:
            raise LocalRunnerConfigError("seed must be non-negative")
        _require_non_empty_str(self.model_registry_key, "model_registry_key")
        _require_non_empty_str(self.dataset_fingerprint, "dataset_fingerprint")
        _require_non_empty_str(self.transform_fingerprint, "transform_fingerprint")
        _require_non_empty_str(self.statistics_fingerprint, "statistics_fingerprint")
        _require_exact_int(self.action_horizon, "action_horizon")
        _require_exact_int(self.action_dim, "action_dim")
        _require_exact_int(self.max_steps, "max_steps")
        output_dir = cast(object, self.output_dir)
        if not isinstance(output_dir, Path):
            raise LocalRunnerConfigError("output_dir must be a path")
        if self.mode != DRY_RUN_MODE:
            raise LocalRunnerConfigError("mode must be dry-run")

    def with_output_dir(self, output_dir: str | Path) -> "LocalRunnerDryRunConfig":
        """返回带 CLI output_dir 覆盖的新配置。"""
        path = _path_from_value(str(output_dir), "output_dir")
        return replace(self, output_dir=path)

    def to_local_runner_config(self) -> LocalRunnerConfig:
        """转换为已合并的本地 runner runtime 配置。"""
        return LocalRunnerConfig(
            run_id=self.run_id,
            run_root=self.output_dir,
            max_steps=self.max_steps,
            seed=self.seed,
            model_registry_key=self.model_registry_key,
            dataset_fingerprint=self.dataset_fingerprint,
            transform_fingerprint=self.transform_fingerprint,
            statistics_fingerprint=self.statistics_fingerprint,
        )


def load_local_runner_dry_run_config(path: str | Path) -> LocalRunnerDryRunConfig:
    """从严格 JSON 文件加载本地 runner dry-run 配置。"""
    config_path = Path(path)
    try:
        raw: object = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalRunnerConfigError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise LocalRunnerConfigError("config must be a JSON object")
    data = cast(dict[str, object], raw)
    return build_local_runner_dry_run_config(data)


def build_local_runner_dry_run_config(
    data: dict[str, object],
) -> LocalRunnerDryRunConfig:
    """从已解析 JSON 字典构造 dry-run 配置。"""
    _reject_unknown_and_missing_fields(data)
    return LocalRunnerDryRunConfig(
        run_id=_required_string(data, "run_id", path_safe=True),
        seed=_required_exact_int(data, "seed", positive=False),
        model_registry_key=_required_string(data, "model_registry_key"),
        dataset_fingerprint=_required_string(data, "dataset_fingerprint"),
        transform_fingerprint=_required_string(data, "transform_fingerprint"),
        statistics_fingerprint=_required_string(data, "statistics_fingerprint"),
        action_horizon=_required_exact_int(data, "action_horizon"),
        action_dim=_required_exact_int(data, "action_dim"),
        max_steps=_required_exact_int(data, "max_steps"),
        output_dir=_path_from_value(_required_string(data, "output_dir"), "output_dir"),
        mode=_required_mode(data),
    )


def _reject_unknown_and_missing_fields(data: dict[str, object]) -> None:
    """拒绝未知字段并报告第一个缺失字段。"""
    for field in sorted(set(data) - _REQUIRED_FIELDS):
        raise LocalRunnerConfigError(f"unknown config field: {field}")
    for field in sorted(_REQUIRED_FIELDS - set(data)):
        raise LocalRunnerConfigError(f"missing required field: {field}")


def _required_string(
    data: dict[str, object],
    field: str,
    *,
    path_safe: bool = False,
) -> str:
    """读取必需非空字符串字段。"""
    value = data[field]
    _require_non_empty_str(value, field)
    text = cast(str, value)
    if path_safe:
        _validate_run_id(text)
    return text


def _required_mode(data: dict[str, object]) -> str:
    """读取并限制 dry-run mode。"""
    mode = _required_string(data, "mode")
    if mode != DRY_RUN_MODE:
        raise LocalRunnerConfigError("mode must be dry-run")
    return mode


def _required_exact_int(
    data: dict[str, object],
    field: str,
    *,
    positive: bool = True,
) -> int:
    """读取必需 exact int 字段。"""
    value = data[field]
    return _require_exact_int(value, field, positive=positive)


def _require_exact_int(value: object, field: str, *, positive: bool = True) -> int:
    """校验 JSON 整数不来自 bool、字符串或浮点。"""
    if type(value) is not int:
        raise LocalRunnerConfigError(f"{field} must be an int")
    number = value
    if positive and number <= 0:
        raise LocalRunnerConfigError(f"{field} must be positive")
    return number


def _require_non_empty_str(value: object, field: str) -> None:
    """校验非空字符串字段。"""
    if not isinstance(value, str):
        raise LocalRunnerConfigError(f"{field} must be a string")
    if not value.strip():
        raise LocalRunnerConfigError(f"{field} must not be empty")


def _validate_run_id(value: object) -> None:
    """限制 run_id 为单段路径名, 避免 dry-run 写出预期目录。"""
    _require_non_empty_str(value, "run_id")
    text = cast(str, value)
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise LocalRunnerConfigError("run_id must be a path-safe name")


def _path_from_value(value: str, field: str) -> Path:
    """从非空字符串构造 Path。"""
    _require_non_empty_str(value, field)
    return Path(value)
