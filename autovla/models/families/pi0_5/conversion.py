"""Pi0.5 JAX/Flax/Orbax 到 safetensors 的离线确定性转换 schema。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
本模块仅接受已恢复的 NumPy 张量;生产运行时不导入 JAX、Flax 或 Orbax。
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TypedDict

import numpy as np

_RULE_FIELDS = {"destination_key", "permutation", "shape", "dtype"}
_DESTINATION_DTYPES = {"float32", "float16"}


class _ValidatedRule(TypedDict):
    """保存完成严格校验后的转换规则。"""

    destination_key: str
    permutation: tuple[int, ...]
    shape: tuple[int, ...]
    dtype: str


def _canonical_little_endian(value: np.ndarray) -> np.ndarray:
    """返回 C 连续的小端视图或副本,供跨主机稳定散列。"""

    byteorder = value.dtype.byteorder
    if byteorder == ">" or (byteorder == "=" and sys.byteorder == "big"):
        value = value.astype(value.dtype.newbyteorder("<"), copy=False)
    return np.ascontiguousarray(value)


def _tensor_hash(value: np.ndarray) -> str:
    """按连续小端张量字节生成稳定 SHA256。"""

    array = _canonical_little_endian(value)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


class Pi05CheckpointConverter:
    """执行显式 key/transpose/reshape/dtype 映射并产出全量审计清单。"""

    schema_version = "autovla.pi0_5.checkpoint_conversion.v1"

    def convert(
        self,
        source_tensors: Mapping[str, object],
        rules: Mapping[str, Mapping[str, object]],
        *,
        source_manifest_sha256: str,
    ) -> tuple[Mapping[str, np.ndarray], Mapping[str, object]]:
        """转换完整源集合;任何缺失、额外、碰撞、形状或 dtype 漂移均关闭。"""

        self._require_sha256(source_manifest_sha256)
        self._require_string_keys(source_tensors, "source tensor")
        self._require_string_keys(rules, "conversion rule")
        validated_rules = {
            source_key: self._validate_rule(source_key, rule) for source_key, rule in rules.items()
        }
        source_keys = set(source_tensors)
        rule_keys = set(validated_rules)
        missing = tuple(sorted(rule_keys - source_keys))
        unexpected = tuple(sorted(source_keys - rule_keys))
        destination_names = [rule["destination_key"] for rule in validated_rules.values()]
        collisions = tuple(
            sorted({name for name in destination_names if destination_names.count(name) > 1})
        )
        if missing or unexpected or collisions:
            raise ValueError(
                "conversion accounting failed: "
                f"missing={missing}, unexpected={unexpected}, collisions={collisions}"
            )
        converted: dict[str, np.ndarray] = {}
        records: list[dict[str, object]] = []
        for source_key in sorted(validated_rules):
            rule = validated_rules[source_key]
            source_value = source_tensors[source_key]
            if not isinstance(source_value, np.ndarray):
                raise TypeError(f"source tensor {source_key!r} must be a NumPy array")
            source = source_value
            if (
                not np.issubdtype(source.dtype, np.number)
                or np.issubdtype(source.dtype, np.complexfloating)
                or not np.isfinite(source).all()
            ):
                raise ValueError(f"source tensor {source_key!r} must be finite numeric data")
            permutation = rule["permutation"]
            if permutation and sorted(permutation) != list(range(source.ndim)):
                raise ValueError(f"invalid permutation for {source_key!r}")
            transformed = np.transpose(source, permutation) if permutation else source
            destination_shape = rule["shape"]
            if np.prod(transformed.shape, dtype=np.int64) != np.prod(
                destination_shape, dtype=np.int64
            ):
                raise ValueError(f"shape element count drift for {source_key!r}")
            dtype_name = rule["dtype"]
            dtype = np.dtype(dtype_name).newbyteorder("<")
            # 目标张量显式拥有 C 连续小端存储,不得与来源数组共享可变内存。
            destination = np.array(
                transformed.reshape(destination_shape), dtype=dtype, order="C", copy=True
            )
            if destination.shape != destination_shape or destination.dtype != dtype:
                raise ValueError(f"destination shape/dtype drift for {source_key!r}")
            destination_key = rule["destination_key"]
            converted[destination_key] = destination
            records.append(
                {
                    "source_key": source_key,
                    "destination_key": destination_key,
                    "source_shape": list(source.shape),
                    "destination_shape": list(destination.shape),
                    "source_dtype": source.dtype.name,
                    "destination_dtype": destination.dtype.name,
                    "source_sha256": _tensor_hash(source),
                    "destination_sha256": _tensor_hash(destination),
                }
            )
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "family_key": "pi0_5",
            "source_format": "jax_flax_orbax_restored_numpy_conversion_only",
            "destination_format": "safetensors",
            "source_manifest_sha256": source_manifest_sha256,
            "records": records,
            "accounting": {
                "source_count": len(source_tensors),
                "destination_count": len(converted),
                "missing_count": 0,
                "unexpected_count": 0,
                "collision_count": 0,
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
        return MappingProxyType(converted), MappingProxyType(payload)

    @staticmethod
    def _require_sha256(value: str) -> None:
        """要求来源清单身份为小写 SHA256。"""

        if (
            type(value) is not str
            or len(value) != 64
            or any(item not in "0123456789abcdef" for item in value)
        ):
            raise ValueError("source_manifest_sha256 must be a lowercase SHA256")

    @staticmethod
    def _require_string_keys(value: Mapping[object, object], label: str) -> None:
        """拒绝会在排序或清单中发生隐式字符串化的键。"""

        if not isinstance(value, Mapping):
            raise TypeError(f"{label} container must be a mapping")
        if any(type(key) is not str or not key for key in value):
            raise TypeError(f"{label} keys must be exact non-empty strings")

    @staticmethod
    def _validate_rule(source_key: str, rule: object) -> _ValidatedRule:
        """验证单条规则的精确字段、容器和标量类型。"""

        if not isinstance(rule, Mapping):
            raise TypeError(f"conversion rule for {source_key!r} must be a mapping")
        if set(rule) != _RULE_FIELDS or any(type(key) is not str for key in rule):
            raise ValueError("conversion rule fields must be exact")
        destination_key = rule["destination_key"]
        dtype_name = rule["dtype"]
        permutation = rule["permutation"]
        shape = rule["shape"]
        if type(destination_key) is not str or not destination_key:
            raise TypeError("destination_key must be an exact non-empty string")
        if type(dtype_name) is not str:
            raise TypeError("dtype must be an exact string")
        if dtype_name not in _DESTINATION_DTYPES:
            raise ValueError(
                "NumPy conversion emits float32/float16; bfloat16 requires a separately "
                "validated conversion backend"
            )
        if type(permutation) is not tuple or any(type(item) is not int for item in permutation):
            raise TypeError("permutation must be an exact tuple of built-in ints")
        if type(shape) is not tuple or not shape or any(type(item) is not int for item in shape):
            raise TypeError("shape must be a non-empty exact tuple of built-in ints")
        if any(item < 0 for item in permutation):
            raise ValueError("permutation axes must be non-negative")
        if any(item <= 0 for item in shape):
            raise ValueError("shape dimensions must be positive")
        return {
            "destination_key": destination_key,
            "permutation": permutation,
            "shape": shape,
            "dtype": dtype_name,
        }
