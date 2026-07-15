"""AutoVLA 嵌套数据整理工具。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

import numpy as np


def collate_nested(values: Sequence[object]) -> object:
    """递归堆叠同构映射、元组和数组并保留不可堆叠标量。"""
    if not values:
        raise ValueError("values must not be empty")
    first = values[0]
    if isinstance(first, np.ndarray):
        arrays = [np.asarray(value) for value in values]
        if any(array.shape != arrays[0].shape for array in arrays):
            raise ValueError("nested arrays must have equal shapes")
        return np.stack(arrays, axis=0)
    if isinstance(first, Mapping):
        first_mapping = cast(Mapping[object, object], first)
        keys = tuple(first_mapping)
        mappings: list[Mapping[object, object]] = []
        for value in values:
            if not isinstance(value, Mapping):
                raise ValueError("nested mappings must have equal ordered keys")
            mapping = cast(Mapping[object, object], value)
            if tuple(mapping) != keys:
                raise ValueError("nested mappings must have equal ordered keys")
            mappings.append(mapping)
        return {key: collate_nested([value[key] for value in mappings]) for key in keys}
    if isinstance(first, tuple):
        first_tuple = cast(tuple[object, ...], first)
        tuples: list[tuple[object, ...]] = []
        for value in values:
            if not isinstance(value, tuple):
                raise ValueError("nested tuples must have equal lengths")
            tuple_value = cast(tuple[object, ...], value)
            if len(tuple_value) != len(first_tuple):
                raise ValueError("nested tuples must have equal lengths")
            tuples.append(tuple_value)
        return tuple(
            collate_nested([value[index] for value in tuples]) for index in range(len(first_tuple))
        )
    return tuple(values)


__all__ = ["collate_nested"]
