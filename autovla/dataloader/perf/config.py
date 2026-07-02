"""DataLoader 性能 Harness 配置契约。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

BuildScope = Literal["bounded", "budgeted_partial", "full", "full-or-budgeted"]

BenchmarkMode = Literal[
    "metadata-only",
    "bounded-decode",
    "training-view",
    "store-plan",
    "store-build-bounded",
    "store-read-benchmark",
    "pfs-training-store-build",
    "pfs-training-store-build-webdataset",
    "pfs-training-store-read",
    "pfs-training-store-read-webdataset",
]

_BENCHMARK_MODES: frozenset[str] = frozenset(
    {
        "bounded-decode",
        "metadata-only",
        "pfs-training-store-build",
        "pfs-training-store-build-webdataset",
        "pfs-training-store-read",
        "pfs-training-store-read-webdataset",
        "store-build-bounded",
        "store-plan",
        "store-read-benchmark",
        "training-view",
    }
)
_STORE_MODES: frozenset[str] = frozenset(
    {
        "pfs-training-store-build",
        "pfs-training-store-build-webdataset",
        "pfs-training-store-read",
        "pfs-training-store-read-webdataset",
        "store-build-bounded",
        "store-plan",
        "store-read-benchmark",
    }
)
_BUILD_SCOPES: frozenset[str] = frozenset(
    {
        "bounded",
        "budgeted_partial",
        "full",
        "full-or-budgeted",
    }
)


def _is_relative_to(path: Path, parent: Path) -> bool:
    """兼容 Python 3.10 的 relative_to 判断。"""
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _non_empty_text(value: object, *, field: str) -> str:
    """校验非空字符串字段。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_int(value: object, *, field: str) -> int:
    """校验正整数字段, bool 不视为 int。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a positive int")
    if value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


def _non_negative_int(value: object, *, field: str) -> int:
    """校验非负整数字段, bool 不视为 int。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a non-negative int")
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class PerfBenchmarkConfig:
    """描述一次 bounded DataLoader 性能 probe。

    配置只允许本地路径和显式 mode, 不包含模型、checkpoint、训练或外部服务字段。
    """

    adapter: str
    dataset: Path
    output_dir: Path
    max_episodes: int
    max_samples: int
    mode: BenchmarkMode
    max_decode_seconds: int = 300
    training_store_dir: Path | None = None
    build_scope: BuildScope = "bounded"

    def __post_init__(self) -> None:
        """校验字段并阻止输出写入 dataset root。"""
        adapter = _non_empty_text(self.adapter, field="adapter")
        mode_value = _non_empty_text(self.mode, field="mode")
        if mode_value not in _BENCHMARK_MODES:
            raise ValueError(f"mode must be one of {sorted(_BENCHMARK_MODES)}")
        build_scope_value = _non_empty_text(self.build_scope, field="build_scope")
        if build_scope_value not in _BUILD_SCOPES:
            raise ValueError(f"build_scope must be one of {sorted(_BUILD_SCOPES)}")
        dataset = Path(self.dataset)
        output_dir = Path(self.output_dir)
        max_episodes = _positive_int(self.max_episodes, field="max_episodes")
        max_samples = _positive_int(self.max_samples, field="max_samples")
        max_decode_seconds = _non_negative_int(
            self.max_decode_seconds,
            field="max_decode_seconds",
        )
        dataset_abs = dataset.absolute()
        output_abs = output_dir.absolute()
        if output_abs == dataset_abs or _is_relative_to(output_abs, dataset_abs):
            raise ValueError("output_dir must not be inside dataset root")
        training_store_dir = self.training_store_dir
        if mode_value in _STORE_MODES and training_store_dir is None:
            raise ValueError("training_store_dir is required for store modes")
        if training_store_dir is not None:
            store_path = Path(training_store_dir)
            store_abs = store_path.absolute()
            if store_abs == dataset_abs or _is_relative_to(store_abs, dataset_abs):
                raise ValueError("training_store_dir must not be inside dataset root")
            object.__setattr__(self, "training_store_dir", store_path)

        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "dataset", dataset)
        object.__setattr__(self, "output_dir", output_dir)
        object.__setattr__(self, "max_episodes", max_episodes)
        object.__setattr__(self, "max_samples", max_samples)
        object.__setattr__(self, "mode", cast(BenchmarkMode, mode_value))
        object.__setattr__(self, "max_decode_seconds", max_decode_seconds)
        object.__setattr__(self, "build_scope", cast(BuildScope, build_scope_value))

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 配置。"""
        payload: dict[str, object] = {
            "adapter": self.adapter,
            "build_scope": self.build_scope,
            "dataset": self.dataset.as_posix(),
            "max_decode_seconds": self.max_decode_seconds,
            "max_episodes": self.max_episodes,
            "max_samples": self.max_samples,
            "mode": self.mode,
            "output_dir": self.output_dir.as_posix(),
        }
        if self.training_store_dir is not None:
            payload["training_store_dir"] = self.training_store_dir.as_posix()
        return payload

    def write_json(self, path: str | Path) -> Path:
        """写出稳定配置 JSON。"""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_json_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def from_json_dict(cls, payload: object) -> "PerfBenchmarkConfig":
        """从 JSON object 构造配置。"""
        if not isinstance(payload, dict):
            raise ValueError("config must be a JSON object")
        typed_payload = cast(dict[str, object], payload)
        required = {
            "adapter",
            "dataset",
            "max_episodes",
            "max_samples",
            "mode",
            "output_dir",
        }
        extra = set(typed_payload) - (
            required | {"build_scope", "max_decode_seconds", "training_store_dir"}
        )
        missing = required - set(typed_payload)
        if extra:
            raise ValueError(f"config contains unknown fields: {sorted(extra)}")
        if missing:
            raise ValueError(f"config missing required fields: {sorted(missing)}")
        return cls(
            adapter=_non_empty_text(typed_payload["adapter"], field="adapter"),
            dataset=Path(_non_empty_text(typed_payload["dataset"], field="dataset")),
            output_dir=Path(_non_empty_text(typed_payload["output_dir"], field="output_dir")),
            max_episodes=_positive_int(typed_payload["max_episodes"], field="max_episodes"),
            max_samples=_positive_int(typed_payload["max_samples"], field="max_samples"),
            mode=cast(BenchmarkMode, _non_empty_text(typed_payload["mode"], field="mode")),
            max_decode_seconds=_non_negative_int(
                typed_payload.get("max_decode_seconds", 300),
                field="max_decode_seconds",
            ),
            training_store_dir=(
                Path(
                    _non_empty_text(
                        typed_payload["training_store_dir"],
                        field="training_store_dir",
                    )
                )
                if typed_payload.get("training_store_dir") is not None
                else None
            ),
            build_scope=cast(
                BuildScope,
                _non_empty_text(
                    typed_payload.get("build_scope", "bounded"),
                    field="build_scope",
                ),
            ),
        )


def load_perf_benchmark_config(path: str | Path) -> PerfBenchmarkConfig:
    """读取并校验 perf benchmark 配置。"""
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"config JSON is invalid: {exc.msg}") from exc
    return PerfBenchmarkConfig.from_json_dict(payload)
