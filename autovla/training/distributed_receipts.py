"""分布式训练计划、提交样本和资源回收的严格收据契约。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, cast

from autovla.training.checkpointing.identity import stable_fingerprint

RANK_PLAN_RECEIPT_SCHEMA = "autovla.training.rank_plan_receipt.v1"
ALL_RANK_PLAN_RECEIPT_SCHEMA = "autovla.training.all_rank_plan_receipt.v1"
RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA = "autovla.training.rank_committed_samples.v2"
ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA = (
    "autovla.training.all_rank_committed_sample_uniqueness.v2"
)
COMMITTED_SAMPLE_MANIFEST_SCHEMA = "autovla.training.committed_sample_manifest.v1"
COMMITTED_SAMPLE_DIGEST_CHUNK_SCHEMA = "autovla.training.committed_sample_digest_chunk.v1"
COMMITTED_SAMPLE_CONTROL_SCHEMA = "autovla.training.committed_sample_control.v1"
STRATEGY_TEARDOWN_RECEIPT_SCHEMA = "autovla.training.strategy_teardown.v1"
DECLARED_PAYLOAD_SCOPE = "DECLARED_PAYLOADS_ONLY"
RUNTIME_UNIQUENESS_STATUS = "runtime_unverified"

MAX_DISTRIBUTED_WORLD_SIZE = 4096
MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW = 4096
MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK = 64
MAX_COMMITTED_SAMPLE_CHUNKS_PER_WINDOW = (
    MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW + MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK - 1
) // MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK
MAX_COMMITTED_SAMPLE_KEY_ENCODED_BYTES = 1024
MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES = 8192

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


def _canonical_encoded_size(payload: Mapping[str, object]) -> int:
    """返回严格 JSON collective 载荷的 UTF-8 字节数。"""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return len(encoded)


def _require_bounded_collective_payload(
    payload: Mapping[str, object],
    *,
    name: str,
) -> None:
    """拒绝超过固定 collective 编码上限的载荷。"""

    size = _canonical_encoded_size(payload)
    if size > MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES:
        raise ValueError(
            f"{name} encoded payload exceeds "
            f"{MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES} bytes"
        )


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
        if self.world_size > MAX_DISTRIBUTED_WORLD_SIZE:
            raise ValueError(
                f"world_size must be <= {MAX_DISTRIBUTED_WORLD_SIZE} for bounded receipts"
            )
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
    """在本 rank 保存一个 optimizer window 的原始稳定样本键。"""

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
        """拒绝 rank 内重复、超界 key 数/字节和倒序 step 窗口。"""

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
        if len(self.sample_keys) > MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW:
            raise ValueError(
                "committed sample optimizer window exceeds "
                f"{MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW} records"
            )
        for key in self.sample_keys:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("committed sample keys must be non-empty text")
            if len(key.encode("utf-8")) > MAX_COMMITTED_SAMPLE_KEY_ENCODED_BYTES:
                raise ValueError(
                    "committed sample key exceeds "
                    f"{MAX_COMMITTED_SAMPLE_KEY_ENCODED_BYTES} encoded bytes"
                )
        if len(set(self.sample_keys)) != len(self.sample_keys):
            raise ValueError("rank committed sample keys must be unique")
        object.__setattr__(self, "fingerprint", stable_fingerprint(self.to_payload()))

    def to_payload(self) -> dict[str, object]:
        """返回仅供本地持久化或 canonical rank 使用的原始键载荷。"""

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

    def manifest(self) -> CommittedSampleManifest:
        """返回不含原始 key 或逐样本 digest 的固定结构 manifest。"""

        chunk_count = (
            len(self.sample_keys) + MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK - 1
        ) // MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK
        return CommittedSampleManifest(
            identity=self.identity,
            rank=self.rank,
            epoch=self.epoch,
            first_optimizer_step=self.first_optimizer_step,
            last_optimizer_step=self.last_optimizer_step,
            record_count=len(self.sample_keys),
            chunk_count=chunk_count,
        )

    def digest_chunks(self) -> tuple[CommittedSampleDigestChunk, ...]:
        """把本 rank 原始 key 转换为有界 SHA256 digest chunk。"""

        manifest = self.manifest()
        return tuple(self.collective_slot(index) for index in range(manifest.chunk_count))

    def collective_slot(self, chunk_index: int) -> CommittedSampleDigestChunk:
        """返回给定 collective round 的有界 active 或 empty slot。"""

        _require_integer(chunk_index, "chunk_index")
        manifest = self.manifest()
        if chunk_index < manifest.chunk_count:
            start = chunk_index * MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK
            stop = (chunk_index + 1) * MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK
            digests = tuple(
                hashlib.sha256(key.encode("utf-8")).hexdigest()
                for key in self.sample_keys[start:stop]
            )
            return CommittedSampleDigestChunk(
                identity=self.identity,
                rank=self.rank,
                epoch=self.epoch,
                first_optimizer_step=self.first_optimizer_step,
                last_optimizer_step=self.last_optimizer_step,
                chunk_index=chunk_index,
                chunk_count=manifest.chunk_count,
                total_record_count=manifest.record_count,
                digests=digests,
                active=True,
            )
        return CommittedSampleDigestChunk(
            identity=self.identity,
            rank=self.rank,
            epoch=self.epoch,
            first_optimizer_step=self.first_optimizer_step,
            last_optimizer_step=self.last_optimizer_step,
            chunk_index=chunk_index,
            chunk_count=manifest.chunk_count,
            total_record_count=manifest.record_count,
            digests=(),
            active=False,
        )

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
class CommittedSampleManifest:
    """声明一个 rank optimizer window 的有界 chunk 计划。"""

    identity: DistributedRunReceiptIdentity
    rank: int
    epoch: int
    first_optimizer_step: int
    last_optimizer_step: int
    record_count: int
    chunk_count: int
    schema_version: str = COMMITTED_SAMPLE_MANIFEST_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE

    def __post_init__(self) -> None:
        """校验 rank、window 和由固定 chunk 上限决定的计数。"""

        if self.schema_version != COMMITTED_SAMPLE_MANIFEST_SCHEMA:
            raise ValueError("unsupported committed-sample manifest schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("committed-sample manifest cannot claim runtime observation")
        rank = _require_integer(self.rank, "rank")
        if rank >= self.identity.world_size:
            raise ValueError("committed-sample manifest rank is out of range")
        _require_integer(self.epoch, "epoch")
        first = _require_integer(self.first_optimizer_step, "first_optimizer_step")
        last = _require_integer(self.last_optimizer_step, "last_optimizer_step")
        if last < first:
            raise ValueError("committed-sample optimizer step window is reversed")
        records = _require_integer(self.record_count, "record_count")
        if records > MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW:
            raise ValueError("committed-sample manifest record count exceeds the window bound")
        chunks = _require_integer(self.chunk_count, "chunk_count")
        expected_chunks = (
            records + MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK - 1
        ) // MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK
        if chunks != expected_chunks:
            raise ValueError("committed-sample manifest chunk count is inconsistent")
        _require_bounded_collective_payload(
            self.to_payload(),
            name="committed-sample manifest",
        )

    def to_payload(self) -> dict[str, object]:
        """返回固定结构、无逐样本材料的 manifest。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "rank": self.rank,
            "epoch": self.epoch,
            "first_optimizer_step": self.first_optimizer_step,
            "last_optimizer_step": self.last_optimizer_step,
            "record_count": self.record_count,
            "chunk_count": self.chunk_count,
        }

    @classmethod
    def from_payload(cls, value: object) -> CommittedSampleManifest:
        """从严格 collective 载荷恢复 manifest。"""

        payload = _strict_mapping(value, "committed-sample manifest")
        expected = {
            "schema_version",
            "evidence_scope",
            "identity",
            "rank",
            "epoch",
            "first_optimizer_step",
            "last_optimizer_step",
            "record_count",
            "chunk_count",
        }
        _require_fields(payload, expected, "committed-sample manifest")
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
            record_count=_require_integer(payload["record_count"], "record_count"),
            chunk_count=_require_integer(payload["chunk_count"], "chunk_count"),
        )


@dataclass(frozen=True, slots=True)
class CommittedSampleDigestChunk:
    """传输一个 rank 在一个 collective round 的固定上界 digest records。"""

    identity: DistributedRunReceiptIdentity
    rank: int
    epoch: int
    first_optimizer_step: int
    last_optimizer_step: int
    chunk_index: int
    chunk_count: int
    total_record_count: int
    digests: tuple[str, ...]
    active: bool
    schema_version: str = COMMITTED_SAMPLE_DIGEST_CHUNK_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE

    def __post_init__(self) -> None:
        """校验固定 record/bytes 上限和 active/empty slot 一致性。"""

        if self.schema_version != COMMITTED_SAMPLE_DIGEST_CHUNK_SCHEMA:
            raise ValueError("unsupported committed-sample digest chunk schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("committed-sample digest chunk cannot claim runtime observation")
        rank = _require_integer(self.rank, "rank")
        if rank >= self.identity.world_size:
            raise ValueError("committed-sample digest chunk rank is out of range")
        _require_integer(self.epoch, "epoch")
        first = _require_integer(self.first_optimizer_step, "first_optimizer_step")
        last = _require_integer(self.last_optimizer_step, "last_optimizer_step")
        if last < first:
            raise ValueError("committed-sample optimizer step window is reversed")
        index = _require_integer(self.chunk_index, "chunk_index")
        chunks = _require_integer(self.chunk_count, "chunk_count")
        records = _require_integer(self.total_record_count, "total_record_count")
        if records > MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW:
            raise ValueError("committed-sample digest chunk exceeds the window bound")
        if type(self.active) is not bool:
            raise TypeError("committed-sample digest chunk active must be boolean")
        if len(self.digests) > MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK:
            raise ValueError("committed-sample digest chunk exceeds the record bound")
        for position, digest in enumerate(self.digests):
            _require_sha256(digest, f"digests[{position}]")
        if len(set(self.digests)) != len(self.digests):
            raise ValueError("committed-sample digest chunk contains a collision or overlap")
        if self.active:
            if index >= chunks or not self.digests:
                raise ValueError("active committed-sample digest chunk is inconsistent")
        elif index < chunks or self.digests:
            raise ValueError("empty committed-sample digest slot is inconsistent")
        _require_bounded_collective_payload(
            self.to_payload(),
            name="committed-sample digest chunk",
        )

    def to_payload(self) -> dict[str, object]:
        """返回不含原始 key 且有固定编码上限的 chunk。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "identity": self.identity.to_payload(),
            "rank": self.rank,
            "epoch": self.epoch,
            "first_optimizer_step": self.first_optimizer_step,
            "last_optimizer_step": self.last_optimizer_step,
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
            "total_record_count": self.total_record_count,
            "digests": self.digests,
            "active": self.active,
        }

    @classmethod
    def from_payload(cls, value: object) -> CommittedSampleDigestChunk:
        """从严格 collective 载荷恢复一个 digest chunk。"""

        payload = _strict_mapping(value, "committed-sample digest chunk")
        expected = {
            "schema_version",
            "evidence_scope",
            "identity",
            "rank",
            "epoch",
            "first_optimizer_step",
            "last_optimizer_step",
            "chunk_index",
            "chunk_count",
            "total_record_count",
            "digests",
            "active",
        }
        _require_fields(payload, expected, "committed-sample digest chunk")
        raw_digests = payload["digests"]
        if not isinstance(raw_digests, (list, tuple)):
            raise TypeError("committed-sample digests must be a sequence")
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
            chunk_index=_require_integer(payload["chunk_index"], "chunk_index"),
            chunk_count=_require_integer(payload["chunk_count"], "chunk_count"),
            total_record_count=_require_integer(
                payload["total_record_count"],
                "total_record_count",
            ),
            digests=tuple(
                _require_sha256(digest, f"digests[{index}]")
                for index, digest in enumerate(cast(Sequence[object], raw_digests))
            ),
            active=payload["active"],
        )


@dataclass(frozen=True, slots=True)
class AllRankCommittedSampleReceipt:
    """保存 canonical rank 验证后广播的固定大小 window summary。"""

    identity: DistributedRunReceiptIdentity
    epoch: int
    first_optimizer_step: int
    last_optimizer_step: int
    total_declared_samples: int
    processed_digest_chunks: int
    digest_fingerprint: str
    schema_version: str = ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA
    evidence_scope: str = DECLARED_PAYLOAD_SCOPE
    runtime_uniqueness_status: str = RUNTIME_UNIQUENESS_STATUS
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        """校验固定 summary 且明确不声称真实 runtime uniqueness。"""

        if self.schema_version != ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA:
            raise ValueError("unsupported all-rank committed-sample receipt schema")
        if self.evidence_scope != DECLARED_PAYLOAD_SCOPE:
            raise ValueError("committed-sample receipt cannot claim runtime observation")
        if self.runtime_uniqueness_status != RUNTIME_UNIQUENESS_STATUS:
            raise ValueError("committed-sample runtime uniqueness must remain unverified")
        _require_integer(self.epoch, "epoch")
        first = _require_integer(self.first_optimizer_step, "first_optimizer_step")
        last = _require_integer(self.last_optimizer_step, "last_optimizer_step")
        if last < first:
            raise ValueError("committed-sample optimizer step window is reversed")
        total = _require_integer(self.total_declared_samples, "total_declared_samples")
        if total > (self.identity.world_size * MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW):
            raise ValueError("all-rank committed-sample total exceeds the bounded protocol")
        _require_integer(self.processed_digest_chunks, "processed_digest_chunks")
        _require_sha256(self.digest_fingerprint, "digest_fingerprint")
        object.__setattr__(
            self,
            "fingerprint",
            stable_fingerprint(self._fingerprint_payload()),
        )
        _require_bounded_collective_payload(
            self.to_payload(),
            name="all-rank committed-sample summary",
        )

    def _fingerprint_payload(self) -> dict[str, object]:
        """返回不含递归 fingerprint 字段的 summary 身份。"""

        return {
            "schema_version": self.schema_version,
            "evidence_scope": self.evidence_scope,
            "runtime_uniqueness_status": self.runtime_uniqueness_status,
            "identity": self.identity.to_payload(),
            "epoch": self.epoch,
            "first_optimizer_step": self.first_optimizer_step,
            "last_optimizer_step": self.last_optimizer_step,
            "total_declared_samples": self.total_declared_samples,
            "processed_digest_chunks": self.processed_digest_chunks,
            "digest_fingerprint": self.digest_fingerprint,
        }

    def to_payload(self) -> dict[str, object]:
        """返回广播给所有 rank 的固定结构 summary。"""

        return {**self._fingerprint_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_payload(cls, value: object) -> AllRankCommittedSampleReceipt:
        """严格恢复并重算 canonical summary fingerprint。"""

        payload = _strict_mapping(value, "all-rank committed-sample summary")
        expected = {
            "schema_version",
            "evidence_scope",
            "runtime_uniqueness_status",
            "identity",
            "epoch",
            "first_optimizer_step",
            "last_optimizer_step",
            "total_declared_samples",
            "processed_digest_chunks",
            "digest_fingerprint",
            "fingerprint",
        }
        _require_fields(payload, expected, "all-rank committed-sample summary")
        receipt = cls(
            schema_version=_require_text(payload["schema_version"], "schema_version"),
            evidence_scope=_require_text(payload["evidence_scope"], "evidence_scope"),
            runtime_uniqueness_status=_require_text(
                payload["runtime_uniqueness_status"],
                "runtime_uniqueness_status",
            ),
            identity=DistributedRunReceiptIdentity.from_payload(payload["identity"]),
            epoch=_require_integer(payload["epoch"], "epoch"),
            first_optimizer_step=_require_integer(
                payload["first_optimizer_step"],
                "first_optimizer_step",
            ),
            last_optimizer_step=_require_integer(
                payload["last_optimizer_step"],
                "last_optimizer_step",
            ),
            total_declared_samples=_require_integer(
                payload["total_declared_samples"],
                "total_declared_samples",
            ),
            processed_digest_chunks=_require_integer(
                payload["processed_digest_chunks"],
                "processed_digest_chunks",
            ),
            digest_fingerprint=_require_sha256(
                payload["digest_fingerprint"],
                "digest_fingerprint",
            ),
        )
        if payload["fingerprint"] != receipt.fingerprint:
            raise ValueError("all-rank committed-sample summary fingerprint drifted")
        return receipt


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

    def gather_bounded_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """只在 canonical rank 0 返回按 rank 排序的有界载荷。"""

        ...

    def broadcast_receipt_payload(
        self,
        payload: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        """从 canonical rank 0 广播一个有界 control 或 summary。"""

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
    """仅在 canonical rank 聚合本地持久化载荷并走 digest 协议。"""

    ranks = tuple(RankCommittedSampleReceipt.from_payload(payload) for payload in payloads)
    if not ranks:
        raise ValueError("committed-sample aggregation requires at least one payload")
    manifests = tuple(receipt.manifest().to_payload() for receipt in ranks)
    max_chunks = max(receipt.manifest().chunk_count for receipt in ranks)
    chunks = tuple(
        receipt.collective_slot(chunk_index).to_payload()
        for chunk_index in range(max_chunks)
        for receipt in ranks
    )
    return aggregate_committed_sample_digest_payloads(
        manifests,
        chunks,
    )


def _validated_committed_sample_manifests(
    payloads: Sequence[Mapping[str, object]],
) -> tuple[CommittedSampleManifest, ...]:
    """在 canonical rank 验证完整 rank 覆盖和一致 optimizer window。"""

    manifests = tuple(CommittedSampleManifest.from_payload(payload) for payload in payloads)
    if not manifests:
        raise ValueError("committed-sample manifests require at least one rank")
    identity = manifests[0].identity
    if len(manifests) != identity.world_size:
        raise ValueError("committed-sample manifest coverage is incomplete")
    if tuple(item.rank for item in manifests) != tuple(range(identity.world_size)):
        raise ValueError("committed-sample manifests must be ordered by complete rank coverage")
    expected_window = (
        manifests[0].epoch,
        manifests[0].first_optimizer_step,
        manifests[0].last_optimizer_step,
    )
    for manifest in manifests:
        if manifest.identity != identity:
            raise ValueError("committed-sample manifest identity drifted")
        window = (
            manifest.epoch,
            manifest.first_optimizer_step,
            manifest.last_optimizer_step,
        )
        if window != expected_window:
            raise ValueError("committed-sample optimizer window differs across ranks")
    return manifests


def aggregate_committed_sample_digest_payloads(
    manifest_payloads: Sequence[Mapping[str, object]],
    chunk_payloads: Sequence[Mapping[str, object]],
) -> AllRankCommittedSampleReceipt:
    """在 canonical rank 聚合有界 digest slots 并拒绝 overlap/collision。"""

    manifests = _validated_committed_sample_manifests(manifest_payloads)
    identity = manifests[0].identity
    max_chunks = max(manifest.chunk_count for manifest in manifests)
    expected_slot_count = identity.world_size * max_chunks
    if len(chunk_payloads) != expected_slot_count:
        raise ValueError("committed-sample digest slot coverage is incomplete")
    chunks = tuple(CommittedSampleDigestChunk.from_payload(payload) for payload in chunk_payloads)
    seen: set[str] = set()
    processed_chunks = 0
    for chunk_index in range(max_chunks):
        offset = chunk_index * identity.world_size
        round_chunks = chunks[offset : offset + identity.world_size]
        if tuple(chunk.rank for chunk in round_chunks) != tuple(range(identity.world_size)):
            raise ValueError("committed-sample digest slots must be ordered by rank per round")
        for chunk, manifest in zip(round_chunks, manifests, strict=True):
            if (
                chunk.identity != identity
                or chunk.epoch != manifest.epoch
                or chunk.first_optimizer_step != manifest.first_optimizer_step
                or chunk.last_optimizer_step != manifest.last_optimizer_step
                or chunk.chunk_index != chunk_index
                or chunk.chunk_count != manifest.chunk_count
                or chunk.total_record_count != manifest.record_count
            ):
                raise ValueError("committed-sample digest chunk identity drifted")
            expected_active = chunk_index < manifest.chunk_count
            if chunk.active is not expected_active:
                raise ValueError("committed-sample digest chunk activity drifted")
            if not chunk.active:
                continue
            processed_chunks += 1
            overlap_or_collision = seen.intersection(chunk.digests)
            if overlap_or_collision:
                raise ValueError("committed sample digest collision or overlap across ranks/chunks")
            seen.update(chunk.digests)
    total_declared_samples = sum(manifest.record_count for manifest in manifests)
    if len(seen) != total_declared_samples:
        raise ValueError("committed-sample digest coverage differs from declared records")
    digest_fingerprint = stable_fingerprint(
        {
            "identity": identity.to_payload(),
            "epoch": manifests[0].epoch,
            "first_optimizer_step": manifests[0].first_optimizer_step,
            "last_optimizer_step": manifests[0].last_optimizer_step,
            "sorted_sample_digests": tuple(sorted(seen)),
        }
    )
    return AllRankCommittedSampleReceipt(
        identity=identity,
        epoch=manifests[0].epoch,
        first_optimizer_step=manifests[0].first_optimizer_step,
        last_optimizer_step=manifests[0].last_optimizer_step,
        total_declared_samples=total_declared_samples,
        processed_digest_chunks=processed_chunks,
        digest_fingerprint=digest_fingerprint,
    )


def _committed_sample_control_payload(
    manifests: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """在 rank 0 构造固定结构的成功或失败 control。"""

    try:
        parsed = _validated_committed_sample_manifests(manifests)
    except BaseException as error:
        payload: dict[str, object] = {
            "schema_version": COMMITTED_SAMPLE_CONTROL_SCHEMA,
            "status": "error",
            "max_chunk_count": 0,
            "failure_type": type(error).__name__,
            "failure_message": str(error)[:512],
        }
    else:
        payload = {
            "schema_version": COMMITTED_SAMPLE_CONTROL_SCHEMA,
            "status": "ok",
            "max_chunk_count": max(item.chunk_count for item in parsed),
            "failure_type": "",
            "failure_message": "",
        }
    _require_bounded_collective_payload(payload, name="committed-sample control")
    return payload


def _parse_committed_sample_control(value: object) -> int:
    """恢复固定 control 并对 canonical rank 验证失败进行对称关闭。"""

    payload = _strict_mapping(value, "committed-sample control")
    _require_fields(
        payload,
        {
            "schema_version",
            "status",
            "max_chunk_count",
            "failure_type",
            "failure_message",
        },
        "committed-sample control",
    )
    if payload["schema_version"] != COMMITTED_SAMPLE_CONTROL_SCHEMA:
        raise ValueError("unsupported committed-sample control schema")
    status = payload["status"]
    if status == "error":
        failure_type = _require_text(payload["failure_type"], "failure_type")
        failure_message = _require_text(payload["failure_message"], "failure_message")
        raise RuntimeError(
            f"canonical committed-sample validation failed: {failure_type}: {failure_message}"
        )
    if status != "ok" or payload["failure_type"] != "" or payload["failure_message"] != "":
        raise ValueError("committed-sample control status is invalid")
    max_chunks = _require_integer(payload["max_chunk_count"], "max_chunk_count")
    if max_chunks > MAX_COMMITTED_SAMPLE_CHUNKS_PER_WINDOW:
        raise ValueError("committed-sample control exceeds the bounded chunk count")
    return max_chunks


def _committed_sample_summary_envelope(
    summary: AllRankCommittedSampleReceipt | None,
    error: BaseException | None,
) -> dict[str, object]:
    """构造固定结构 summary/failure 广播,避免传播全局 digest 集。"""

    if (summary is None) == (error is None):
        raise ValueError("committed-sample summary envelope requires one result")
    payload: dict[str, object] = {
        "schema_version": COMMITTED_SAMPLE_CONTROL_SCHEMA,
        "status": "ok" if error is None else "error",
        "summary": {} if summary is None else summary.to_payload(),
        "failure_type": "" if error is None else type(error).__name__,
        "failure_message": "" if error is None else str(error)[:512],
    }
    _require_bounded_collective_payload(payload, name="committed-sample summary envelope")
    return payload


def _parse_committed_sample_summary_envelope(
    value: object,
) -> AllRankCommittedSampleReceipt:
    """恢复固定 summary 或对称传播 canonical rank 错误。"""

    payload = _strict_mapping(value, "committed-sample summary envelope")
    _require_fields(
        payload,
        {
            "schema_version",
            "status",
            "summary",
            "failure_type",
            "failure_message",
        },
        "committed-sample summary envelope",
    )
    if payload["schema_version"] != COMMITTED_SAMPLE_CONTROL_SCHEMA:
        raise ValueError("unsupported committed-sample summary envelope schema")
    if payload["status"] == "error":
        failure_type = _require_text(payload["failure_type"], "failure_type")
        failure_message = _require_text(payload["failure_message"], "failure_message")
        raise RuntimeError(
            f"canonical committed-sample aggregation failed: {failure_type}: {failure_message}"
        )
    if (
        payload["status"] != "ok"
        or payload["failure_type"] != ""
        or payload["failure_message"] != ""
    ):
        raise ValueError("committed-sample summary envelope status is invalid")
    return AllRankCommittedSampleReceipt.from_payload(payload["summary"])


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
    """经 rank0-only bounded digest chunks 聚合并广播固定 summary。"""

    if transport.rank != local.rank or transport.world_size != local.identity.world_size:
        raise ValueError("committed-sample transport topology differs from local identity")
    manifest_payloads = transport.gather_bounded_receipt_payloads(local.manifest().to_payload())
    control = _committed_sample_control_payload(manifest_payloads) if transport.rank == 0 else None
    max_chunks = _parse_committed_sample_control(transport.broadcast_receipt_payload(control))
    gathered_chunks: list[Mapping[str, object]] = []
    for chunk_index in range(max_chunks):
        round_payloads = transport.gather_bounded_receipt_payloads(
            local.collective_slot(chunk_index).to_payload()
        )
        if transport.rank == 0:
            gathered_chunks.extend(round_payloads)
    summary: AllRankCommittedSampleReceipt | None = None
    aggregation_error: BaseException | None = None
    if transport.rank == 0:
        try:
            summary = aggregate_committed_sample_digest_payloads(
                manifest_payloads,
                gathered_chunks,
            )
        except BaseException as error:
            aggregation_error = error
    envelope = (
        _committed_sample_summary_envelope(summary, aggregation_error)
        if transport.rank == 0
        else None
    )
    return _parse_committed_sample_summary_envelope(transport.broadcast_receipt_payload(envelope))


__all__ = [
    "ALL_RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA",
    "ALL_RANK_PLAN_RECEIPT_SCHEMA",
    "COMMITTED_SAMPLE_DIGEST_CHUNK_SCHEMA",
    "COMMITTED_SAMPLE_MANIFEST_SCHEMA",
    "DECLARED_PAYLOAD_SCOPE",
    "MAX_COMMITTED_SAMPLE_CHUNKS_PER_WINDOW",
    "MAX_COMMITTED_SAMPLE_COLLECTIVE_ENCODED_BYTES",
    "MAX_COMMITTED_SAMPLE_KEY_ENCODED_BYTES",
    "MAX_COMMITTED_SAMPLE_RECORDS_PER_CHUNK",
    "MAX_COMMITTED_SAMPLE_RECORDS_PER_WINDOW",
    "MAX_DISTRIBUTED_WORLD_SIZE",
    "RANK_COMMITTED_SAMPLE_RECEIPT_SCHEMA",
    "RANK_PLAN_RECEIPT_SCHEMA",
    "RUNTIME_UNIQUENESS_STATUS",
    "STRATEGY_TEARDOWN_RECEIPT_SCHEMA",
    "AllRankCommittedSampleReceipt",
    "AllRankTrainingPlanReceipt",
    "CommittedSampleDigestChunk",
    "CommittedSampleManifest",
    "DistributedReceiptTransport",
    "DistributedRunReceiptIdentity",
    "RankCommittedSampleReceipt",
    "RankTrainingPlanReceipt",
    "StrategySessionIdentity",
    "StrategyTeardownReceipt",
    "aggregate_committed_sample_digest_payloads",
    "aggregate_committed_sample_payloads",
    "aggregate_rank_plan_payloads",
    "collect_committed_sample_receipt",
    "collect_rank_plan_receipt",
]
