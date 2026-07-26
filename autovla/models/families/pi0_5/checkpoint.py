"""Pi0.5 生产运行时的本地 safetensors-only checkpoint 适配器。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import math
from collections.abc import Iterator, Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING, ContextManager, Protocol, TypeGuard, cast

if TYPE_CHECKING:
    import torch

from autovla.core.registry.errors import OptionalDependencyError

_MAX_TENSOR_SLICE_BYTES = 32 * 1024 * 1024
_SAFETENSORS_DTYPE_BYTES = {
    "BOOL": 1,
    "U8": 1,
    "I8": 1,
    "F8_E4M3": 1,
    "F8_E5M2": 1,
    "I16": 2,
    "U16": 2,
    "F16": 2,
    "BF16": 2,
    "I32": 4,
    "U32": 4,
    "F32": 4,
    "I64": 8,
    "U64": 8,
    "F64": 8,
    "C64": 8,
    "C128": 16,
}


class _SafeTensorSlice(Protocol):
    """描述 safetensors metadata 与有界切片表面。"""

    def get_shape(self) -> Sequence[int]:
        """返回 tensor shape。"""

        ...

    def get_dtype(self) -> str:
        """返回 safetensors dtype 名。"""

        ...

    def __getitem__(self, region: tuple[slice, ...]) -> torch.Tensor:
        """读取一个有界区域。"""

        ...


class _SafeTensorHandle(Protocol):
    """描述单个只读 safetensors 文件。"""

    def keys(self) -> Sequence[str]:
        """返回文件内键。"""

        ...

    def get_slice(self, key: str) -> _SafeTensorSlice:
        """返回不物化 tensor 的切片视图。"""

        ...

    def get_tensor(self, key: str) -> torch.Tensor:
        """读取标量或受上界约束的完整 tensor。"""

        ...


class _SafeOpen(Protocol):
    """描述 safetensors 公共只读打开函数。"""

    def __call__(
        self,
        filename: str,
        *,
        framework: str,
        device: str,
    ) -> ContextManager[_SafeTensorHandle]:
        """打开本地 safetensors 文件。"""

        ...


class _NoGradFactory(Protocol):
    """描述 Torch no_grad 上下文工厂。"""

    def __call__(self) -> ContextManager[None]:
        """返回禁用梯度的上下文。"""

        ...


def _is_no_grad_factory(value: object) -> TypeGuard[_NoGradFactory]:
    """把动态 Torch 属性收窄为上下文工厂。"""

    return callable(value)


class _Pi05PartitionedLoadSink:
    """用 safe_open metadata 与有界切片实现 Pi0.5 分区加载。"""

    def __init__(
        self,
        adapter: Pi05CheckpointAdapter,
        model: object,
        path: str | Path,
    ) -> None:
        """保存轻量输入,checkpoint 数据读取延迟到单张量 mutation。"""

        del model
        self._adapter = adapter
        self._path = path
        self._validated_path: Path | None = None
        self._shapes: dict[str, tuple[int, ...]] = {}
        self._audited: set[str] = set()
        self._loaded: set[str] = set()
        self._tensor_count = 0
        self._loaded_element_count = 0

    def prepare(self) -> None:
        """仅用 safe_open metadata 建立全局键和 shape 计划。"""

        value = self._adapter.validate_path(self._path)
        opener = _safe_open()
        shapes: dict[str, tuple[int, ...]] = {}
        with opener(str(value), framework="pt", device="cpu") as handle:
            for key in handle.keys():
                if not isinstance(key, str) or not key:
                    raise ValueError("Pi0.5 safetensors keys must be non-empty strings")
                if key in shapes:
                    raise ValueError(f"duplicate Pi0.5 safetensors key: {key}")
                shapes[key] = _logical_shape(tuple(handle.get_slice(key).get_shape()))
        if not shapes:
            raise ValueError("Pi0.5 checkpoint must contain at least one tensor")
        self._validated_path = value
        self._shapes = shapes
        self._tensor_count = len(shapes)
        self._loaded_element_count = sum(math.prod(shape) for shape in shapes.values())

    def audit_tensor(
        self,
        name: str,
        logical_shape: tuple[int, ...],
        /,
    ) -> None:
        """用 metadata 审计键和 ZeRO 逻辑 full-shape。"""

        logical_shape = _logical_shape(logical_shape)
        expected_shape = self._shapes.get(name)
        if expected_shape is None:
            raise ValueError(f"strict checkpoint mismatch: missing={(name,)}")
        if expected_shape != logical_shape:
            raise ValueError(f"strict checkpoint mismatch: shapes={(name,)}")
        self._audited.add(name)

    def complete_audit(
        self,
        *,
        parameter_names: tuple[str, ...],
        buffer_names: tuple[str, ...],
    ) -> None:
        """要求 checkpoint 对参数与复制 buffer 严格全覆盖。"""

        expected = set(parameter_names) | set(buffer_names)
        checkpoint_keys = set(self._shapes)
        missing = tuple(sorted(expected - checkpoint_keys))
        unexpected = tuple(sorted(checkpoint_keys - expected))
        if missing or unexpected or self._audited != expected:
            raise ValueError(
                f"strict checkpoint mismatch: missing={missing}, unexpected={unexpected}"
            )

    def load_tensor(self, name: str, tensor: object, /) -> None:
        """仅在 rank 0 以固定切片上限写入一个已聚合目标。"""

        torch = importlib.import_module("torch")
        if not isinstance(tensor, torch.Tensor):
            raise TypeError("partitioned checkpoint target must be a torch.Tensor")
        if name not in self._audited or name in self._loaded:
            raise RuntimeError(
                f"partitioned checkpoint tensor was not audited exactly once: {name}"
            )
        path = self._require_path()
        opener = _safe_open()
        no_grad = getattr(torch, "no_grad", None)
        if not _is_no_grad_factory(no_grad):
            raise TypeError("torch.no_grad must be callable")
        with no_grad(), opener(str(path), framework="pt", device="cpu") as handle:
            tensor_slice = handle.get_slice(name)
            item_bytes = _dtype_bytes(tensor_slice.get_dtype())
            max_slice_bytes = _file_slice_limit(path, item_bytes=item_bytes)
            for region in _iter_chunk_regions(
                self._shapes[name],
                item_bytes=item_bytes,
                max_slice_bytes=max_slice_bytes,
            ):
                payload = handle.get_tensor(name) if not region else tensor_slice[region]
                payload = payload.to(device=tensor.device, dtype=tensor.dtype)
                destination = tensor if not region else tensor[region]
                destination.copy_(payload)
                del destination, payload
        self._loaded.add(name)

    def finish(self) -> Mapping[str, object]:
        """确认严格消费并导出可传输的 fingerprint/count。"""

        if self._loaded != self._audited:
            raise RuntimeError("partitioned checkpoint load did not consume the audited tensor set")
        return {
            "fingerprint": self._adapter.fingerprint(self._path),
            "tensor_count": self._tensor_count,
            "loaded_element_count": self._loaded_element_count,
            "source_staging": "safe_open_bounded_slice",
            "max_source_slice_bytes": _MAX_TENSOR_SLICE_BYTES,
        }

    def restore_result(self, payload: Mapping[str, object], /) -> tuple[str, int]:
        """严格恢复 Pi0.5 原有加载返回值。"""

        if set(payload) != {
            "fingerprint",
            "tensor_count",
            "loaded_element_count",
            "source_staging",
            "max_source_slice_bytes",
        }:
            raise ValueError("partitioned Pi0.5 result payload fields are invalid")
        fingerprint = payload["fingerprint"]
        tensor_count = payload["tensor_count"]
        loaded_element_count = payload["loaded_element_count"]
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("partitioned Pi0.5 fingerprint is invalid")
        if type(tensor_count) is not int or tensor_count < 0:
            raise ValueError("partitioned Pi0.5 tensor count is invalid")
        if type(loaded_element_count) is not int or loaded_element_count < 0:
            raise ValueError("partitioned Pi0.5 loaded element count is invalid")
        if payload["source_staging"] != "safe_open_bounded_slice":
            raise ValueError("partitioned Pi0.5 source staging is invalid")
        if payload["max_source_slice_bytes"] != _MAX_TENSOR_SLICE_BYTES:
            raise ValueError("partitioned Pi0.5 source slice bound is invalid")
        return fingerprint, loaded_element_count

    def _require_path(self) -> Path:
        """返回仅 rank 0 验证的 checkpoint 路径。"""

        if self._validated_path is None:
            raise RuntimeError("partitioned checkpoint sink is not prepared on rank 0")
        return self._validated_path


def _safe_open() -> _SafeOpen:
    """返回 safetensors 公共 metadata/切片打开函数。"""

    if importlib.util.find_spec("safetensors") is None:
        raise OptionalDependencyError(
            "partitioned Pi0.5 loading requires the model-pi0-5 runtime profile"
        )
    module = importlib.import_module("safetensors")
    opener = getattr(module, "safe_open", None)
    if not callable(opener):
        raise TypeError("safetensors.safe_open must be callable")
    return cast(_SafeOpen, opener)


def _logical_shape(raw: object) -> tuple[int, ...]:
    """校验 metadata 或策略传入的逻辑 shape。"""

    if type(raw) is not tuple:
        raise TypeError("partitioned checkpoint logical shape must be a tuple")
    dimensions = cast(tuple[object, ...], raw)
    if any(type(value) is not int or value < 0 for value in dimensions):
        raise ValueError("partitioned checkpoint logical shape must contain non-negative integers")
    return cast(tuple[int, ...], raw)


def _dtype_bytes(dtype: str) -> int:
    """把 safetensors dtype 映射为单元素字节数。"""

    try:
        return _SAFETENSORS_DTYPE_BYTES[dtype]
    except KeyError as error:
        raise ValueError(f"unsupported safetensors dtype: {dtype}") from error


def _iter_chunk_regions(
    shape: tuple[int, ...],
    *,
    item_bytes: int,
    max_slice_bytes: int = _MAX_TENSOR_SLICE_BYTES,
) -> Iterator[tuple[slice, ...]]:
    """生成不超过固定字节上限的多维切片。"""

    if not shape:
        yield ()
        return
    if 0 in shape:
        return
    max_elements = max(1, max_slice_bytes // item_bytes)
    chunk_shape = [1] * len(shape)
    remaining = max_elements
    for index in range(len(shape) - 1, -1, -1):
        width = min(shape[index], remaining)
        chunk_shape[index] = max(1, width)
        remaining = max(1, remaining // chunk_shape[index])
    if math.prod(chunk_shape) > max_elements:
        raise AssertionError("checkpoint chunk planner exceeded its byte budget")
    starts = [
        range(0, dimension, chunk) for dimension, chunk in zip(shape, chunk_shape, strict=True)
    ]
    for offsets in product(*starts):
        yield tuple(
            slice(offset, min(offset + chunk, dimension))
            for offset, chunk, dimension in zip(offsets, chunk_shape, shape, strict=True)
        )


def _file_slice_limit(path: Path, *, item_bytes: int) -> int:
    """限制源切片小于 checkpoint 文件且不超过 32 MiB。"""

    file_bytes = path.stat().st_size
    if file_bytes <= 2 * item_bytes:
        raise ValueError("safetensors file is too small to contain a valid local payload")
    return min(_MAX_TENSOR_SLICE_BYTES, max(1, (file_bytes - 1) // 2))


class Pi05CheckpointAdapter:
    """严格加载单一 safetensors 文件,拒绝 pickle、远程路径与宽松键匹配。"""

    identity = "autovla.pi0_5.safetensors_strict.v1"

    def validate_path(self, path: str | Path) -> Path:
        """要求已存在的绝对本地普通 ``.safetensors`` 文件。"""

        value = Path(path)
        if not value.is_absolute() or value.suffix != ".safetensors":
            raise ValueError("Pi0.5 runtime checkpoint must be an absolute .safetensors path")
        if not value.is_file() or value.is_symlink():
            raise ValueError("Pi0.5 runtime checkpoint must be an existing non-symlink file")
        return value

    def fingerprint(self, path: str | Path) -> str:
        """流式计算 checkpoint SHA256,避免整文件驻留内存。"""

        value = self.validate_path(path)
        digest = hashlib.sha256()
        with value.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load_local(self, model: object, path: str | Path) -> tuple[str, int]:
        """严格加载 safetensors 并返回 fingerprint 与已加载元素数。"""

        value = self.validate_path(path)
        from safetensors.torch import load_file

        state = load_file(str(value), device="cpu")
        loader = getattr(model, "load_state_dict", None)
        if not callable(loader):
            raise TypeError("Pi0.5 model must expose load_state_dict")
        result = loader(state, strict=True)
        missing = tuple(getattr(result, "missing_keys", ()))
        unexpected = tuple(getattr(result, "unexpected_keys", ()))
        if missing or unexpected:
            raise ValueError(
                f"strict checkpoint mismatch: missing={missing}, unexpected={unexpected}"
            )
        loaded_element_count = sum(tensor.numel() for tensor in state.values())
        return self.fingerprint(value), loaded_element_count

    def partitioned_load(
        self,
        model: object,
        path: str | Path,
    ) -> _Pi05PartitionedLoadSink:
        """构造延迟 I/O 的 ZeRO-3 严格逐张量 sink。"""

        return _Pi05PartitionedLoadSink(self, model, path)
