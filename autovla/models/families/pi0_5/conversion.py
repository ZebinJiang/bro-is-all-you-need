# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/blob/15a9616a00943ada6c20a0f158e3adb39df2ccac/examples/convert_jax_model_to_pytorch.py
# License: Apache-2.0 source; model, tokenizer and checkpoint terms are separate.
# Reuse: Materially adapted official Orbax-to-PyTorch key and tensor transforms.
# AutoVLA changes: Authoritative local namespace, deterministic manifest and lazy boundary.
# ruff: noqa: RUF002
"""Pi0.5 JAX/Flax/Orbax 到 safetensors 的离线确定性转换 schema。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
本模块仅接受已恢复的 NumPy 张量;生产运行时不导入 JAX、Flax 或 Orbax。
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TypedDict, cast

import numpy as np
from numpy.typing import NDArray

from autovla.models.families.pi0_5.source_map import OPENPI_REVISION

GenericArray = NDArray[np.generic]
FloatingArray = NDArray[np.float16] | NDArray[np.float32]

_RULE_FIELDS = {"destination_key", "permutation", "shape", "dtype"}
_DESTINATION_DTYPES = {"float32", "float16"}
_CONVERSION_BLOB = "632c0b8782c1ecb5cb380130a30a3152b220eafd"


@dataclass(frozen=True, slots=True)
class Pi05ConversionRuleReceipt:
    """记录一个上游参数叶到本地 state-dict 键的不可变规则。"""

    source_key: str
    destination_key: str
    operation: str
    repeat: int = 1
    source_selector: str = "whole"

    def __post_init__(self) -> None:
        """拒绝空键、未知操作和不闭合层模板。"""

        if not self.source_key.strip() or not self.destination_key.strip():
            raise ValueError("conversion receipt keys must not be empty")
        if not self.source_selector.strip():
            raise ValueError("conversion source selector must not be empty")
        if self.operation not in {
            "identity",
            "transpose",
            "transpose_3_2_0_1",
            "reshape",
            "slice_identity",
            "slice_transpose",
            "slice_reshape",
            "slice_reshape_transpose",
            "slice_transpose_reshape",
            "slice_select_transpose",
            "slice_q_transpose_reshape",
            "slice_prefix_o_transpose_reshape",
            "slice_expert_o_reshape_transpose",
        }:
            raise ValueError("unsupported Pi0.5 conversion operation")
        if type(self.repeat) is not int or self.repeat <= 0:
            raise ValueError("conversion repeat must be a positive exact int")
        if (self.repeat > 1) != ("{layer}" in self.destination_key):
            raise ValueError("layered conversion rules must use a destination layer template")


@dataclass(frozen=True, slots=True)
class Pi05ConversionPlan:
    """绑定官方转换符号、全部静态规则和目标 manifest 身份。"""

    rules: tuple[Pi05ConversionRuleReceipt, ...]
    source_revision: str = OPENPI_REVISION
    source_path: str = "examples/convert_jax_model_to_pytorch.py"
    source_symbols: tuple[str, ...] = (
        "slice_paligemma_state_dict",
        "slice_gemma_state_dict",
        "convert_pi0_checkpoint",
    )
    source_blob: str = _CONVERSION_BLOB
    source_suffix_policy: str = "optional_/value_detected_from_restored_orbax_layout"
    destination_format: str = "safetensors"
    destination_precisions: tuple[str, ...] = ("float32", "bfloat16")
    strict_load_requirement: str = "all_destination_keys_consumed_with_strict_true"
    schema_version: str = "autovla.pi0_5.official_conversion_plan.v2"

    def __post_init__(self) -> None:
        """要求固定来源、唯一源键和完整规则集合。"""

        if self.source_revision != OPENPI_REVISION or self.source_blob != _CONVERSION_BLOB:
            raise ValueError("Pi0.5 conversion source identity drifted")
        if not self.rules or any(
            type(rule) is not Pi05ConversionRuleReceipt for rule in self.rules
        ):
            raise TypeError("Pi0.5 conversion plan requires immutable rule receipts")
        source_selectors = tuple((rule.source_key, rule.source_selector) for rule in self.rules)
        if len(set(source_selectors)) != len(source_selectors):
            raise ValueError("Pi0.5 conversion source selectors must be unique")
        if self.destination_format != "safetensors":
            raise ValueError("Pi0.5 conversion destination must remain safetensors")

    @property
    def source_leaf_count(self) -> int:
        """返回转换前必须完整消费的恢复后参数叶数量。"""

        return len({rule.source_key for rule in self.rules})

    @property
    def logical_rule_count(self) -> int:
        """返回包含共享源叶切片选择器的逻辑映射数量。"""

        return len(self.rules)

    @property
    def destination_tensor_count(self) -> int:
        """返回展开固定层数后的目标张量数量。"""

        return sum(rule.repeat for rule in self.rules)

    @property
    def manifest_identity(self) -> str:
        """返回无需读取任何参数载荷即可计算的转换计划身份。"""

        payload = {
            "destination_format": self.destination_format,
            "destination_precisions": self.destination_precisions,
            "rules": [asdict(rule) for rule in self.rules],
            "schema_version": self.schema_version,
            "source_blob": self.source_blob,
            "source_path": self.source_path,
            "source_revision": self.source_revision,
            "source_suffix_policy": self.source_suffix_policy,
            "source_symbols": self.source_symbols,
            "strict_load_requirement": self.strict_load_requirement,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def _receipt(
    source: str,
    destination: str,
    operation: str,
    repeat: int = 1,
    selector: str = "whole",
) -> Pi05ConversionRuleReceipt:
    """缩短固定规则表的声明，不执行动态规则推断。"""

    return Pi05ConversionRuleReceipt(source, destination, operation, repeat, selector)


_VISION_PREFIX = "backbone.vision_tower.vision_model"
_LANGUAGE_PREFIX = "backbone.language_model"
_EXPERT_PREFIX = "action_head.gemma_expert.model"

_OFFICIAL_CONVERSION_RULES = (
    _receipt(
        "img/embedding/kernel",
        f"{_VISION_PREFIX}.embeddings.patch_embedding.weight",
        "transpose_3_2_0_1",
    ),
    _receipt(
        "img/embedding/bias",
        f"{_VISION_PREFIX}.embeddings.patch_embedding.bias",
        "identity",
    ),
    _receipt(
        "img/pos_embedding",
        f"{_VISION_PREFIX}.embeddings.position_embedding.weight",
        "reshape",
    ),
    _receipt(
        "img/Transformer/encoderblock/LayerNorm_0/scale",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.layer_norm1.weight",
        "slice_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/LayerNorm_0/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.layer_norm1.bias",
        "slice_identity",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/LayerNorm_1/scale",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.layer_norm2.weight",
        "slice_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/LayerNorm_1/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.layer_norm2.bias",
        "slice_identity",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MlpBlock_0/Dense_0/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.mlp.fc1.weight",
        "slice_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MlpBlock_0/Dense_0/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.mlp.fc1.bias",
        "slice_identity",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MlpBlock_0/Dense_1/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.mlp.fc2.weight",
        "slice_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MlpBlock_0/Dense_1/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.mlp.fc2.bias",
        "slice_identity",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/key/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.k_proj.weight",
        "slice_reshape_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/key/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.k_proj.bias",
        "slice_reshape",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/value/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.v_proj.weight",
        "slice_reshape_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/value/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.v_proj.bias",
        "slice_reshape",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/query/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.q_proj.weight",
        "slice_reshape_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/query/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.q_proj.bias",
        "slice_reshape",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/out/kernel",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.out_proj.weight",
        "slice_reshape_transpose",
        27,
    ),
    _receipt(
        "img/Transformer/encoderblock/MultiHeadDotProductAttention_0/out/bias",
        f"{_VISION_PREFIX}.encoder.layers.{{layer}}.self_attn.out_proj.bias",
        "slice_reshape",
        27,
    ),
    _receipt(
        "img/Transformer/encoder_norm/scale",
        f"{_VISION_PREFIX}.post_layernorm.weight",
        "transpose",
    ),
    _receipt(
        "img/Transformer/encoder_norm/bias",
        f"{_VISION_PREFIX}.post_layernorm.bias",
        "identity",
    ),
    _receipt(
        "img/head/kernel",
        "backbone.multi_modal_projector.linear.weight",
        "transpose",
    ),
    _receipt(
        "img/head/bias",
        "backbone.multi_modal_projector.linear.bias",
        "identity",
    ),
    _receipt(
        "llm/embedder/input_embedding",
        f"{_LANGUAGE_PREFIX}.embed_tokens.weight",
        "identity",
    ),
    _receipt(
        "llm/layers/attn/q_einsum/w",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.self_attn.q_proj.weight",
        "slice_q_transpose_reshape",
        18,
    ),
    _receipt(
        "llm/layers/attn/kv_einsum/w",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.self_attn.k_proj.weight",
        "slice_select_transpose",
        18,
        "layer,0,0",
    ),
    _receipt(
        "llm/layers/attn/kv_einsum/w",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.self_attn.v_proj.weight",
        "slice_select_transpose",
        18,
        "layer,1,0",
    ),
    _receipt(
        "llm/layers/attn/attn_vec_einsum/w",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.self_attn.o_proj.weight",
        "slice_prefix_o_transpose_reshape",
        18,
    ),
    _receipt(
        "llm/layers/mlp/gating_einsum",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.mlp.gate_proj.weight",
        "slice_select_transpose",
        18,
        "layer,0",
    ),
    _receipt(
        "llm/layers/mlp/gating_einsum",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.mlp.up_proj.weight",
        "slice_select_transpose",
        18,
        "layer,1",
    ),
    _receipt(
        "llm/layers/mlp/linear",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.mlp.down_proj.weight",
        "slice_transpose",
        18,
    ),
    _receipt(
        "llm/layers/pre_attention_norm/scale",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.input_layernorm.weight",
        "slice_identity",
        18,
    ),
    _receipt(
        "llm/layers/pre_ffw_norm/scale",
        f"{_LANGUAGE_PREFIX}.layers.{{layer}}.post_attention_layernorm.weight",
        "slice_identity",
        18,
    ),
    _receipt("llm/final_norm/scale", f"{_LANGUAGE_PREFIX}.norm.weight", "identity"),
    _receipt(
        "llm/layers/attn/q_einsum_1/w",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.self_attn.q_proj.weight",
        "slice_q_transpose_reshape",
        18,
    ),
    _receipt(
        "llm/layers/attn/kv_einsum_1/w",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.self_attn.k_proj.weight",
        "slice_select_transpose",
        18,
        "layer,0,0",
    ),
    _receipt(
        "llm/layers/attn/kv_einsum_1/w",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.self_attn.v_proj.weight",
        "slice_select_transpose",
        18,
        "layer,1,0",
    ),
    _receipt(
        "llm/layers/attn/attn_vec_einsum_1/w",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.self_attn.o_proj.weight",
        "slice_expert_o_reshape_transpose",
        18,
    ),
    _receipt(
        "llm/layers/mlp_1/gating_einsum",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.mlp.gate_proj.weight",
        "slice_select_transpose",
        18,
        "layer,0",
    ),
    _receipt(
        "llm/layers/mlp_1/gating_einsum",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.mlp.up_proj.weight",
        "slice_select_transpose",
        18,
        "layer,1",
    ),
    _receipt(
        "llm/layers/mlp_1/linear",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.mlp.down_proj.weight",
        "slice_transpose",
        18,
    ),
    _receipt(
        "llm/layers/pre_attention_norm_1/Dense_0/bias",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.input_layernorm.dense.bias",
        "slice_identity",
        18,
    ),
    _receipt(
        "llm/layers/pre_attention_norm_1/Dense_0/kernel",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.input_layernorm.dense.weight",
        "slice_transpose",
        18,
    ),
    _receipt(
        "llm/layers/pre_ffw_norm_1/Dense_0/bias",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.post_attention_layernorm.dense.bias",
        "slice_identity",
        18,
    ),
    _receipt(
        "llm/layers/pre_ffw_norm_1/Dense_0/kernel",
        f"{_EXPERT_PREFIX}.layers.{{layer}}.post_attention_layernorm.dense.weight",
        "slice_transpose",
        18,
    ),
    _receipt(
        "llm/final_norm_1/Dense_0/bias",
        f"{_EXPERT_PREFIX}.norm.dense.bias",
        "identity",
    ),
    _receipt(
        "llm/final_norm_1/Dense_0/kernel",
        f"{_EXPERT_PREFIX}.norm.dense.weight",
        "transpose",
    ),
    *(
        _receipt(f"{name}/kernel", f"action_head.{name}.weight", "transpose")
        for name in ("action_in_proj", "action_out_proj", "time_mlp_in", "time_mlp_out")
    ),
    *(
        _receipt(f"{name}/bias", f"action_head.{name}.bias", "identity")
        for name in ("action_in_proj", "action_out_proj", "time_mlp_in", "time_mlp_out")
    ),
)

OFFICIAL_PI05_CONVERSION_PLAN = Pi05ConversionPlan(_OFFICIAL_CONVERSION_RULES)


class _ValidatedRule(TypedDict):
    """保存完成严格校验后的转换规则。"""

    destination_key: str
    permutation: tuple[int, ...]
    shape: tuple[int, ...]
    dtype: str


def _canonical_little_endian(value: GenericArray) -> GenericArray:
    """返回 C 连续的小端视图或副本,供跨主机稳定散列。"""

    byteorder = value.dtype.byteorder
    if byteorder == ">" or (byteorder == "=" and sys.byteorder == "big"):
        value = value.astype(value.dtype.newbyteorder("<"), copy=False)
    return np.ascontiguousarray(value)


def _tensor_hash(value: GenericArray) -> str:
    """按连续小端张量字节生成稳定 SHA256。"""

    array = _canonical_little_endian(value)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def restore_official_orbax_numpy(checkpoint_dir: Path) -> Mapping[str, GenericArray]:
    """在 conversion-only 环境中延迟恢复并压平官方 Orbax 参数树。

    此边界不导入 OpenPI trainer，也不会被生产 factory 或 family 根导入。
    """

    if not checkpoint_dir.is_absolute() or not checkpoint_dir.is_dir():
        raise ValueError("Orbax checkpoint_dir must be an existing absolute directory")
    params_dir = checkpoint_dir / "params"
    if not params_dir.is_dir():
        raise ValueError("official Pi0.5 Orbax payload must contain params/")
    import jax
    import orbax.checkpoint as ocp
    from flax.traverse_util import flatten_dict

    restored = ocp.PyTreeCheckpointer().restore(str(params_dir))
    if not isinstance(restored, Mapping):
        raise TypeError("restored Orbax payload must be a mapping")
    tree = cast(Mapping[str, object], restored)
    if "params" in tree and isinstance(tree["params"], Mapping):
        tree = cast(Mapping[str, object], tree["params"])
    paligemma = tree.get("PaliGemma")
    if not isinstance(paligemma, Mapping):
        raise ValueError("restored Orbax payload lacks PaliGemma parameters")
    flattened: dict[str, GenericArray] = {
        str(key): np.asarray(jax.device_get(value))
        for key, value in flatten_dict(paligemma, sep="/").items()
    }
    for name in ("action_in_proj", "action_out_proj", "time_mlp_in", "time_mlp_out"):
        value = tree.get(name)
        if not isinstance(value, Mapping):
            raise ValueError(f"restored Orbax payload lacks {name}")
        for key, leaf in flatten_dict(value, sep="/").items():
            flattened[f"{name}/{key}"] = np.asarray(jax.device_get(leaf))
    return MappingProxyType(flattened)


def _official_transform(
    source: GenericArray,
    receipt: Pi05ConversionRuleReceipt,
    *,
    layer: int,
) -> GenericArray:
    """按固定官方规则执行一个目标张量变换。"""

    operation = receipt.operation
    if operation == "identity":
        return source
    if operation == "transpose":
        return source.transpose()
    if operation == "transpose_3_2_0_1":
        return source.transpose(3, 2, 0, 1)
    if operation == "reshape":
        return source.reshape(-1, 1152)
    if operation == "slice_identity":
        return source[layer]
    if operation == "slice_transpose":
        return source[layer].transpose()
    if operation == "slice_reshape":
        return source[layer].reshape(-1)
    if operation == "slice_reshape_transpose":
        return source[layer].reshape(-1, 1152).transpose()
    if operation == "slice_q_transpose_reshape":
        width = 2048 if receipt.destination_key.startswith("backbone.") else 1024
        return source[layer].transpose(0, 2, 1).reshape(-1, width)
    if operation == "slice_prefix_o_transpose_reshape":
        return source[layer].transpose(2, 0, 1).reshape(-1, 2048)
    if operation == "slice_expert_o_reshape_transpose":
        return source[layer].reshape(-1, 1024).transpose()
    if operation == "slice_select_transpose":
        selectors = tuple(
            layer if value == "layer" else int(value)
            for value in receipt.source_selector.split(",")
        )
        return source[selectors].transpose()
    raise ValueError(f"unsupported official conversion operation: {operation}")


class Pi05CheckpointConverter:
    """执行显式 key/transpose/reshape/dtype 映射并产出全量审计清单。"""

    schema_version = "autovla.pi0_5.checkpoint_conversion.v1"

    def convert(
        self,
        source_tensors: Mapping[str, object],
        rules: Mapping[str, Mapping[str, object]],
        *,
        source_manifest_sha256: str,
    ) -> tuple[Mapping[str, FloatingArray], Mapping[str, object]]:
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
        converted: dict[str, FloatingArray] = {}
        records: list[dict[str, object]] = []
        for source_key in sorted(validated_rules):
            rule = validated_rules[source_key]
            source_value = source_tensors[source_key]
            if not isinstance(source_value, np.ndarray):
                raise TypeError(f"source tensor {source_key!r} must be a NumPy array")
            generic_source = cast(GenericArray, source_value)
            if not np.issubdtype(generic_source.dtype, np.number) or np.issubdtype(
                generic_source.dtype, np.complexfloating
            ):
                raise ValueError(f"source tensor {source_key!r} must be finite numeric data")
            source = generic_source
            if not np.isfinite(source).all():
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
            dtype: np.dtype[np.float32] | np.dtype[np.float16]
            if dtype_name == "float32":
                dtype = np.dtype(np.float32).newbyteorder("<")
            else:
                dtype = np.dtype(np.float16).newbyteorder("<")
            # 目标张量显式拥有 C 连续小端存储,不得与来源数组共享可变内存。
            destination = cast(
                FloatingArray,
                np.array(
                    transformed.reshape(destination_shape),
                    dtype=dtype,
                    order="C",
                    copy=True,
                ),
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

    def convert_official(
        self,
        source_tensors: Mapping[str, object],
        *,
        source_manifest_sha256: str,
        destination_dtype: str = "float32",
    ) -> tuple[Mapping[str, FloatingArray], Mapping[str, object]]:
        """执行固定 51 叶到 811 张量的官方 Pi0.5 转换。"""

        self._require_sha256(source_manifest_sha256)
        self._require_string_keys(source_tensors, "source tensor")
        if destination_dtype not in _DESTINATION_DTYPES:
            raise ValueError("official NumPy conversion dtype must be float32 or float16")
        expected = {rule.source_key for rule in OFFICIAL_PI05_CONVERSION_PLAN.rules}
        source_keys = set(source_tensors)
        if source_keys == expected:
            suffix = ""
        elif source_keys == {f"{key}/value" for key in expected}:
            suffix = "/value"
        else:
            raise ValueError("official conversion source keys do not match one complete layout")
        dtype = np.dtype(
            np.float32 if destination_dtype == "float32" else np.float16
        ).newbyteorder("<")
        converted: dict[str, FloatingArray] = {}
        records: list[dict[str, object]] = []
        for receipt in OFFICIAL_PI05_CONVERSION_PLAN.rules:
            source_key = f"{receipt.source_key}{suffix}"
            raw_source = source_tensors[source_key]
            if not isinstance(raw_source, np.ndarray):
                raise TypeError(f"source tensor {source_key!r} must be a NumPy array")
            source = cast(GenericArray, raw_source)
            if not np.issubdtype(source.dtype, np.number) or not np.isfinite(source).all():
                raise ValueError(f"source tensor {source_key!r} must be finite numeric data")
            for layer in range(receipt.repeat):
                transformed = _official_transform(source, receipt, layer=layer)
                destination = cast(
                    FloatingArray,
                    np.array(transformed, dtype=dtype, order="C", copy=True),
                )
                destination_key = receipt.destination_key.format(layer=layer)
                if destination_key in converted:
                    raise ValueError(
                        f"official conversion destination collision: {destination_key}"
                    )
                converted[destination_key] = destination
                records.append(
                    {
                        "source_key": source_key,
                        "source_selector": receipt.source_selector,
                        "destination_key": destination_key,
                        "operation": receipt.operation,
                        "source_shape": list(source.shape),
                        "destination_shape": list(destination.shape),
                        "source_dtype": source.dtype.name,
                        "destination_dtype": destination.dtype.name,
                        "source_sha256": _tensor_hash(source),
                        "destination_sha256": _tensor_hash(destination),
                    }
                )
        if len(converted) != OFFICIAL_PI05_CONVERSION_PLAN.destination_tensor_count:
            raise RuntimeError("official conversion destination accounting drifted")
        payload: dict[str, object] = {
            "schema_version": "autovla.pi0_5.official_checkpoint_conversion.v1",
            "family_key": "pi0_5",
            "plan_identity": OFFICIAL_PI05_CONVERSION_PLAN.manifest_identity,
            "source_revision": OFFICIAL_PI05_CONVERSION_PLAN.source_revision,
            "source_format": "jax_flax_orbax_restored_numpy_conversion_only",
            "source_manifest_sha256": source_manifest_sha256,
            "source_suffix": suffix,
            "destination_format": "safetensors",
            "destination_dtype": destination_dtype,
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
    def _require_string_keys(value: object, label: str) -> None:
        """拒绝会在排序或清单中发生隐式字符串化的键。"""

        if not isinstance(value, Mapping):
            raise TypeError(f"{label} container must be a mapping")
        mapping = cast(Mapping[object, object], value)
        if any(type(key) is not str or not key for key in mapping):
            raise TypeError(f"{label} keys must be exact non-empty strings")

    @staticmethod
    def _validate_rule(source_key: str, rule: object) -> _ValidatedRule:
        """验证单条规则的精确字段、容器和标量类型。"""

        if not isinstance(rule, Mapping):
            raise TypeError(f"conversion rule for {source_key!r} must be a mapping")
        raw_rule = cast(Mapping[object, object], rule)
        if set(raw_rule) != _RULE_FIELDS or any(type(key) is not str for key in raw_rule):
            raise ValueError("conversion rule fields must be exact")
        destination_key = raw_rule["destination_key"]
        dtype_name = raw_rule["dtype"]
        permutation = raw_rule["permutation"]
        shape = raw_rule["shape"]
        if type(destination_key) is not str or not destination_key:
            raise TypeError("destination_key must be an exact non-empty string")
        if type(dtype_name) is not str:
            raise TypeError("dtype must be an exact string")
        if dtype_name not in _DESTINATION_DTYPES:
            raise ValueError(
                "NumPy conversion emits float32/float16; bfloat16 requires a separately "
                "validated conversion backend"
            )
        if type(permutation) is not tuple:
            raise TypeError("permutation must be an exact tuple of built-in ints")
        raw_permutation = cast(tuple[object, ...], permutation)
        if any(type(item) is not int for item in raw_permutation):
            raise TypeError("permutation must be an exact tuple of built-in ints")
        typed_permutation = cast(tuple[int, ...], raw_permutation)
        if type(shape) is not tuple:
            raise TypeError("shape must be a non-empty exact tuple of built-in ints")
        raw_shape = cast(tuple[object, ...], shape)
        if not raw_shape or any(type(item) is not int for item in raw_shape):
            raise TypeError("shape must be a non-empty exact tuple of built-in ints")
        typed_shape = cast(tuple[int, ...], raw_shape)
        if any(item < 0 for item in typed_permutation):
            raise ValueError("permutation axes must be non-negative")
        if any(item <= 0 for item in typed_shape):
            raise ValueError("shape dimensions must be positive")
        return {
            "destination_key": destination_key,
            "permutation": typed_permutation,
            "shape": typed_shape,
            "dtype": dtype_name,
        }
