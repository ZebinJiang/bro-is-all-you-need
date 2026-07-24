"""Pi0.5 转换与归一化严格类型修复的无 Torch 回归测试。"""

from collections.abc import Mapping
from typing import cast

import numpy as np
import pytest

from autovla.models.families.pi0_5.conversion import Pi05CheckpointConverter
from autovla.models.families.pi0_5.normalization import (
    Pi05NormalizationReceipt,
    Pi05SemanticNormalizationPlan,
    Pi05SemanticTransform,
)
from autovla.models.families.pi0_5.source_map import OPENPI_REVISION


def _normalization_payload() -> dict[str, object]:
    """构造一个字段完整且不含模型载荷的归一化收据。"""

    feature = {
        "frame": "base",
        "name": "joint",
        "source": "robot",
        "unit": "rad",
    }
    return {
        "action_features": [feature],
        "embodiment": "test_arm",
        "schema_version": "autovla.pi0_5.normalization_receipt.v1",
        "semantic_transform_id": "autovla.pi0_5.semantic.identity.v1",
        "source_revision": OPENPI_REVISION,
        "state_features": [feature],
        "statistics_fingerprint": "a" * 64,
        "statistics_source": "verified-local-norm-stats.json",
    }


def test_conversion_preserves_precise_destination_dtypes_without_torch() -> None:
    """转换器必须继续生成拥有内存的 float16/float32 NumPy 张量。"""

    converter = Pi05CheckpointConverter()
    source = {
        "half": np.arange(4, dtype=np.int16).reshape(2, 2),
        "single": np.arange(4, dtype=np.float64).reshape(2, 2),
    }
    rules: dict[str, Mapping[str, object]] = {
        "half": {
            "destination_key": "half.weight",
            "dtype": "float16",
            "permutation": (),
            "shape": (2, 2),
        },
        "single": {
            "destination_key": "single.weight",
            "dtype": "float32",
            "permutation": (),
            "shape": (2, 2),
        },
    }

    converted, _ = converter.convert(
        source,
        rules,
        source_manifest_sha256="b" * 64,
    )

    assert converted["half.weight"].dtype == np.dtype("<f2")
    assert converted["single.weight"].dtype == np.dtype("<f4")
    assert converted["half.weight"].flags.owndata
    assert converted["single.weight"].flags.owndata


def test_conversion_dynamic_mapping_guards_remain_fail_closed() -> None:
    """静态类型收窄不得放过动态传入的非映射容器。"""

    converter = Pi05CheckpointConverter()
    invalid_sources = cast(Mapping[str, object], object())
    with pytest.raises(TypeError, match="container must be a mapping"):
        converter.convert(invalid_sources, {}, source_manifest_sha256="c" * 64)

    invalid_rule = cast(Mapping[str, object], [])
    with pytest.raises(TypeError, match="must be a mapping"):
        converter.convert(
            {"kernel": np.ones((1,), dtype=np.float32)},
            {"kernel": invalid_rule},
            source_manifest_sha256="d" * 64,
        )


def test_normalization_dynamic_semantic_transform_remains_fail_closed() -> None:
    """收据映射可解析,但动态伪造的语义变换仍必须在构造时拒绝。"""

    receipt = Pi05NormalizationReceipt.from_mapping(_normalization_payload())
    invalid_transform = cast(Pi05SemanticTransform, object())

    with pytest.raises(TypeError, match="must implement Pi05SemanticTransform"):
        Pi05SemanticNormalizationPlan(
            receipt=receipt,
            state_q01=np.zeros(1, dtype=np.float32),
            state_q99=np.ones(1, dtype=np.float32),
            action_q01=np.zeros(1, dtype=np.float32),
            action_q99=np.ones(1, dtype=np.float32),
            semantic_transform=invalid_transform,
        )
