"""Checkpoint 状态、RNG 和摘要辅助函数。"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard, cast

import numpy as np
import torch
from numpy.typing import NDArray


def _is_three_item_tuple(value: object) -> TypeGuard[tuple[object, object, object]]:
    """判断对象是否为恰含三项的元组。"""

    if not _is_object_tuple(value):
        return False
    if type(value) is not tuple:
        return False
    return len(value) == 3


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """判断对象是否为元组并保留元素的对象边界。"""

    return isinstance(value, tuple)


def _require_python_rng_state(value: object) -> tuple[int, tuple[int, ...], float | None]:
    """校验并收窄 Python random 的完整状态结构。"""

    if not _is_three_item_tuple(value):
        raise TypeError("Python RNG state must be a three-item tuple")
    version, internal, gaussian = value
    if type(version) is not int or not _is_object_tuple(internal):
        raise TypeError("Python RNG state version and internal state are invalid")
    if not internal:
        raise TypeError("Python RNG internal state must contain integers")
    narrowed_internal: list[int] = []
    for item in internal:
        if type(item) is not int:
            raise TypeError("Python RNG internal state must contain integers")
        narrowed_internal.append(item)
    if gaussian is not None and not isinstance(gaussian, float):
        raise TypeError("Python RNG gaussian cache must be float or None")
    return version, tuple(narrowed_internal), gaussian


def capture_rng_state() -> dict[str, object]:
    """捕获 Python、NumPy、CPU 与可选 CUDA RNG 状态。"""

    algorithm, keys, position, has_gauss, cached_gaussian = cast(
        tuple[str, NDArray[np.uint32], int, int, float],
        np.random.get_state(),
    )
    return {
        "python": random.getstate(),
        "numpy": {
            "algorithm": algorithm,
            "keys": tuple(int(value) for value in keys),
            "position": position,
            "has_gauss": has_gauss,
            "cached_gaussian": cached_gaussian,
        },
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": torch.cuda.get_rng_state() if torch.cuda.is_available() else None,
    }


def _require_numpy_rng_state(
    value: object,
) -> tuple[str, tuple[int, ...], int, int, float]:
    """校验并收窄 primitive-only NumPy MT19937 状态。"""
    if not isinstance(value, Mapping):
        raise TypeError("NumPy RNG state must be a mapping")
    mapping = cast(Mapping[object, object], value)
    expected = {"algorithm", "keys", "position", "has_gauss", "cached_gaussian"}
    if set(mapping) != expected:
        raise ValueError("NumPy RNG state fields are incomplete or unknown")
    algorithm = mapping["algorithm"]
    raw_keys = mapping["keys"]
    position = mapping["position"]
    has_gauss = mapping["has_gauss"]
    cached_gaussian = mapping["cached_gaussian"]
    if not isinstance(algorithm, str) or algorithm != "MT19937":
        raise ValueError("NumPy RNG algorithm is incompatible")
    if not isinstance(raw_keys, (list, tuple)):
        raise TypeError("NumPy RNG keys must be a primitive sequence")
    values = cast(list[object] | tuple[object, ...], raw_keys)
    if len(values) != 624:
        raise ValueError("NumPy RNG checkpoint key length is incompatible")
    keys: list[int] = []
    for item in values:
        if type(item) is not int:
            raise TypeError("NumPy RNG keys must contain exact integers")
        if not 0 <= item <= 0xFFFFFFFF:
            raise ValueError("NumPy RNG keys must remain in the uint32 range")
        keys.append(item)
    if type(position) is not int or not 0 <= position <= 624:
        raise ValueError("NumPy RNG position is incompatible")
    if type(has_gauss) is not int or has_gauss not in {0, 1}:
        raise ValueError("NumPy RNG gaussian flag is incompatible")
    if not isinstance(cached_gaussian, float):
        raise TypeError("NumPy RNG gaussian cache must be a float")
    return algorithm, tuple(keys), position, has_gauss, cached_gaussian


def restore_rng_state(state: Mapping[str, object]) -> None:
    """严格恢复 checkpoint 中的全部 RNG 状态。"""

    validate_rng_state(state)

    python_state = _require_python_rng_state(state["python"])
    random.setstate(python_state)
    algorithm, keys, position, has_gauss, cached_gaussian = _require_numpy_rng_state(state["numpy"])
    np.random.set_state(
        (algorithm, np.asarray(keys, dtype=np.uint32), position, has_gauss, cached_gaussian)
    )
    cpu_state = state["torch_cpu"]
    if not isinstance(cpu_state, torch.Tensor):
        raise TypeError("torch_cpu RNG state must be a tensor")
    torch.set_rng_state(cpu_state)
    cuda_state = state.get("torch_cuda")
    if cuda_state is not None:
        if not torch.cuda.is_available() or not isinstance(cuda_state, torch.Tensor):
            raise RuntimeError("CUDA RNG checkpoint is incompatible with current runtime")
        torch.cuda.set_rng_state(cuda_state)


def validate_rng_state(state: Mapping[str, object]) -> None:
    """在不修改进程 RNG 的前提下校验完整状态结构。"""

    if set(state) != {"python", "numpy", "torch_cpu", "torch_cuda"}:
        raise ValueError("RNG state fields are incomplete or unknown")
    _require_python_rng_state(state["python"])
    _require_numpy_rng_state(state["numpy"])
    cpu_state = state["torch_cpu"]
    if not isinstance(cpu_state, torch.Tensor):
        raise TypeError("torch_cpu RNG state must be a tensor")
    current_cpu = torch.get_rng_state()
    if (
        cpu_state.dtype != torch.uint8
        or cpu_state.ndim != 1
        or cpu_state.shape != current_cpu.shape
    ):
        raise ValueError("torch_cpu RNG state shape or dtype is incompatible")
    cuda_state = state["torch_cuda"]
    if cuda_state is not None and not isinstance(cuda_state, torch.Tensor):
        raise TypeError("torch_cuda RNG state must be a tensor or None")
    if cuda_state is not None:
        if not torch.cuda.is_available():
            raise RuntimeError("torch_cuda RNG state requires CUDA")
        current_cuda = torch.cuda.get_rng_state()
        if (
            cuda_state.dtype != torch.uint8
            or cuda_state.ndim != 1
            or cuda_state.shape != current_cuda.shape
        ):
            raise ValueError("torch_cuda RNG state shape or dtype is incompatible")


def sha256_file(path: Path) -> str:
    """流式计算 checkpoint 文件 SHA256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory(path: Path) -> str:
    """按相对路径和文件内容稳定计算完整目录 SHA256。"""

    if not path.is_dir():
        raise ValueError(f"checkpoint directory does not exist: {path}")
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ValueError("checkpoint directory must contain files")
    for file_path in files:
        relative = file_path.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "capture_rng_state",
    "restore_rng_state",
    "sha256_directory",
    "sha256_file",
    "validate_rng_state",
]
