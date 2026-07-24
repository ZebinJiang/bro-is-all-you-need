"""分布式训练计划、提交样本和资源回收的严格收据契约。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, cast

from autovla.training.checkpointing.identity import stable_fingerprint

RANK_PLAN_RECEIPT_SCHEMA = "autovla.training.rank_plan_receipt.v1"
ALL_RANK_PLAN_RECEIPT_SCHEMA = "autovla.training.all_rank_plan_receipt.v1"
RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA = "autovla.training.rank_committed_samples.v1"
ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA = (
    "autovla.training.all_rank_committed_sample_uniqueness.v1"
)
STRATEGY_TEARDOWN_RECEIPT_SCHEMA = "autovla.training.strategy_teardown.v1"
DECLARED_PAYLOAD_SCOPE = "DECLARED_PAYLOADS_ONLY"

_SHA256_CHARACTERS = frozenset("0123456789abcdef")


def _require_text(value: object, name: str) -> str:
    """读取非空文本且拒绝隐式字符串转换。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_integer(value: object, name: str, *, minimum: int = 0) -> int:
    """读取排除 bool 的有下界整数。"""

    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _require_sha256(value: object, name: str) -> str:
    """读取规范小写 SHA256。"""

    text = _require_text(value, name)
    if len(text) != 64 or any(character not in _SHA256_CHARACTERS for character in text):
        raise ValueError(f"{name} must be a lowercase SHA256")
    return text


def _strict_mapping(value: object, name: str) -> dict[str, object]:
    """复制字符串键映射并拒绝动态键转换。"""

    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    output: dict[str, object] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{name} keys must be non-empty strings")
        output[key] = item
    return output


def _require_fields(
    payload: Mapping[str, object],
    expected: set[str],
    name: str,
) -> None:
    """要求持久化载荷字段精确匹配版本 schema。"""

    if set(payload) != expected:
        raise ValueError(f"{name} fields are incomplete or unknown")


@dataclass(frozen=True, slots=True)
class DistributedRunReceiptIdentity:
    """绑定后续 GPU 收据必须共同声明的运行和计划身份。"""

    run_id: str
    source_sha: str
    family_key: str
    strategy: str
    world_size: int
    topology_fingerprint: str
    training_plan_fingerprint: str

    def __post_init__(self) -> None:
        """拒绝缺失运行身份、非精确 Git SHA 和无效指纹。"""

        for name in ("run_id", "family_key", "strategy"):
            _require_text(getattr(self, name), name)
        source_sha = _require_text(self.source_sha, "source_sha")
        if len(source_sha) != 40 or any(
            character not in _SHA256_CHARACTERS for character in source_sha
        ):
            raise ValueError("source_sha must be a full lowercase Git commit")
        _require_integer(self.world_size, "world_size", minimum=1)
        _require_sha256(self.topology_fingerprint, "topology_fingerprint")
        _require_sha256(self.training_plan_fingerprint, "training_plan_fingerprint")

    def to_payload(self) -> dict[str, object]:
        """返回确定字段顺序无关的身份载荷。"""

        return {
            "run_id": self.run_id,
            "source_sha": self.source_sha,
            "family_key": self.family_key,
            "strategy": self.strategy,
            "world_size": self.world_size,
            "topology_fingerprint": self.topology_fingerprint,
            "training_plan_fingerprint": self.training_plan_fingerprint,
        }

    @classmethod
    def from_payload(cls, value: object) -> DistributedRunReceiptIdentity:
        """从严格映射恢复运行身份。"""

        payload = _strict_mapping(value, "distributed run receipt identity")
        expected = {
            "run_id",
            "source_sha",
            "family_key",
            "strategy",
            "world_size",
            "topology_fingerprint",
            "training_plan_fingerprint",
        }
        _require_fields(payload, expected, "distributed run receipt identity")
        return cls(
            run_id=_require_text(payload["run_id"], "run_id"),
            source_sha=_require_text(payload["source_sha"], "source_sha"),
            family_key=_require_text(payload["family_key"], "family_key"),
            strategy=_require_text(payload["strategy"], "strategy"),
            world_size=_require_integer(payload["world_size"], "world_size", minimum=1),
            topology_fingerprint=_require_sha256(
                payload["topology_fingerprint"],
                "topology_fingerprint",
            ),
            training_plan_fingerprint=_require_sha256(
                payload["training_plan_fingerprint"],
                "training_plan_fingerprint",
            ),
        )


@dataclass(frozen=True, slots=True)
class RankTrainingPlanReceipt:
    """声明一个 rank 预期提交的批次计划,不声称运行时已执行。"""

    identity: DistributedRunReceiptIdentity
    rank: int
    access_mode: str
    partition_policy: str
    committed_batches: int
    micro_batch_size: int
    gradient_accumulation_steps: int
    schema_version: str = RANK_PLAN_RECEIPT_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        """校验 rank、计划计数和静态证据边界。"""

        if self.schema_version != RANK_PLAN_RECEIPT_SCHEMA:
            raise ValueError("unsupported rank training plan receipt schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("rank training plan receipt cannot claim runtime observation")
        rank = _require_integer(self.rank, "rank")
        if rank >= self.identity.world_size:
            raise ValueError("rank training plan receipt rank is out of range")
        for name in ("access_mode", "partition_policy"):
            _require_text(getattr(self, name), name)
        _require_integer(self.committed_batches, "committed_batches")
        _require_integer(self.micro_batch_size, "micro_batch_size", minimum=1)
        _require_integer(
            self.gradient_accumulation_steps,
            "gradient_accumulation_steps",
            minimum=1,
        )
        object.__setattr__(self, "fingerprint", stable_fingerprint(self.to_payload()))

    def to_payload(self) -> dict[str, object]:
        """返回可供严格 collective 传输的纯载荷。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "rank": self.rank,
            "access_mode": self.access_mode,
            "partition_policy": self.partition_policy,
            "committed_batches": self.committed_batches,
            "micro_batch_size": self.micro_batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
        }

    @classmethod
    def from_payload(cls, value: object) -> RankTrainingPlanReceipt:
        """严格恢复 rank 计划载荷并重算指纹。"""

        payload = _strict_mapping(value, "rank training plan receipt")
        expected = {
            "schema_version",
            "evidence_scope",
            "identity",
            "rank",
            "access_mode",
            "partition_policy",
            "committed_batches",
            "micro_batch_size",
            "gradient_accumulation_steps",
        }
        _require_fields(payload, expected, "rank training plan receipt")
        return cls(
            schema_version=_require_text(payload["schema_version"], "schema_version"),
            evidence_scope=_require_text(payload["evidence_scope"], "evidence_scope"),
            identity=DistributedRunReceiptIdentity.from_payload(payload["identity"]),
            rank=_require_integer(payload["rank"], "rank"),
            access_mode=_require_text(payload["access_mode"], "access_mode"),
            partition_policy=_require_text(payload["partition_policy"], "partition_policy"),
            committed_batches=_require_integer(
                payload["committed_batches"],
                "committed_batches",
            ),
            micro_batch_size=_require_integer(
                payload["micro_batch_size"],
                "micro_batch_size",
                minimum=1,
            ),
            gradient_accumulation_steps=_require_integer(
                payload["gradient_accumulation_steps"],
                "gradient_accumulation_steps",
                minimum=1,
            ),
        )


@dataclass(frozen=True, slots=True)
class AllRankTrainingPlanReceipt:
    """保存按 rank 排序且结构一致的计划声明集合。"""

    identity: DistributedRunReceiptIdentity
    ranks: tuple[RankTrainingPlanReceipt, ...]
    schema_version: str = ALL_RANK_PLAN_RECEIPT_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        """要求全 rank 覆盖、相同计划字段和确定顺序。"""

        if self.schema_version != ALL_RANK_PLAN_RECEIPT_SCHEMA:
            raise ValueError("unsupported all-rank training plan receipt schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("all-rank plan receipt cannot claim runtime observation")
        if len(self.ranks) != self.identity.world_size:
            raise ValueError("all-rank plan receipt coverage is incomplete")
        expected_ranks = tuple(range(self.identity.world_size))
        if tuple(receipt.rank for receipt in self.ranks) != expected_ranks:
            raise ValueError("all-rank plan receipts must be ordered by complete rank coverage")
        baseline: tuple[object, ...] | None = None
        for receipt in self.ranks:
            if receipt.identity != self.identity:
                raise ValueError("all-rank plan receipt identity drifted")
            current = (
                receipt.access_mode,
                receipt.partition_policy,
                receipt.committed_batches,
                receipt.micro_batch_size,
                receipt.gradient_accumulation_steps,
            )
            if baseline is None:
                baseline = current
            elif current != baseline:
                raise ValueError("all-rank training plans are not identical")
        object.__setattr__(
            self,
            "fingerprint",
            stable_fingerprint(
                {
                    "schema_version": self.schema_version,
                    "evidence_scope": self.evidence_scope,
                    "identity": self.identity.to_payload(),
                    "rank_fingerprints": tuple(receipt.fingerprint for receipt in self.ranks),
                }
            ),
        )

    def to_payload(self) -> dict[str, object]:
        """返回可持久化的按 rank 排序计划聚合。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "ranks": tuple(receipt.to_payload() for receipt in self.ranks),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class RankCommittedSampleReceipt:
    """声明一个 rank 已提交的稳定样本键序列。"""

    identity: DistributedRunReceiptIdentity
    rank: int
    epoch: int
    first_optimizer_step: int
    last_optimizer_step: int
    sample_keys: tuple[str, ...]
    schema_version: str = RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        """拒绝 rank 内重复、空键和倒序 step 窗口。"""

        if self.schema_version != RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA:
            raise ValueError("unsupported rank committed-sample receipt schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("rank committed-sample receipt cannot claim runtime observation")
        rank = _require_integer(self.rank, "rank")
        if rank >= self.identity.world_size:
            raise ValueError("rank committed-sample receipt rank is out of range")
        _require_integer(self.epoch, "epoch")
        first = _require_integer(self.first_optimizer_step, "first_optimizer_step")
        last = _require_integer(self.last_optimizer_step, "last_optimizer_step")
        if last < first:
            raise ValueError("committed-sample optimizer step window is reversed")
        if any(not isinstance(key, str) or not key.strip() for key in self.sample_keys):
            raise ValueError("committed sample keys must be non-empty text")
        if len(set(self.sample_keys)) != len(self.sample_keys):
            raise ValueError("rank committed sample keys must be unique")
        object.__setattr__(self, "fingerprint", stable_fingerprint(self.to_payload()))

    def to_payload(self) -> dict[str, object]:
        """返回不包含张量或任意对象的严格样本载荷。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "rank": self.rank,
            "epoch": self.epoch,
            "first_optimizer_step": self.first_optimizer_step,
            "last_optimizer_step": self.last_optimizer_step,
            "sample_keys": self.sample_keys,
        }

    @classmethod
    def from_payload(cls, value: object) -> RankCommittedSampleReceipt:
        """严格恢复 rank 提交样本载荷。"""

        payload = _strict_mapping(value, "rank committed-sample receipt")
        expected = {
            "schema_version",
            "evidence_scope",
            "identity",
            "rank",
            "epoch",
            "first_optimizer_step",
            "last_optimizer_step",
            "sample_keys",
        }
        _require_fields(payload, expected, "rank committed-sample receipt")
        raw_keys = payload["sample_keys"]
        if not isinstance(raw_keys, (list, tuple)):
            raise TypeError("sample_keys must be a sequence")
        keys = tuple(
            _require_text(key, f"sample_keys[{index}]")
            for index, key in enumerate(cast(Sequence[object], raw_keys))
        )
        return cls(
            schema_version=_require_text(payload["schema_version"], "schema_version"),
            evidence_scope=_require_text(payload["evidence_scope"], "evidence_scope"),
            identity=DistributedRunReceiptIdentity.from_payload(payload["identity"]),
            rank=_require_integer(payload["rank"], "rank"),
            epoch=_require_integer(payload["epoch"], "epoch"),
            first_optimizer_step=_require_integer(
                payload["first_optimizer_step"],
                "first_optimizer_step",
            ),
            last_optimizer_step=_require_integer(
                payload["last_optimizer_step"],
                "last_optimizer_step",
            ),
            sample_keys=keys,
        )


@dataclass(frozen=True, slots=True)
class AllRankCommittedSampleReceipt:
    """保存全 rank 声明样本无交集的结构化聚合结果。"""

    identity: DistributedRunReceiptIdentity
    ranks: tuple[RankCommittedSampleReceipt, ...]
    total_declared_samples: int
    schema_version: str = ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        """验证完整 rank 覆盖和声明样本集合无交集。"""

        if self.schema_version != ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA:
            raise ValueError("unsupported all-rank committed-sample receipt schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("committed-sample receipt cannot claim runtime observation")
        if len(self.ranks) != self.identity.world_size:
            raise ValueError("all-rank committed-sample receipt coverage is incomplete")
        if tuple(receipt.rank for receipt in self.ranks) != tuple(range(self.identity.world_size)):
            raise ValueError("committed-sample receipts must be ordered by complete rank coverage")
        seen: set[str] = set()
        for receipt in self.ranks:
            if receipt.identity != self.identity:
                raise ValueError("committed-sample receipt identity drifted")
            overlap = seen.intersection(receipt.sample_keys)
            if overlap:
                raise ValueError(f"committed sample keys overlap across ranks: {sorted(overlap)}")
            seen.update(receipt.sample_keys)
        if self.total_declared_samples != len(seen):
            raise ValueError("total_declared_samples differs from unique declared sample count")
        object.__setattr__(
            self,
            "fingerprint",
            stable_fingerprint(
                {
                    "schema_version": self.schema_version,
                    "evidence_scope": self.evidence_scope,
                    "identity": self.identity.to_payload(),
                    "rank_fingerprints": tuple(receipt.fingerprint for receipt in self.ranks),
                    "total_declared_samples": self.total_declared_samples,
                }
            ),
        )

    def to_payload(self) -> dict[str, object]:
        """返回可持久化的声明样本唯一性聚合。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "ranks": tuple(receipt.to_payload() for receipt in self.ranks),
            "total_declared_samples": self.total_declared_samples,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class StrategySessionIdentity:
    """绑定 prepared session 的拓扑和策略配置身份。"""

    strategy: str
    rank: int
    world_size: int
    topology_fingerprint: str
    configuration_fingerprint: str

    def __post_init__(self) -> None:
        """校验 session 身份字段。"""

        _require_text(self.strategy, "strategy")
        rank = _require_integer(self.rank, "rank")
        world_size = _require_integer(self.world_size, "world_size", minimum=1)
        if rank >= world_size:
            raise ValueError("strategy session rank is out of range")
        _require_sha256(self.topology_fingerprint, "topology_fingerprint")
        _require_sha256(self.configuration_fingerprint, "configuration_fingerprint")

    def to_payload(self) -> dict[str, object]:
        """返回 teardown 等生命周期收据共享的 session 身份。"""

        return {
            "strategy": self.strategy,
            "rank": self.rank,
            "world_size": self.world_size,
            "topology_fingerprint": self.topology_fingerprint,
            "configuration_fingerprint": self.configuration_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class StrategyTeardownReceipt:
    """记录一次幂等 session 回收尝试及其精确资源归属。"""

    identity: StrategySessionIdentity
    step_state_status: str
    engine_status: str
    references_cleared: bool
    process_group_owned: bool
    process_group_status: str
    failure_types: tuple[str, ...]
    schema_version: str = STRATEGY_TEARDOWN_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        """拒绝未知状态和矛盾回收结论。"""

        if self.schema_version != STRATEGY_TEARDOWN_RECEIPT_SCHEMA:
            raise ValueError("unsupported strategy teardown receipt schema")
        if self.step_state_status not in {"clean", "abandoned_incomplete_step"}:
            raise ValueError("unknown teardown step-state status")
        if self.engine_status not in {"destroyed", "destroy_not_exposed", "failed"}:
            raise ValueError("unknown teardown engine status")
        if type(self.references_cleared) is not bool or type(self.process_group_owned) is not bool:
            raise TypeError("teardown ownership flags must be booleans")
        if self.process_group_status not in {
            "destroyed",
            "already_absent",
            "preserved_external",
            "failed",
        }:
            raise ValueError("unknown teardown process-group status")
        if any(not item.strip() for item in self.failure_types):
            raise ValueError("teardown failure types must be non-empty text")
        if self.failure_types and not (
            self.step_state_status == "abandoned_incomplete_step"
            or self.engine_status == "failed"
            or self.process_group_status == "failed"
        ):
            raise ValueError("teardown failures require a failed resource status")

    def to_payload(self) -> dict[str, object]:
        """返回不含异常对象的确定性资源回收载荷。"""

        return {
            "schema_version": self.schema_version,
            "identity": self.identity.to_payload(),
            "step_state_status": self.step_state_status,
            "engine_status": self.engine_status,
            "references_cleared": self.references_cleared,
            "process_group_owned": self.process_group_owned,
            "process_group_status": self.process_group_status,
            "failure_types": self.failure_types,
        }


class DistributedReceiptTransport(Protocol):
    """约束后续 GPU 运行聚合严格收据的最小 collective 表面。"""

    @property
    def rank(self) -> int:
        """返回本地 rank。"""

        ...

    @property
    def world_size(self) -> int:
        """返回 collective world size。"""

        ...

    def gather_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """按 rank 顺序在全部 rank 返回严格载荷。"""

        ...


def aggregate_rank_plan_payloads(
    payloads: Sequence[Mapping[str, object]],
) -> AllRankTrainingPlanReceipt:
    """聚合声明载荷并验证全 rank 计划一致,不生成运行时通过结论。"""

    ranks = tuple(RankTrainingPlanReceipt.from_payload(payload) for payload in payloads)
    if not ranks:
        raise ValueError("all-rank plan aggregation requires at least one payload")
    return AllRankTrainingPlanReceipt(identity=ranks[0].identity, ranks=ranks)


def aggregate_committed_sample_payloads(
    payloads: Sequence[Mapping[str, object]],
) -> AllRankCommittedSampleReceipt:
    """聚合声明样本键并拒绝任意 rank 内或 rank 间重复。"""

    ranks = tuple(RankCommittedSampleReceipt.from_payload(payload) for payload in payloads)
    if not ranks:
        raise ValueError("committed-sample aggregation requires at least one payload")
    return AllRankCommittedSampleReceipt(
        identity=ranks[0].identity,
        ranks=ranks,
        total_declared_samples=sum(len(receipt.sample_keys) for receipt in ranks),
    )


def collect_rank_plan_receipt(
    local: RankTrainingPlanReceipt,
    transport: DistributedReceiptTransport,
) -> AllRankTrainingPlanReceipt:
    """经真实 transport 收集计划;调用方仍须持久化 GPU 运行身份和日志。"""

    if transport.rank != local.rank or transport.world_size != local.identity.world_size:
        raise ValueError("rank plan receipt transport topology differs from local identity")
    return aggregate_rank_plan_payloads(transport.gather_receipt_payloads(local.to_payload()))


def collect_committed_sample_receipt(
    local: RankCommittedSampleReceipt,
    transport: DistributedReceiptTransport,
) -> AllRankCommittedSampleReceipt:
    """经真实 transport 收集提交样本键并执行声明集合唯一性检查。"""

    if transport.rank != local.rank or transport.world_size != local.identity.world_size:
        raise ValueError("committed-sample transport topology differs from local identity")
    return aggregate_committed_sample_payloads(
        transport.gather_receipt_payloads(local.to_payload())
    )


__all__ = [
    "ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA",
    "ALL_RANK_PLAN_RECEIPT_SCHEMA",
    "DECLARED_PAYLOAD_SCOPE",
    "RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA",
    "RANK_PLAN_RECEIPT_SCHEMA",
    "STRATEGY_TEARDOWN_RECEIPT_SCHEMA",
    "AllRankCommittedSampleReceipt",
    "AllRankTrainingPlanReceipt",
    "DistributedReceiptTransport",
    "DistributedRunReceiptIdentity",
    "RankCommittedSampleReceipt",
    "RankTrainingPlanReceipt",
    "StrategySessionIdentity",
    "StrategyTeardownReceipt",
    "aggregate_committed_sample_payloads",
    "aggregate_rank_plan_payloads",
    "collect_committed_sample_receipt",
    "collect_rank_plan_receipt",
]
