"""AutoVLA 确定性批平衡。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from autovla.data.contracts import stable_fingerprint


def _empty_counts() -> dict[str, int]:
    """返回类型明确的空计数映射。"""
    return {}


def _is_positive_number(value: object) -> bool:
    """在解码边界拒绝 bool,并接受正数。"""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value > 0.0


def _is_non_negative_count_entry(name: object, value: object) -> bool:
    """校验未信任映射条目的名称和精确整数计数。"""
    return isinstance(name, str) and bool(name.strip()) and type(value) is int and value >= 0


@dataclass(frozen=True, slots=True)
class BalanceGroup:
    """描述一个批平衡组和正权重。"""

    name: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        """校验组名和权重。"""
        if not self.name.strip():
            raise ValueError("balance group name must not be empty")
        if not _is_positive_number(self.weight):
            raise ValueError("balance group weight must be positive")


class BatchBalancer:
    """使用最大余数法生成稳定批内组配额。"""

    def __init__(self, groups: Sequence[BalanceGroup]) -> None:
        """保存名称唯一的平衡组。"""
        if not groups:
            raise ValueError("groups must not be empty")
        names = tuple(group.name for group in groups)
        if len(set(names)) != len(names):
            raise ValueError("balance group names must be unique")
        self._groups = tuple(groups)

    def quotas(self, batch_size: int, *, batch_index: int = 0) -> Mapping[str, int]:
        """按权重计算总和精确等于批大小的确定性配额。"""
        if type(batch_size) is not int or type(batch_index) is not int:
            raise TypeError("batch size and index must be integers")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if batch_index < 0:
            raise ValueError("batch_index must be non-negative")
        total = sum(group.weight for group in self._groups)
        raw = [batch_size * group.weight / total for group in self._groups]
        quotas = [int(value) for value in raw]
        remaining = batch_size - sum(quotas)
        order = sorted(
            range(len(self._groups)),
            key=lambda index: (
                -(raw[index] - quotas[index]),
                (index - batch_index) % len(self._groups),
            ),
        )
        for index in order[:remaining]:
            quotas[index] += 1
        return {group.name: quotas[index] for index, group in enumerate(self._groups)}

    def plan(self, batch_size: int, *, batch_index: int = 0) -> tuple[str, ...]:
        """把配额展开为轮转后的批内组顺序。"""
        quotas = dict(self.quotas(batch_size, batch_index=batch_index))
        names = tuple(group.name for group in self._groups)
        output: list[str] = []
        offset = batch_index % len(names)
        while len(output) < batch_size:
            for relative in range(len(names)):
                name = names[(offset + relative) % len(names)]
                if quotas[name] > 0:
                    output.append(name)
                    quotas[name] -= 1
        return tuple(output)


@dataclass(frozen=True, slots=True)
class BatchCompositionPolicy:
    """描述与源抽样相互独立的批内 dataset/embodiment 约束。"""

    dataset_targets: Mapping[str, int] = field(default_factory=_empty_counts)
    embodiment_targets: Mapping[str, int] = field(default_factory=_empty_counts)
    minimum_contribution: Mapping[str, int] = field(default_factory=_empty_counts)
    maximum_contribution: Mapping[str, int] = field(default_factory=_empty_counts)
    exhaustion_fallback: str = "redistribute"
    distributed_consistency: str = "global_batch_index"
    drop_last: bool = True
    accumulation_steps: int = 1
    schema_version: str = "autovla.batch_composition_policy.v1"

    def __post_init__(self) -> None:
        """校验配额、上下界和分布式一致性策略。"""
        if self.schema_version != "autovla.batch_composition_policy.v1":
            raise ValueError("unsupported BatchCompositionPolicy schema version")
        if not self.dataset_targets and not self.embodiment_targets:
            raise ValueError("batch composition requires dataset or embodiment targets")
        for mapping in (
            self.dataset_targets,
            self.embodiment_targets,
            self.minimum_contribution,
            self.maximum_contribution,
        ):
            if any(
                not _is_non_negative_count_entry(name, value) for name, value in mapping.items()
            ):
                raise ValueError("batch composition counts must be non-negative")
        if self.exhaustion_fallback not in {"error", "drop_batch", "redistribute"}:
            raise ValueError("unsupported batch exhaustion fallback")
        if self.distributed_consistency != "global_batch_index":
            raise ValueError("batch composition must use global_batch_index consistency")
        if type(self.drop_last) is not bool:
            raise TypeError("batch composition drop_last must be bool")
        if type(self.accumulation_steps) is not int or self.accumulation_steps <= 0:
            raise ValueError("accumulation_steps must be positive")
        for name in set(self.minimum_contribution) & set(self.maximum_contribution):
            if self.minimum_contribution[name] > self.maximum_contribution[name]:
                raise ValueError(f"minimum contribution exceeds maximum for {name!r}")
        object.__setattr__(self, "dataset_targets", MappingProxyType(dict(self.dataset_targets)))
        object.__setattr__(
            self, "embodiment_targets", MappingProxyType(dict(self.embodiment_targets))
        )
        object.__setattr__(
            self, "minimum_contribution", MappingProxyType(dict(self.minimum_contribution))
        )
        object.__setattr__(
            self, "maximum_contribution", MappingProxyType(dict(self.maximum_contribution))
        )

    def quotas(self, batch_size: int, *, global_batch_index: int) -> Mapping[str, int]:
        """按显式目标和上下界解析稳定批配额。"""
        if type(batch_size) is not int or type(global_batch_index) is not int:
            raise TypeError("batch size and index must be integers")
        if batch_size <= 0 or global_batch_index < 0:
            raise ValueError("batch size must be positive and index non-negative")
        targets = self.dataset_targets or self.embodiment_targets
        total = sum(targets.values())
        if total <= 0:
            raise ValueError("batch composition targets must have positive total")
        weighted = tuple(BalanceGroup(name, float(value)) for name, value in targets.items())
        quotas = dict(BatchBalancer(weighted).quotas(batch_size, batch_index=global_batch_index))
        for name, minimum in self.minimum_contribution.items():
            if name in quotas:
                quotas[name] = max(quotas[name], minimum)
        for name, maximum in self.maximum_contribution.items():
            if name in quotas:
                quotas[name] = min(quotas[name], maximum)
        difference = batch_size - sum(quotas.values())
        names = tuple(sorted(quotas))
        direction = 1 if difference > 0 else -1
        while difference:
            changed = False
            for offset in range(len(names)):
                name = names[(global_batch_index + offset) % len(names)]
                candidate = quotas[name] + direction
                minimum = self.minimum_contribution.get(name, 0)
                maximum = self.maximum_contribution.get(name, batch_size)
                if minimum <= candidate <= maximum:
                    quotas[name] = candidate
                    difference -= direction
                    changed = True
                    if difference == 0:
                        break
            if not changed:
                raise ValueError("batch composition bounds cannot satisfy batch size")
        return MappingProxyType(dict(sorted(quotas.items())))

    def resolve_available(
        self,
        batch_size: int,
        *,
        global_batch_index: int,
        exhausted: Sequence[str] = (),
    ) -> Mapping[str, int] | None:
        """按显式 fallback 处理耗尽组; ``None`` 表示丢弃该批。"""
        targets = self.dataset_targets or self.embodiment_targets
        exhausted_set = set(exhausted)
        if exhausted_set - set(targets):
            raise ValueError("exhausted batch group is unknown")
        if not exhausted_set:
            return self.quotas(batch_size, global_batch_index=global_batch_index)
        if self.exhaustion_fallback == "error":
            raise RuntimeError("batch composition source exhausted")
        if self.exhaustion_fallback == "drop_batch":
            return None
        available = {name: value for name, value in targets.items() if name not in exhausted_set}
        if not available:
            raise RuntimeError("all batch composition sources are exhausted")
        policy = BatchCompositionPolicy(
            dataset_targets=available if self.dataset_targets else {},
            embodiment_targets=available if self.embodiment_targets else {},
            minimum_contribution={
                name: value
                for name, value in self.minimum_contribution.items()
                if name in available
            },
            maximum_contribution={
                name: value
                for name, value in self.maximum_contribution.items()
                if name in available
            },
            exhaustion_fallback=self.exhaustion_fallback,
            distributed_consistency=self.distributed_consistency,
            drop_last=self.drop_last,
            accumulation_steps=self.accumulation_steps,
        )
        return policy.quotas(batch_size, global_batch_index=global_batch_index)

    def provenance(
        self, *, global_batch_index: int, quotas: Mapping[str, int]
    ) -> Mapping[str, object]:
        """生成 collator 可写入批 provenance 的稳定身份。"""
        if type(global_batch_index) is not int or global_batch_index < 0:
            raise ValueError("global batch index must be a non-negative integer")
        if any(
            not name.strip() or type(value) is not int or value < 0
            for name, value in quotas.items()
        ):
            raise ValueError("batch provenance quotas must be non-negative integers")
        return MappingProxyType(
            {
                "batch_composition_policy_fingerprint": self.fingerprint,
                "global_batch_index": global_batch_index,
                "quotas": dict(sorted(quotas.items())),
            }
        )

    def to_dict(self) -> dict[str, object]:
        """返回稳定可检查点表示。"""
        return {
            "schema_version": self.schema_version,
            "dataset_targets": dict(sorted(self.dataset_targets.items())),
            "embodiment_targets": dict(sorted(self.embodiment_targets.items())),
            "minimum_contribution": dict(sorted(self.minimum_contribution.items())),
            "maximum_contribution": dict(sorted(self.maximum_contribution.items())),
            "exhaustion_fallback": self.exhaustion_fallback,
            "distributed_consistency": self.distributed_consistency,
            "drop_last": self.drop_last,
            "accumulation_steps": self.accumulation_steps,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BatchCompositionPolicy:
        """从严格 JSON 载荷恢复批组成策略。"""
        expected = {
            "schema_version",
            "dataset_targets",
            "embodiment_targets",
            "minimum_contribution",
            "maximum_contribution",
            "exhaustion_fallback",
            "distributed_consistency",
            "drop_last",
            "accumulation_steps",
        }
        if set(payload) != expected:
            raise ValueError("batch policy payload keys do not match schema")
        return cls(
            dataset_targets=cast(Mapping[str, int], payload["dataset_targets"]),
            embodiment_targets=cast(Mapping[str, int], payload["embodiment_targets"]),
            minimum_contribution=cast(Mapping[str, int], payload["minimum_contribution"]),
            maximum_contribution=cast(Mapping[str, int], payload["maximum_contribution"]),
            exhaustion_fallback=cast(str, payload["exhaustion_fallback"]),
            distributed_consistency=cast(str, payload["distributed_consistency"]),
            drop_last=cast(bool, payload["drop_last"]),
            accumulation_steps=cast(int, payload["accumulation_steps"]),
            schema_version=cast(str, payload["schema_version"]),
        )

    @property
    def fingerprint(self) -> str:
        """返回批组成语义身份。"""
        return stable_fingerprint(self.to_dict())


@dataclass(frozen=True, slots=True)
class BatchCompositionState:
    """保存下一批索引及按来源提交的样本计数。"""

    policy_fingerprint: str
    next_global_batch_index: int
    committed_samples: Mapping[str, int] = field(default_factory=_empty_counts)

    def __post_init__(self) -> None:
        """校验并冻结检查点状态。"""
        if (
            not self.policy_fingerprint.strip()
            or type(self.next_global_batch_index) is not int
            or self.next_global_batch_index < 0
        ):
            raise ValueError("invalid batch composition state")
        if any(
            not name.strip() or type(value) is not int or value < 0
            for name, value in self.committed_samples.items()
        ):
            raise ValueError("committed sample counts must be non-negative")
        object.__setattr__(
            self,
            "committed_samples",
            MappingProxyType(dict(self.committed_samples)),
        )

    def to_dict(self) -> dict[str, object]:
        """返回检查点安全载荷。"""
        return {
            "policy_fingerprint": self.policy_fingerprint,
            "next_global_batch_index": self.next_global_batch_index,
            "committed_samples": dict(sorted(self.committed_samples.items())),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BatchCompositionState:
        """从严格检查点载荷恢复批组成状态。"""
        expected = {"policy_fingerprint", "next_global_batch_index", "committed_samples"}
        if set(payload) != expected:
            raise ValueError("batch state payload keys do not match schema")
        return cls(
            policy_fingerprint=cast(str, payload["policy_fingerprint"]),
            next_global_batch_index=cast(int, payload["next_global_batch_index"]),
            committed_samples=cast(Mapping[str, int], payload["committed_samples"]),
        )


__all__ = [
    "BalanceGroup",
    "BatchBalancer",
    "BatchCompositionPolicy",
    "BatchCompositionState",
]
