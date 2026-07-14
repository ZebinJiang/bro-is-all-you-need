"""AutoVLA 生产硬件与离线执行环境配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import (
    require_bool,
    require_choice,
    require_non_empty_str,
    require_positive_int,
)


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    """声明 A100 GPU-only 训练环境,不执行设备探测或依赖安装。"""

    name: str = "a100"
    accelerator: str = "gpu"
    gpu_architecture: str = "a100"
    device: str = "cuda"
    precision: str = "bfloat16"
    distributed_backend: str = "nccl"
    slurm_partition: str = "a100"
    cpus_per_gpu: int = 8
    memory_request_convention: str = "per_node"
    memory_gib_per_gpu: int = 64
    deepspeed_profile: str = "training-deepspeed"
    environment_fingerprint_schema: str = "autovla.environment_fingerprint.v1"
    environment_fingerprint_inputs: tuple[str, ...] = (
        "source_sha",
        "selected_profile",
        "python_version",
        "cuda_runtime_version",
        "nccl_version",
        "torch_version",
        "transformers_version",
        "safetensors_version",
        "huggingface_hub_version",
        "webdataset_version",
        "deepspeed_version",
        "asset_manifest_identity",
    )
    runtime_fingerprint_status: str = "locks_and_fingerprints_collected_runtime_deferred"
    declared_environment_status: str = "locked_profiles_bounded_pre_cuda_validation_only"
    hf_hub_offline: bool = True
    transformers_offline: bool = True
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """拒绝 CPU、非 A100、联网和非 NCCL 生产姿态。"""

        require_non_empty_str(self.name, "environment.name")
        require_choice(self.accelerator, "environment.accelerator", ("gpu",))
        require_choice(self.gpu_architecture, "environment.gpu_architecture", ("a100",))
        require_choice(self.device, "environment.device", ("cuda",))
        require_choice(self.precision, "environment.precision", ("bfloat16",))
        require_choice(
            self.distributed_backend,
            "environment.distributed_backend",
            ("nccl",),
        )
        require_choice(self.slurm_partition, "environment.slurm_partition", ("a100",))
        require_positive_int(self.cpus_per_gpu, "environment.cpus_per_gpu")
        require_choice(
            self.memory_request_convention,
            "environment.memory_request_convention",
            ("per_node",),
        )
        require_positive_int(self.memory_gib_per_gpu, "environment.memory_gib_per_gpu")
        require_choice(
            self.deepspeed_profile,
            "environment.deepspeed_profile",
            ("training-deepspeed",),
        )
        require_choice(
            self.environment_fingerprint_schema,
            "environment.environment_fingerprint_schema",
            ("autovla.environment_fingerprint.v1",),
        )
        required_inputs = {
            "source_sha",
            "selected_profile",
            "python_version",
            "cuda_runtime_version",
            "nccl_version",
            "torch_version",
            "transformers_version",
            "safetensors_version",
            "huggingface_hub_version",
            "webdataset_version",
            "deepspeed_version",
            "asset_manifest_identity",
        }
        if type(self.environment_fingerprint_inputs) is not tuple or (
            any(type(item) is not str or not item for item in self.environment_fingerprint_inputs)
        ):
            raise ValueError("environment.environment_fingerprint_inputs must be a string tuple")
        if set(self.environment_fingerprint_inputs) != required_inputs or len(
            self.environment_fingerprint_inputs
        ) != len(required_inputs):
            raise ValueError("environment.environment_fingerprint_inputs are incomplete or unknown")
        require_choice(
            self.runtime_fingerprint_status,
            "environment.runtime_fingerprint_status",
            ("locks_and_fingerprints_collected_runtime_deferred",),
        )
        require_choice(
            self.declared_environment_status,
            "environment.declared_environment_status",
            ("locked_profiles_bounded_pre_cuda_validation_only",),
        )
        for name in ("hf_hub_offline", "transformers_offline", "local_files_only"):
            require_bool(getattr(self, name), f"environment.{name}")
            if not getattr(self, name):
                raise ValueError(f"environment.{name} must remain true")


__all__ = ["EnvironmentConfig"]
