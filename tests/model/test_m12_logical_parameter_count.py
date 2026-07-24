"""M12 family-neutral 逻辑参数计数的无 Torch 合同测试。"""

from pathlib import Path

import pytest

from autovla.models.assembly.contracts import (
    logical_parameter_element_count,
    logical_parameter_shape,
)


class _PlainParameter:
    """模拟普通未分区参数。"""

    shape = (2, 3)

    @staticmethod
    def numel() -> int:
        """返回普通本地元素数。"""

        return 6


class _PartitionedParameter:
    """模拟不同 rank 上本地分片大小不同的 ZeRO 参数。"""

    ds_id = 7

    def __init__(self, local_numel: int) -> None:
        """保存本地分片大小并声明完整逻辑 shape。"""

        self.ds_shape = (4, 8)
        self.shape = (local_numel,)
        self._local_numel = local_numel

    def numel(self) -> int:
        """返回 rank-local 分片大小。"""

        return self._local_numel


class _UnreliablePartitionedParameter:
    """模拟缺少完整逻辑 shape 的 ZeRO 参数。"""

    ds_status = "partitioned"
    shape = (4,)

    @staticmethod
    def numel() -> int:
        """返回不足以证明完整参数的本地大小。"""

        return 4


def test_logical_parameter_count_is_rank_invariant_for_partitioned_parameters() -> None:
    """完整 ds_shape 必须覆盖不同 rank 的本地 numel 差异。"""

    rank_zero = _PartitionedParameter(8)
    rank_one = _PartitionedParameter(3)

    assert logical_parameter_shape(rank_zero) == (4, 8)
    assert logical_parameter_element_count(rank_zero) == 32
    assert logical_parameter_element_count(rank_one) == 32
    assert logical_parameter_element_count(_PlainParameter()) == 6


def test_partition_marker_without_reliable_logical_shape_fails_closed() -> None:
    """发现 ZeRO 标记但缺少 ds_shape 时不得回退本地 numel。"""

    with pytest.raises(RuntimeError, match="lacks a reliable DeepSpeed ds_shape"):
        logical_parameter_element_count(_UnreliablePartitionedParameter())


@pytest.mark.parametrize("shape", ((2, True), (2, "3"), (2, -1)))
def test_partitioned_logical_shape_rejects_ambiguous_dimensions(
    shape: tuple[object, ...],
) -> None:
    """逻辑 shape 只接受非负内置整数。"""

    parameter = _PartitionedParameter(1)
    parameter.ds_shape = shape
    with pytest.raises(ValueError):
        logical_parameter_element_count(parameter)


def test_all_family_tuning_evidence_uses_shared_logical_count_helper() -> None:
    """三家族不得重新按 rank-local ``numel()`` 计算 tuning evidence。"""

    paths = (
        Path("autovla/models/families/gr00t_n1d6/factory.py"),
        Path("autovla/models/families/gr00t_n1d7/factory.py"),
        Path("autovla/models/families/pi0_5/factory.py"),
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "logical_parameter_element_count(parameter)" in source
        assert "parameter.numel() for parameter in model.parameters()" not in source
