"""Pi0.5 JAX/Flax/Orbax 到 safetensors 的离线确定性转换 schema。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
本模块仅接受已恢复的 NumPy 张量;生产运行时不导入 JAX、Flax 或 Orbax。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import cast

import numpy as np


def _tensor_hash(value: np.ndarray) -> str:
    """按连续小端张量字节生成稳定 SHA256。"""

    array = np.ascontiguousarray(value)
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
        source_keys = set(source_tensors)
        rule_keys = set(rules)
        missing = tuple(sorted(rule_keys - source_keys))
        unexpected = tuple(sorted(source_keys - rule_keys))
        destination_names = [str(rule.get("destination_key", "")) for rule in rules.values()]
        collisions = tuple(
            sorted(
                {name for name in destination_names if name and destination_names.count(name) > 1}
            )
        )
        if missing or unexpected or collisions or any(not name for name in destination_names):
            raise ValueError(
                "conversion accounting failed: "
                f"missing={missing}, unexpected={unexpected}, collisions={collisions}"
            )
        converted: dict[str, np.ndarray] = {}
        records: list[dict[str, object]] = []
        for source_key in sorted(rules):
            rule = rules[source_key]
            if set(rule) != {"destination_key", "permutation", "shape", "dtype"}:
                raise ValueError("conversion rule fields must be exact")
            source = np.asarray(source_tensors[source_key])
            if not np.issubdtype(source.dtype, np.number) or not np.isfinite(source).all():
                raise ValueError(f"source tensor {source_key!r} must be finite numeric data")
            permutation = tuple(cast(Sequence[int], rule["permutation"]))
            if permutation and sorted(permutation) != list(range(source.ndim)):
                raise ValueError(f"invalid permutation for {source_key!r}")
            transformed = np.transpose(source, permutation) if permutation else source
            destination_shape = tuple(int(item) for item in cast(Sequence[int], rule["shape"]))
            if np.prod(transformed.shape, dtype=np.int64) != np.prod(
                destination_shape, dtype=np.int64
            ):
                raise ValueError(f"shape element count drift for {source_key!r}")
            dtype_name = str(rule["dtype"])
            if dtype_name not in {"float32", "float16"}:
                raise ValueError(
                    "NumPy conversion emits float32/float16; bfloat16 requires a separately "
                    "validated conversion backend"
                )
            dtype = np.dtype(dtype_name)
            destination = np.ascontiguousarray(transformed.reshape(destination_shape).astype(dtype))
            destination_key = str(rule["destination_key"])
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

        if len(value) != 64 or any(item not in "0123456789abcdef" for item in value):
            raise ValueError("source_manifest_sha256 must be a lowercase SHA256")
