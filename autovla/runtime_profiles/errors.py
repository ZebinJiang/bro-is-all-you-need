"""运行时环境画像的稳定错误类型。"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CUDA_DIAGNOSTIC_VALUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}")
_CUDA_DIAGNOSTIC_SECRET = re.compile(
    r"(?:api[_-]?key|auth|credential|password|secret|token)",
    re.IGNORECASE,
)
_MAX_COMPUTE_CAPABILITIES = 16


@dataclass(frozen=True, slots=True)
class CudaIntentMismatchDetails:
    """保存可安全落盘的 CUDA intent 期望值与观测值。"""

    expected_torch_compiled_cuda_version: str | None
    expected_cuda_runtime_version: str | None
    expected_cuda_driver_version: str | None
    expected_cudnn_version: str | None
    expected_nccl_version: str | None
    expected_compute_capabilities: tuple[str, ...]
    observed_torch_compiled_cuda_version: str | None
    observed_cuda_runtime_version: str | None
    observed_cuda_driver_version: str | None
    observed_cudnn_version: str | None
    observed_nccl_version: str | None
    observed_gpu_compute_capability: str | None

    def __post_init__(self) -> None:
        """拒绝可能携带路径、凭据或无界文本的诊断值。"""

        values = (
            self.expected_torch_compiled_cuda_version,
            self.expected_cuda_runtime_version,
            self.expected_cuda_driver_version,
            self.expected_cudnn_version,
            self.expected_nccl_version,
            *self.expected_compute_capabilities,
            self.observed_torch_compiled_cuda_version,
            self.observed_cuda_runtime_version,
            self.observed_cuda_driver_version,
            self.observed_cudnn_version,
            self.observed_nccl_version,
            self.observed_gpu_compute_capability,
        )
        if len(self.expected_compute_capabilities) > _MAX_COMPUTE_CAPABILITIES or any(
            value is not None
            and (
                not _CUDA_DIAGNOSTIC_VALUE.fullmatch(value) or _CUDA_DIAGNOSTIC_SECRET.search(value)
            )
            for value in values
        ):
            raise ValueError("CUDA diagnostic values must be bounded non-secret identifiers")

    def to_dict(self) -> dict[str, object]:
        """返回固定字段、稳定顺序的 JSON-safe 诊断。"""

        return {
            "expected": {
                "torch_compiled_cuda_version": self.expected_torch_compiled_cuda_version,
                "cuda_runtime_version": self.expected_cuda_runtime_version,
                "cuda_driver_version": self.expected_cuda_driver_version,
                "cudnn_version": self.expected_cudnn_version,
                "nccl_version": self.expected_nccl_version,
                "compute_capabilities": list(self.expected_compute_capabilities),
            },
            "observed": {
                "torch_compiled_cuda_version": self.observed_torch_compiled_cuda_version,
                "cuda_runtime_version": self.observed_cuda_runtime_version,
                "cuda_driver_version": self.observed_cuda_driver_version,
                "cudnn_version": self.observed_cudnn_version,
                "nccl_version": self.observed_nccl_version,
                "gpu_compute_capability": self.observed_gpu_compute_capability,
            },
        }


class RuntimeEnvironmentError(RuntimeError):
    """携带稳定错误码的运行时环境失败。"""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: CudaIntentMismatchDetails | None = None,
    ) -> None:
        """保存机器可判定错误码与面向人的简短说明。"""

        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, object]:
        """序列化稳定错误,仅在存在时附加类型化安全详情。"""

        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details.to_dict()
        return payload
