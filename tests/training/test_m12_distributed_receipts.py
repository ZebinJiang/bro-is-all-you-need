"""M12 分布式计划与提交样本收据的纯 CPU 合同测试。"""

import json
from collections.abc import Mapping, Sequence

import pytest

from autovla.training.distributed_receipts import (
    DECLARED_PAYLOAD_SCOPE,
    MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES,
    MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK,
    MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW,
    MAX_DISTRIBUTED_WORLD_SIZE,
    RUNTIME_UNIQUENESS_STATUS,
    DistributedRunReceiptIdentity,
    RankCommittedSampleReceipt,
    RankTrainingPlanReceipt,
    aggregate_committed_sample_payloads,
    aggregate_rank_plan_payloads,
    collect_committed_sample_receipt,
    collect_rank_plan_receipt,
)


def _identity(world_size: int = 2) -> DistributedRunReceiptIdentity:
    """返回指定 world size 共享的固定测试身份。"""

    return DistributedRunReceiptIdentity(
        run_id="m12-static-contract",
        source_sha="a" * 40,
        family_key="gr00t_n1d6",
        strategy="deepspeed_zero_3",
        world_size=world_size,
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

    def gather_bounded_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """计划测试不得进入 committed-sample 路径。"""

        raise AssertionError(f"unexpected bounded payload: {payload}")

    def broadcast_receipt_payload(
        self,
        payload: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        """计划测试不得进入 committed-sample 广播。"""

        raise AssertionError(f"unexpected broadcast payload: {payload}")


class _CommittedTransport:
    """模拟只在 rank 0 聚合 digest chunk 并广播 summary。"""

    rank = 0
    world_size = 2

    def __init__(
        self,
        local: RankCommittedSampleReceipt,
        peer: RankCommittedSampleReceipt,
    ) -> None:
        """保存两个 rank 的本地收据和已发送载荷。"""

        self._local = local
        self._peer = peer
        self.payloads: list[Mapping[str, object]] = []

    def gather_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """committed-sample 路径不得使用 all-rank 原始载荷。"""

        raise AssertionError(f"unexpected all-rank payload: {payload}")

    def gather_bounded_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """按 manifest 或 chunk round 返回 rank 顺序载荷。"""

        self.payloads.append(payload)
        if payload["schema_version"].endswith("manifest.v1"):
            assert payload == self._local.manifest().to_payload()
            return (
                payload,
                self._peer.manifest().to_payload(),
            )
        chunk_index = payload["chunk_index"]
        assert isinstance(chunk_index, int)
        return (
            payload,
            self._peer.collective_slot(chunk_index).to_payload(),
        )

    def broadcast_receipt_payload(
        self,
        payload: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        """rank 0 测试直接返回待广播固定载荷。"""

        assert payload is not None
        self.payloads.append(payload)
        return payload


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
    assert aggregated.runtime_uniqueness_status == RUNTIME_UNIQUENESS_STATUS
    assert "sample_keys" not in repr(aggregated.to_payload())

    overlapping = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=1,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=2,
        sample_keys=("dataset-a:1", "dataset-a:2"),
    )
    with pytest.raises(ValueError, match="collision or overlap"):
        aggregate_committed_sample_payloads((rank_zero.to_payload(), overlapping.to_payload()))


def test_committed_sample_collective_transmits_only_bounded_digest_chunks() -> None:
    """collective 不发送原始 key,非 canonical rank 只需固定 summary。"""

    rank_zero = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=0,
        epoch=3,
        first_optimizer_step=20,
        last_optimizer_step=21,
        sample_keys=tuple(
            f"dataset-a:{index}" for index in range(MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK + 1)
        ),
    )
    rank_one = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=1,
        epoch=3,
        first_optimizer_step=20,
        last_optimizer_step=21,
        sample_keys=("dataset-b:0",),
    )
    transport = _CommittedTransport(rank_zero, rank_one)

    summary = collect_committed_sample_receipt(rank_zero, transport)

    assert summary.total_declared_samples == MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK + 2
    assert summary.epoch == 3
    assert summary.first_optimizer_step == 20
    assert summary.last_optimizer_step == 21
    assert summary.runtime_uniqueness_status == "runtime_unverified"
    for payload in transport.payloads:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        assert len(encoded) <= MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES
        assert "sample_keys" not in payload
        assert "dataset-a:" not in encoded.decode()


def test_committed_sample_bounds_do_not_become_an_unbounded_full_set() -> None:
    """sample/world 增长仍受显式 window、chunk 和 encoded bytes 上限约束。"""

    at_bound = RankCommittedSampleReceipt(
        identity=_identity(),
        rank=0,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=1,
        sample_keys=tuple(
            f"bounded:{index}" for index in range(MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW)
        ),
    )
    chunks = at_bound.digest_chunks()
    assert all(len(chunk.digests) <= MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK for chunk in chunks)
    assert all(
        len(
            json.dumps(
                chunk.to_payload(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        <= MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES
        for chunk in chunks
    )

    with pytest.raises(ValueError, match="optimizer window exceeds"):
        RankCommittedSampleReceipt(
            identity=_identity(),
            rank=0,
            epoch=0,
            first_optimizer_step=0,
            last_optimizer_step=1,
            sample_keys=tuple(
                f"unbounded:{index}" for index in range(MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW + 1)
            ),
        )

    large_world = RankCommittedSampleReceipt(
        identity=_identity(MAX_DISTRIBUTED_WORLD_SIZE),
        rank=0,
        epoch=0,
        first_optimizer_step=0,
        last_optimizer_step=1,
        sample_keys=tuple(
            f"large-world:{index}" for index in range(MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK)
        ),
    )
    large_world_payload = large_world.collective_slot(0).to_payload()
    assert (
        len(
            json.dumps(
                large_world_payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        <= MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES
    )

    with pytest.raises(ValueError, match="world_size must be <="):
        _identity(MAX_DISTRIBUTED_WORLD_SIZE + 1)


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
