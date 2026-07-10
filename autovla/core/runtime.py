"""AutoVLA 核心运行计划与环境门禁。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

RuntimeMode: TypeAlias = Literal["metadata_only", "local_cpu_smoke", "model_gr00t_n1d6_future"]
DevicePolicy: TypeAlias = Literal["cpu", "metadata_only", "cuda_future"]
PrecisionPolicy: TypeAlias = Literal["float32", "bfloat16_future", "float16_future"]


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    """描述运行能力,并对本地 dry-run 之外的能力 fail closed。"""

    mode: RuntimeMode
    device_policy: DevicePolicy = "cpu"
    precision_policy: PrecisionPolicy = "float32"
    compile_enabled: bool = False
    distributed_enabled: bool = False
    slurm_enabled: bool = False
    fsdp_enabled: bool = False
    deepspeed_enabled: bool = False

    def __post_init__(self) -> None:
        """校验本任务允许的运行计划。"""
        if self.mode in {"metadata_only", "local_cpu_smoke"} and self.device_policy not in {
            "cpu",
            "metadata_only",
        }:
            raise ValueError("metadata/local smoke modes cannot request CUDA")
        for name in (
            "compile_enabled",
            "distributed_enabled",
            "slurm_enabled",
            "fsdp_enabled",
            "deepspeed_enabled",
        ):
            if bool(getattr(self, name)):
                raise ValueError(f"{name} is disabled in this task")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "mode": self.mode,
            "device_policy": self.device_policy,
            "precision_policy": self.precision_policy,
            "compile_enabled": self.compile_enabled,
            "distributed_enabled": self.distributed_enabled,
            "slurm_enabled": self.slurm_enabled,
            "fsdp_enabled": self.fsdp_enabled,
            "deepspeed_enabled": self.deepspeed_enabled,
        }


@dataclass(frozen=True, slots=True)
class EnvProfile:
    """描述模型族运行前必须满足的环境变量门禁。"""

    profile_key: str
    mode: RuntimeMode
    required_env: tuple[str, ...] = ()
    forbidden_env: tuple[str, ...] = (
        "WANDB_API_KEY",
        "HF_TOKEN",
        "HUGGINGFACE_HUB_TOKEN",
    )

    def __post_init__(self) -> None:
        """校验 profile 字段非空且无重复。"""
        if not self.profile_key.strip():
            raise ValueError("profile_key must not be empty")
        if len(set(self.required_env)) != len(self.required_env):
            raise ValueError("required_env must not contain duplicates")
        if len(set(self.forbidden_env)) != len(self.forbidden_env):
            raise ValueError("forbidden_env must not contain duplicates")

    @classmethod
    def metadata_only(cls) -> "EnvProfile":
        """返回 metadata-only profile。"""
        return cls(profile_key="metadata_only", mode="metadata_only")

    @classmethod
    def local_cpu_smoke(cls) -> "EnvProfile":
        """返回本地 CPU smoke profile。"""
        return cls(profile_key="local_cpu_smoke", mode="local_cpu_smoke")

    @classmethod
    def model_gr00t_n1d6_future(cls) -> "EnvProfile":
        """返回未来 GR00T runtime profile,本任务不激活。"""
        return cls(
            profile_key="model-gr00t-n1d6",
            mode="model_gr00t_n1d6_future",
            required_env=("AUTOVLA_GR00T_SOURCE_ROOT", "AUTOVLA_GR00T_N1D6_CHECKPOINT"),
        )

    def validate(self, env: Mapping[str, str]) -> None:
        """校验 required/forbidden 环境变量。"""
        missing = [name for name in self.required_env if not env.get(name, "").strip()]
        if missing:
            raise RuntimeError(f"missing required env vars: {', '.join(missing)}")
        present_forbidden = [name for name in self.forbidden_env if env.get(name)]
        if present_forbidden:
            raise RuntimeError(f"forbidden env vars present: {', '.join(present_forbidden)}")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "profile_key": self.profile_key,
            "mode": self.mode,
            "required_env": list(self.required_env),
            "forbidden_env": list(self.forbidden_env),
        }


__all__ = ["EnvProfile", "RuntimePlan"]
