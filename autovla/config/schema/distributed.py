"""AutoVLA GPU 分布式和精度配置。"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Literal

from autovla.config.schema.base import require_bool, require_choice

BucketSize = int
DeepSpeedVersion = Literal["0.17.6", "0.19.2"]

SUPPORTED_DEEPSPEED_VERSIONS: tuple[DeepSpeedVersion, ...] = ("0.17.6", "0.19.2")
_STAGE3_DEFAULTS = (
    50_000_000,
    100_000,
    1_000_000_000,
    1_000_000_000,
)
DEEPSPEED_MODULE_PUBLIC_API_SURFACE: tuple[str, ...] = (
    "deepspeed.initialize",
    "deepspeed.zero.Init",
    "deepspeed.zero.GatheredParameters",
)
DEEPSPEED_ENGINE_PUBLIC_API_SURFACE: tuple[str, ...] = (
    "DeepSpeedEngine.module",
    "DeepSpeedEngine.__call__",
    "DeepSpeedEngine.backward",
    "DeepSpeedEngine.is_gradient_accumulation_boundary",
    "DeepSpeedEngine.step",
    "DeepSpeedEngine.zero_grad",
    "DeepSpeedEngine.save_checkpoint",
    "DeepSpeedEngine.load_checkpoint",
    "DeepSpeedEngine.global_steps",
    "DeepSpeedEngine.micro_steps",
    "DeepSpeedEngine.skipped_steps",
)
DEEPSPEED_PUBLIC_API_SURFACE = (
    DEEPSPEED_MODULE_PUBLIC_API_SURFACE + DEEPSPEED_ENGINE_PUBLIC_API_SURFACE
)


def _require_exact_positive_int(value: object, name: str) -> int:
    """校验值为严格正的内置整数,拒绝 bool 和整数子类。"""

    if type(value) is not int:
        raise ValueError(f"{name} must be a built-in integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def validate_deepspeed_public_api(
    module: object,
    *,
    selected_version: DeepSpeedVersion,
) -> dict[str, object]:
    """校验 profile 选择版本和两版共享的模块级公共 API。"""

    if selected_version not in SUPPORTED_DEEPSPEED_VERSIONS:
        raise ValueError(f"unsupported profile-selected DeepSpeed version: {selected_version!r}")
    installed_version = getattr(module, "__version__", None)
    if type(installed_version) is not str or installed_version != selected_version:
        raise RuntimeError(
            "DeepSpeed exact version mismatch: "
            f"selected={selected_version!r}, installed={installed_version!r}"
        )
    initialize = getattr(module, "initialize", None)
    zero = getattr(module, "zero", None)
    zero_init = getattr(zero, "Init", None)
    gathered_parameters = getattr(zero, "GatheredParameters", None)
    missing = tuple(
        name
        for name, value in (
            ("deepspeed.initialize", initialize),
            ("deepspeed.zero.Init", zero_init),
            ("deepspeed.zero.GatheredParameters", gathered_parameters),
        )
        if not callable(value)
    )
    if missing:
        raise RuntimeError(
            "DeepSpeed public API surface is incomplete: "
            f"selected={selected_version!r}, installed={installed_version!r}, missing={missing!r}"
        )
    return {
        "selected_version": selected_version,
        "installed_version": installed_version,
        "validation_status": "exact_version_and_module_api_validated_engine_api_deferred",
        "validated_public_api_surface": DEEPSPEED_MODULE_PUBLIC_API_SURFACE,
        "deferred_public_api_surface": DEEPSPEED_ENGINE_PUBLIC_API_SURFACE,
    }


def validate_deepspeed_engine_public_api(
    engine: object,
    *,
    selected_version: DeepSpeedVersion,
    installed_version: str,
) -> dict[str, object]:
    """在 initialize 后验证两版共享的 engine 公共 API 表面。"""

    if (
        selected_version not in SUPPORTED_DEEPSPEED_VERSIONS
        or installed_version != selected_version
    ):
        raise RuntimeError(
            "DeepSpeed engine version identity mismatch: "
            f"selected={selected_version!r}, installed={installed_version!r}"
        )
    missing = tuple(
        name
        for name, value in (
            ("DeepSpeedEngine.__call__", engine),
            ("DeepSpeedEngine.backward", getattr(engine, "backward", None)),
            (
                "DeepSpeedEngine.is_gradient_accumulation_boundary",
                getattr(engine, "is_gradient_accumulation_boundary", None),
            ),
            ("DeepSpeedEngine.step", getattr(engine, "step", None)),
            ("DeepSpeedEngine.zero_grad", getattr(engine, "zero_grad", None)),
            ("DeepSpeedEngine.save_checkpoint", getattr(engine, "save_checkpoint", None)),
            ("DeepSpeedEngine.load_checkpoint", getattr(engine, "load_checkpoint", None)),
        )
        if not callable(value)
    )
    missing_attributes = tuple(
        name
        for name, value in (
            ("DeepSpeedEngine.module", getattr(engine, "module", None)),
            ("DeepSpeedEngine.global_steps", getattr(engine, "global_steps", None)),
            ("DeepSpeedEngine.micro_steps", getattr(engine, "micro_steps", None)),
            ("DeepSpeedEngine.skipped_steps", getattr(engine, "skipped_steps", None)),
        )
        if value is None
    )
    if missing or missing_attributes:
        raise RuntimeError(
            "DeepSpeed engine public API surface is incomplete: "
            f"selected={selected_version!r}, installed={installed_version!r}, "
            f"missing={missing + missing_attributes!r}"
        )
    return {
        "selected_version": selected_version,
        "installed_version": installed_version,
        "validation_status": "exact_version_and_full_public_api_validated",
        "validated_public_api_surface": DEEPSPEED_PUBLIC_API_SURFACE,
        "deferred_public_api_surface": (),
    }


@dataclass(frozen=True, slots=True)
class DeepSpeedConfig:
    """描述一个 DeepSpeed ZeRO 1/2/3 生产配置。

    AutoVLA 配置始终是事实来源。该对象只生成确定性、可序列化的官方
    DeepSpeed 配置字典,并明确拒绝 offload 与其他并行体系。
    """

    version: DeepSpeedVersion = "0.19.2"
    zero_stage: Literal[1, 2, 3] = 2
    bf16_enabled: bool = True
    fp16_enabled: bool = False
    overlap_communication: bool = True
    contiguous_gradients: bool = True
    reduce_scatter: bool = True
    allgather_partitions: bool = True
    reduce_bucket_size: BucketSize = 500_000_000
    allgather_bucket_size: BucketSize = 500_000_000
    stage3_prefetch_bucket_size: BucketSize = 50_000_000
    stage3_parameter_persistence_threshold: BucketSize = 100_000
    stage3_max_live_parameters: BucketSize = 1_000_000_000
    stage3_max_reuse_distance: BucketSize = 1_000_000_000
    gather_16bit_weights_on_model_save: bool = False
    wall_clock_breakdown: bool = False
    communication_data_type: Literal["bf16", "fp32"] = "bf16"
    optimizer_offload: Literal["none"] = "none"
    parameter_offload: Literal["none"] = "none"

    def __post_init__(self) -> None:
        """拒绝歧义精度、非法 stage、offload 和未使用的 stage-3 override。"""

        require_choice(
            self.version,
            "training.distributed.deepspeed.version",
            SUPPORTED_DEEPSPEED_VERSIONS,
        )
        if type(self.zero_stage) is not int or self.zero_stage not in (1, 2, 3):
            raise ValueError("training.distributed.deepspeed.zero_stage must be 1, 2, or 3")
        for name in (
            "bf16_enabled",
            "fp16_enabled",
            "overlap_communication",
            "contiguous_gradients",
            "reduce_scatter",
            "allgather_partitions",
            "gather_16bit_weights_on_model_save",
            "wall_clock_breakdown",
        ):
            require_bool(getattr(self, name), f"training.distributed.deepspeed.{name}")
        if not self.bf16_enabled or self.fp16_enabled:
            raise ValueError(
                "production DeepSpeed requires bf16_enabled=true and fp16_enabled=false"
            )
        if self.optimizer_offload != "none" or self.parameter_offload != "none":
            raise ValueError("DeepSpeed CPU/NVMe offload is unsupported")
        require_choice(
            self.communication_data_type,
            "training.distributed.deepspeed.communication_data_type",
            ("bf16", "fp32"),
        )
        for name in (
            "reduce_bucket_size",
            "allgather_bucket_size",
            "stage3_prefetch_bucket_size",
            "stage3_parameter_persistence_threshold",
            "stage3_max_live_parameters",
            "stage3_max_reuse_distance",
        ):
            _require_exact_positive_int(
                getattr(self, name),
                f"training.distributed.deepspeed.{name}",
            )
        stage3_fields = (
            self.stage3_prefetch_bucket_size,
            self.stage3_parameter_persistence_threshold,
            self.stage3_max_live_parameters,
            self.stage3_max_reuse_distance,
        )
        if self.zero_stage != 3 and stage3_fields != _STAGE3_DEFAULTS:
            raise ValueError("DeepSpeed stage-3-only overrides require zero_stage=3")

    def to_deepspeed_dict(
        self,
        *,
        micro_batch_size_per_gpu: int,
        gradient_accumulation_steps: int,
        data_parallel_world_size: int,
        gradient_clipping: float | None,
    ) -> dict[str, object]:
        """生成字段顺序稳定且不含隐式功能的 DeepSpeed 配置。"""

        _require_exact_positive_int(micro_batch_size_per_gpu, "micro_batch_size_per_gpu")
        _require_exact_positive_int(
            gradient_accumulation_steps,
            "gradient_accumulation_steps",
        )
        _require_exact_positive_int(data_parallel_world_size, "data_parallel_world_size")
        zero: dict[str, object] = {
            "stage": self.zero_stage,
            "overlap_comm": self.overlap_communication,
            "contiguous_gradients": self.contiguous_gradients,
            "reduce_scatter": self.reduce_scatter,
            "allgather_partitions": self.allgather_partitions,
            "reduce_bucket_size": self.reduce_bucket_size,
            "allgather_bucket_size": self.allgather_bucket_size,
        }
        if self.zero_stage == 3:
            zero.update(
                {
                    "stage3_prefetch_bucket_size": self.stage3_prefetch_bucket_size,
                    "stage3_param_persistence_threshold": (
                        self.stage3_parameter_persistence_threshold
                    ),
                    "stage3_max_live_parameters": self.stage3_max_live_parameters,
                    "stage3_max_reuse_distance": self.stage3_max_reuse_distance,
                    "stage3_gather_16bit_weights_on_model_save": (
                        self.gather_16bit_weights_on_model_save
                    ),
                }
            )
        payload: dict[str, object] = {
            "train_micro_batch_size_per_gpu": micro_batch_size_per_gpu,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "train_batch_size": (
                micro_batch_size_per_gpu * gradient_accumulation_steps * data_parallel_world_size
            ),
            "bf16": {"enabled": self.bf16_enabled},
            "fp16": {"enabled": self.fp16_enabled},
            "communication_data_type": self.communication_data_type,
            "zero_optimization": zero,
            "wall_clock_breakdown": self.wall_clock_breakdown,
            "steps_per_print": 1000,
        }
        if gradient_clipping is not None:
            payload["gradient_clipping"] = gradient_clipping
        return payload


@dataclass(frozen=True, slots=True)
class DistributedConfig:
    """描述 CUDA-only 训练策略和进程拓扑。"""

    strategy_key: str = "single_gpu"
    world_size: int = 1
    device: str = "cuda"
    gradient_as_bucket_view: bool = True
    find_unused_parameters: bool = False
    deepspeed: DeepSpeedConfig | None = None

    def __post_init__(self) -> None:
        """规范化窄别名并拒绝 CPU、FSDP 和错误拓扑。"""

        aliases = {
            "single_device": "single_gpu",
            "ddp": "distributed_data_parallel",
        }
        if self.strategy_key in {"fully_sharded_data_parallel", "fsdp", "fsdp2"}:
            raise ValueError("FSDP/FSDP2 is unsupported; migrate to deepspeed with zero_stage=3")
        canonical = aliases.get(self.strategy_key, self.strategy_key)
        if canonical == "deepspeed":
            if self.deepspeed is None:
                raise ValueError(
                    "legacy deepspeed strategy requires training.distributed.deepspeed config"
                )
            canonical = f"deepspeed_zero_{self.deepspeed.zero_stage}"
        if canonical != self.strategy_key:
            warnings.warn(
                f"training strategy {self.strategy_key!r} is deprecated; use {canonical!r}",
                DeprecationWarning,
                stacklevel=2,
            )
            object.__setattr__(self, "strategy_key", canonical)
        require_choice(
            canonical,
            "training.distributed.strategy_key",
            (
                "single_gpu",
                "distributed_data_parallel",
                "deepspeed_zero_1",
                "deepspeed_zero_2",
                "deepspeed_zero_3",
            ),
        )
        _require_exact_positive_int(self.world_size, "training.distributed.world_size")
        if self.device != "cuda":
            raise ValueError("AutoVLA production model training is CUDA-only")
        require_bool(self.gradient_as_bucket_view, "distributed.gradient_as_bucket_view")
        require_bool(self.find_unused_parameters, "distributed.find_unused_parameters")
        if canonical == "single_gpu" and self.world_size != 1:
            raise ValueError("single_gpu strategy requires world_size=1")
        deepspeed_keys = {"deepspeed_zero_1", "deepspeed_zero_2", "deepspeed_zero_3"}
        if canonical in {"distributed_data_parallel", *deepspeed_keys} and self.world_size < 2:
            raise ValueError(f"{canonical} strategy requires world_size>=2")
        if canonical in deepspeed_keys and self.deepspeed is None:
            raise ValueError("deepspeed strategy requires training.distributed.deepspeed")
        if canonical not in deepspeed_keys and self.deepspeed is not None:
            raise ValueError(
                "training.distributed.deepspeed is allowed only when strategy_key='deepspeed'"
            )
        if (
            self.deepspeed is not None
            and canonical != f"deepspeed_zero_{self.deepspeed.zero_stage}"
        ):
            raise ValueError("DeepSpeed strategy key and zero_stage must match")


@dataclass(frozen=True, slots=True)
class PrecisionConfig:
    """描述 GPU 训练精度,默认采用 A100 BF16。"""

    mode: str = "bfloat16"

    def __post_init__(self) -> None:
        """拒绝未知精度模式,保留显式 FP32 诊断模式。"""

        require_choice(self.mode, "training.precision.mode", ("float32", "bfloat16", "float16"))


__all__ = [
    "DEEPSPEED_ENGINE_PUBLIC_API_SURFACE",
    "DEEPSPEED_MODULE_PUBLIC_API_SURFACE",
    "DEEPSPEED_PUBLIC_API_SURFACE",
    "SUPPORTED_DEEPSPEED_VERSIONS",
    "BucketSize",
    "DeepSpeedConfig",
    "DeepSpeedVersion",
    "DistributedConfig",
    "PrecisionConfig",
    "validate_deepspeed_engine_public_api",
    "validate_deepspeed_public_api",
]
