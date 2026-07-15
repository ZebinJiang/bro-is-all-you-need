"""R3 显式轴、布局、对齐和掩码语义测试。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from autovla.core.semantics import (
    AlignmentMode,
    AlignmentPolicy,
    AxisName,
    MaskKind,
    MaskSemantics,
    TensorLayout,
    resolve_alignment,
)


def test_should_construct_explicit_scalar_vector_time_and_time_feature_layouts() -> None:
    """验证公共布局不会用秩替代轴含义。"""
    assert TensorLayout.scalar().axes == ()
    assert TensorLayout.feature().axes == (AxisName.FEATURE,)
    assert TensorLayout.time().axes == (AxisName.TIME,)
    assert TensorLayout.time_feature().axes == (AxisName.TIME, AxisName.FEATURE)
    assert TensorLayout((AxisName.CAMERA, AxisName.FRAME)) != TensorLayout.time_feature()
    assert AxisName.TOKEN.value == "token"
    assert AxisName.EMBODIMENT.value == "embodiment"
    assert TensorLayout.time_feature(3, 7).sizes == (3, 7)


def test_should_reject_ambiguous_or_mismatched_alignment() -> None:
    """验证 exact/broadcast/time-index 之外的错配失败关闭。"""
    with pytest.raises(ValueError, match="exact"):
        resolve_alignment(
            source_layout=TensorLayout.feature(),
            source_shape=(2,),
            target_layout=TensorLayout.time_feature(),
            target_shape=(3, 2),
            policy=AlignmentPolicy(AlignmentMode.EXACT),
        )
    with pytest.raises(ValueError, match="broadcast"):
        resolve_alignment(
            source_layout=TensorLayout.feature(),
            source_shape=(3,),
            target_layout=TensorLayout.time_feature(),
            target_shape=(2, 2),
            policy=AlignmentPolicy(AlignmentMode.BROADCAST),
        )
    with pytest.raises(ValueError, match="time_indices"):
        AlignmentPolicy(AlignmentMode.TIME_INDEX)


def test_should_resolve_explicit_broadcast_and_time_index() -> None:
    """验证 ``[D]`` 广播和 ``[T,D]`` 时间映射都必须显式声明。"""
    broadcast = resolve_alignment(
        source_layout=TensorLayout.feature(),
        source_shape=(2,),
        target_layout=TensorLayout.time_feature(),
        target_shape=(3, 2),
        policy=AlignmentPolicy(AlignmentMode.BROADCAST),
    )
    assert broadcast.reshape == (1, 2)
    indexed = resolve_alignment(
        source_layout=TensorLayout.time_feature(),
        source_shape=(3, 2),
        target_layout=TensorLayout.time_feature(),
        target_shape=(2, 2),
        policy=AlignmentPolicy(AlignmentMode.TIME_INDEX, (2, 0)),
    )
    assert indexed.time_indices == (2, 0)


def test_should_resolve_all_explicit_time_policies_and_reject() -> None:
    """验证 truncate/pad/repeat/reject 都形成不同且确定的计划。"""
    source = TensorLayout.time_feature(3, 2)
    short = TensorLayout.time_feature(2, 2)
    long = TensorLayout.time_feature(5, 2)
    truncate = resolve_alignment(
        source_layout=source,
        source_shape=(3, 2),
        target_layout=short,
        target_shape=(2, 2),
        policy=AlignmentPolicy(AlignmentMode.TRUNCATE_TIME),
    )
    pad = resolve_alignment(
        source_layout=source,
        source_shape=(3, 2),
        target_layout=long,
        target_shape=(5, 2),
        policy=AlignmentPolicy(AlignmentMode.PAD_TIME),
    )
    repeat = resolve_alignment(
        source_layout=source,
        source_shape=(3, 2),
        target_layout=long,
        target_shape=(5, 2),
        policy=AlignmentPolicy(AlignmentMode.REPEAT_TIME),
    )
    assert truncate.time_indices == (0, 1)
    assert pad.time_indices == (0, 1, 2, -1, -1)
    assert repeat.time_indices == (0, 1, 2, 0, 1)
    fingerprints = {truncate.policy_fingerprint, pad.policy_fingerprint, repeat.policy_fingerprint}
    assert len(fingerprints) == 3
    with pytest.raises(ValueError, match="reject"):
        resolve_alignment(
            source_layout=source,
            source_shape=(3, 2),
            target_layout=source,
            target_shape=(3, 2),
            policy=AlignmentPolicy(AlignmentMode.REJECT),
        )


def test_should_keep_mask_kinds_distinct() -> None:
    """验证 temporal/action/statistics/padding/loss/camera/frame 不是别名。"""
    semantics = {
        kind: MaskSemantics(kind, TensorLayout.time())
        for kind in (
            MaskKind.TEMPORAL,
            MaskKind.ACTION_DIMENSION,
            MaskKind.STATISTICS,
            MaskKind.PADDING,
            MaskKind.LOSS,
            MaskKind.CAMERA,
            MaskKind.FRAME,
        )
    }
    assert len({item.kind for item in semantics.values()}) == 7


def test_core_import_should_not_eagerly_import_numpy_or_torch() -> None:
    """验证核心公共根保持后端无关和导入轻量。"""
    code = "import sys, autovla.core; print('numpy' in sys.modules, 'torch' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False False"
