"""分布式 loader 提交批次数证明契约测试。"""

from __future__ import annotations

import pytest

from autovla.data.contracts import DistributedBatchPlan, PartitionPlan


def _map_plan(*, sample_count: int, policy: str) -> PartitionPlan:
    """构造双 rank、每批两个样本的确定性 map 分区。"""

    return PartitionPlan.for_map(
        tuple((0, index) for index in range(sample_count)),
        global_rank=0,
        world_size=2,
        batch_size=2,
        seed=17,
        epoch=0,
        shuffle=False,
        policy=policy,
    )


def test_non_divisible_exact_map_tail_fails_closed() -> None:
    """不整除且不裁尾的 map 计划不得进入 collective 训练。"""

    plan = _map_plan(sample_count=9, policy="exact_no_pad")

    assert plan.committed_batch_counts(batch_size=2, drop_last=False) == (3, 2)
    with pytest.raises(ValueError, match="unequal committed batch counts"):
        DistributedBatchPlan.for_map(plan, batch_size=2, drop_last=False)


def test_drop_global_tail_proves_equal_batches_without_repetition() -> None:
    """全局裁尾对非整除输入产生相等批次且不复制样本。"""

    plan = _map_plan(sample_count=9, policy="drop_global_tail")
    proof = DistributedBatchPlan.for_map(plan, batch_size=2, drop_last=False)

    assert proof.rank_batch_counts == (2, 2)
    assert proof.committed_batches == 2
    assert plan.dropped_count == 1
    assert plan.repeated_count == 0
    assert len(set(plan.global_sequence)) == len(plan.global_sequence)


def test_divisible_exact_map_plan_is_accepted_without_forced_tail_drop() -> None:
    """本来已等批次的 exact map 计划不需要额外丢弃样本。"""

    proof = DistributedBatchPlan.for_map_sample_count(
        sample_count=8,
        world_size=2,
        batch_size=2,
        drop_last=False,
        policy="exact_no_pad",
    )

    assert proof.rank_batch_counts == (2, 2)


def test_resumed_map_plan_proves_equal_remaining_batches() -> None:
    """相同 committed cursor 在恢复后保持各 rank 剩余批次数一致。"""

    proof = DistributedBatchPlan.for_map_sample_count(
        sample_count=16,
        world_size=2,
        batch_size=2,
        drop_last=False,
        policy="exact_no_pad",
        committed_sample_cursor=4,
    )

    assert proof.rank_batch_counts == (2, 2)


def test_padding_policy_is_rejected_even_when_counts_match() -> None:
    """显式 padding 虽可配平批次, 也不能替代无重复提交证明。"""

    plan = _map_plan(sample_count=9, policy="pad_repeat")

    with pytest.raises(ValueError, match="must not repeat samples"):
        DistributedBatchPlan.for_map(plan, batch_size=2, drop_last=False)


@pytest.mark.parametrize(("drop_last", "expected"), ((False, 3), (True, 2)))
def test_streaming_nominal_plan_proves_rank_equivalence(
    drop_last: bool,
    expected: int,
) -> None:
    """每 rank 同一 nominal epoch 对整批和短尾都给出相同承诺。"""

    proof = DistributedBatchPlan.for_streaming(
        world_size=4,
        nominal_epoch_size=5,
        batch_size=2,
        drop_last=drop_last,
    )

    assert proof.rank_batch_counts == (expected,) * 4
