"""M13 Pi0.5 转换形状、精度、目标元数据和授权失败关闭回归。"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from autovla.models.families.pi0_5 import conversion
from autovla.models.families.pi0_5.conversion import (
    Pi05CheckpointConverter,
    Pi05ConversionPlan,
    Pi05ConversionRuleReceipt,
    Pi05TargetTensorMetadata,
)


def _tiny_plan() -> Pi05ConversionPlan:
    """构造不读取资产且只展开两个小张量的固定测试计划。"""

    rule = Pi05ConversionRuleReceipt(
        source_key="tiny/layers",
        destination_key="layers.{layer}.weight",
        operation="slice_identity",
        repeat=2,
        source_selector="layer",
        expected_source_shape=(2, 2),
        expected_destination_shape=(2,),
    )
    return Pi05ConversionPlan((rule,))


def test_official_plan_binds_every_source_and_destination_shape() -> None:
    """811 个目标必须全部由带精确两侧形状的规则生成。"""

    plan = conversion.OFFICIAL_PI05_CONVERSION_PLAN
    assert plan.destination_precisions == ("float32", "float16")
    assert plan.destination_tensor_count == 811
    assert all(rule.expected_source_shape for rule in plan.rules)
    assert all(rule.expected_destination_shape for rule in plan.rules)
    assert len(plan.target_state_metadata("float32")) == 811
    with pytest.raises(ValueError, match="not implemented"):
        plan.target_state_metadata("bfloat16")


def test_official_conversion_rejects_malformed_source_shape_before_transform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """来源形状漂移必须在任何展开变换前失败。"""

    plan = _tiny_plan()
    monkeypatch.setattr(conversion, "OFFICIAL_PI05_CONVERSION_PLAN", plan)
    calls = 0

    def forbidden_transform(
        source: np.ndarray,
        receipt: Pi05ConversionRuleReceipt,
        *,
        layer: int,
    ) -> np.ndarray:
        """记录不应发生的张量变换。"""

        del source, receipt, layer
        nonlocal calls
        calls += 1
        raise AssertionError("shape drift reached transform")

    monkeypatch.setattr(conversion, "_official_transform", forbidden_transform)
    with pytest.raises(ValueError, match="source shape drift"):
        Pi05CheckpointConverter().convert_official(
            {"tiny/layers": np.zeros((2, 3), dtype=np.float32)},
            source_manifest_sha256="a" * 64,
            target_state_metadata=plan.target_state_metadata("float32"),
        )
    assert calls == 0


def test_official_conversion_requires_exact_canonical_target_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """目标键、形状和 dtype 任一漂移都不能生成成功清单。"""

    plan = _tiny_plan()
    monkeypatch.setattr(conversion, "OFFICIAL_PI05_CONVERSION_PLAN", plan)
    source = {"tiny/layers": np.zeros((2, 2), dtype=np.float32)}
    target = dict(plan.target_state_metadata("float32"))
    target.pop("layers.1.weight")
    with pytest.raises(ValueError, match="target state metadata accounting failed"):
        Pi05CheckpointConverter().convert_official(
            source,
            source_manifest_sha256="b" * 64,
            target_state_metadata=target,
        )
    target = dict(plan.target_state_metadata("float32"))
    target["layers.0.weight"] = Pi05TargetTensorMetadata((3,), "float32")
    with pytest.raises(ValueError, match="target state metadata contract drift"):
        Pi05CheckpointConverter().convert_official(
            source,
            source_manifest_sha256="b" * 64,
            target_state_metadata=target,
        )
    target = dict(plan.target_state_metadata("float32"))
    target["layers.0.weight"] = replace(target["layers.0.weight"], dtype="float16")
    with pytest.raises(ValueError, match="target state metadata contract drift"):
        Pi05CheckpointConverter().convert_official(
            source,
            source_manifest_sha256="b" * 64,
            target_state_metadata=target,
        )


@pytest.mark.parametrize("dtype", ["float32", "float16"])
def test_tiny_conversion_matches_precision_and_hashes_each_source_once(
    monkeypatch: pytest.MonkeyPatch,
    dtype: str,
) -> None:
    """小型成功路径必须严格匹配目标精度并只散列一次共享来源。"""

    plan = _tiny_plan()
    monkeypatch.setattr(conversion, "OFFICIAL_PI05_CONVERSION_PLAN", plan)
    source = np.arange(4, dtype=np.float32).reshape(2, 2)
    source_hash_calls = 0
    original_hash = conversion._tensor_hash

    def recording_hash(value: np.ndarray) -> str:
        """只统计共享来源对象的摘要次数。"""

        nonlocal source_hash_calls
        if value is source:
            source_hash_calls += 1
        return original_hash(value)

    monkeypatch.setattr(conversion, "_tensor_hash", recording_hash)
    tensors, manifest = Pi05CheckpointConverter().convert_official(
        {"tiny/layers": source},
        source_manifest_sha256="c" * 64,
        target_state_metadata=plan.target_state_metadata(dtype),
        destination_dtype=dtype,
    )
    assert tuple(tensors) == ("layers.0.weight", "layers.1.weight")
    assert all(value.dtype.name == dtype for value in tensors.values())
    assert manifest["destination_dtype"] == dtype
    assert source_hash_calls == 1
