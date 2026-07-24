"""M12 分布式计划与提交样本收据的纯 CPU 合同测试。"""

from collections.abc import Mapping, Sequence

import pytest

from autovla.training.distributed_receipts import (
    DECLARED_PAYLOAD_SCOPE,
    DistributedRunReceiptIdentity,
    RankCommittedSampleReceipt,
    RankTrainingPlanReceipt,
    aggregate_committed_sample_payloads,
    aggregate_rank_plan_payloads,
    collect_rank_plan_receipt,
)


def _identity() -> DistributedRunReceiptIdentity:
    """返回两 rank 共享的固定测试身份。"""

    return DistributedRunReceiptIdentity(
        run_id="m12-static-contract",
        source_sha="a" * 40,
        family_key="gr00t_n1d6",
        strategy="deepspeed_zero_3",
        world_size=2,
        topology_fingerprint="b" * 64,
        training_plan_fingerprint="c" * 64,
    )


def _plan(rank: int) -> RankTrainingPlanReceipt:
    """构造给定 rank 的一致计划声明。"""

    return RankTrainingPlanReceipt(
        identity=_identity(),
        rank=rank,
        access_mode="map",
        partition_policy="drop_global_tail",
        committed_batches=8,
        micro_batch_size=2,
        gradient_accumulation_steps=4,
    )


class _StaticTransport:
    """模拟严格按 rank 返回载荷的 collective 边界。"""

    rank = 0
    world_size = 2

    def __init__(self, payloads: Sequence[Mapping[str, object]]) -> None:
        """保存固定测试载荷。"""

        self._payloads = tuple(payloads)

    def gather_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """校验本地载荷后返回固定集合。"""

        assert payload == self._payloads[0]
        return self._payloads


def test_all_rank_plan_receipt_is_versioned_deterministic_and_static_only() -> None:
    """聚合计划固定排序和指纹,且不得宣称 GPU 运行已验证。"""

    payloads = (_plan(0).to_payload(), _plan(1).to_payload())
    direct = aggregate_rank_plan_payloads(payloads)
    collected = collect_rank_plan_receipt(_plan(0), _StaticTransport(payloads))

    assert direct.fingerprint == collected.fingerprint
    assert direct.evidence_scope == DECLARED_PAYLOAD_SCOPE
    assert tuple(receipt.rank for receipt in direct.ranks) == (0, 1)
    assert "runtime_verified" not in vars(type(direct))


def test_all_rank_plan_receipt_rejects_rank_or_plan_drift() -> None:
    """聚合边界拒绝 rank 顺序和任一计划字段漂移。"""

    with pytest.raises(ValueError, match="ordered by complete rank coverage"):
        aggregate_rank_plan_payloads((_plan(1).to_payload(), _plan(0).to_payload()))
    drifted = RankTrainingPlanReceipt(
        identity=_identity(),
        rank=1,
        access_mode="map",
        partition_policy="drop_global_tail",
        committed_batches=9,
        micro_batch_size=2,
        gradient_accumulation_steps=4,
    )
    with pytest.raises(ValueError, match="not identical"):
        aggregate_rank_plan_payloads((_plan(0).to_payload(), drifted.to_payload()))


def test_committed_sample_aggregation_rejects_cross_rank_overlap() -> None:
    """提交样本声明必须在 rank 内和 rank 间都唯一。"""

    rank_zero = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=0,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=2,
        sample_keys=("dataset-a:0", "dataset-a:2"),
    )
    rank_one = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=1,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=2,
        sample_keys=("dataset-a:1", "dataset-a:3"),
    )
    aggregated = aggregate_committed_sample_payloads(
        (rank_zero.to_payload(), rank_one.to_payload())
    )
    assert aggregated.total_declared_samples == 4
    assert aggregated.evidence_scope == DECLARED_PAYLOAD_SCOPE

    overlapping = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=1,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=2,
        sample_keys=("dataset-a:1", "dataset-a:2"),
    )
    with pytest.raises(ValueError, match="overlap across ranks"):
        aggregate_committed_sample_payloads(
            (rank_zero.to_payload(), overlapping.to_payload())
        )


def test_receipt_payloads_reject_unknown_fields_and_runtime_claims() -> None:
    """版本载荷禁止未知字段和伪造 runtime scope。"""

    payload = _plan(0).to_payload()
    payload["unknown"] = "forbidden"
    with pytest.raises(ValueError, match="incomplete or unknown"):
        RankTrainingPlanReceipt.from_payload(payload)

    runtime_claim = _plan(0).to_payload()
    runtime_claim["evidence_scope"] = "GPU_RUNTIME_VERIFIED"
    with pytest.raises(ValueError, match="cannot claim runtime observation"):
        RankTrainingPlanReceipt.from_payload(runtime_claim)
