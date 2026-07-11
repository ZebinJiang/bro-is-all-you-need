"""Checkpoint 状态、RNG 和摘要辅助函数。"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import numpy as np
import torch


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

    algorithm, keys, position, has_gauss, cached_gaussian = np.random.get_state()
    return {
        "python": random.getstate(),
        "numpy": {
            "algorithm": algorithm,
            "keys": torch.from_numpy(keys.copy()),
            "position": position,
            "has_gauss": has_gauss,
            "cached_gaussian": cached_gaussian,
        },
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": torch.cuda.get_rng_state() if torch.cuda.is_available() else None,
    }


def restore_rng_state(state: Mapping[str, object]) -> None:
    """严格恢复 checkpoint 中的全部 RNG 状态。"""

    validate_rng_state(state)

    python_state = _require_python_rng_state(state["python"])
    random.setstate(python_state)
    numpy_state = state["numpy"]
    if not isinstance(numpy_state, Mapping):
        raise TypeError("NumPy RNG state must be a mapping")
    algorithm = numpy_state.get("algorithm")
    keys = numpy_state.get("keys")
    position = numpy_state.get("position")
    has_gauss = numpy_state.get("has_gauss")
    cached_gaussian = numpy_state.get("cached_gaussian")
    if (
        not isinstance(algorithm, str)
        or not isinstance(keys, torch.Tensor)
        or type(position) is not int
        or type(has_gauss) is not int
        or not isinstance(cached_gaussian, float)
    ):
        raise TypeError("NumPy RNG checkpoint fields are invalid")
    np.random.set_state(
        (algorithm, keys.cpu().numpy().astype(np.uint32), position, has_gauss, cached_gaussian)
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
    numpy_state = state["numpy"]
    if not isinstance(numpy_state, Mapping):
        raise TypeError("NumPy RNG state must be a mapping")
    if set(numpy_state) != {
        "algorithm",
        "keys",
        "position",
        "has_gauss",
        "cached_gaussian",
    }:
        raise ValueError("NumPy RNG state fields are incomplete or unknown")
    if (
        not isinstance(numpy_state["algorithm"], str)
        or not isinstance(numpy_state["keys"], torch.Tensor)
        or type(numpy_state["position"]) is not int
        or type(numpy_state["has_gauss"]) is not int
        or not isinstance(numpy_state["cached_gaussian"], float)
    ):
        raise TypeError("NumPy RNG checkpoint fields are invalid")
    if not isinstance(state["torch_cpu"], torch.Tensor):
        raise TypeError("torch_cpu RNG state must be a tensor")
    cuda_state = state["torch_cuda"]
    if cuda_state is not None and not isinstance(cuda_state, torch.Tensor):
        raise TypeError("torch_cuda RNG state must be a tensor or None")


def sha256_file(path: Path) -> str:
    """流式计算 checkpoint 文件 SHA256。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["capture_rng_state", "restore_rng_state", "sha256_file", "validate_rng_state"]
