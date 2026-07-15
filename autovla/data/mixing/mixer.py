"""AutoVLA 确定性数据集混合。"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import cast

from autovla.data.contracts import stable_fingerprint
from autovla.data.datasets.base import DatasetHandle
from autovla.data.sampling import PartitionContext
from autovla.data.types import TrainingSample


def _empty_counts() -> dict[str, int]:
    """返回类型明确的空计数映射。"""
    return {}


def _is_non_empty_text(value: object) -> bool:
    """在解码边界校验非空文本。"""
    return isinstance(value, str) and bool(value.strip())


def _is_finite_positive_number(value: object) -> bool:
    """拒绝 bool,并校验有限正数。"""
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0.0
    )


def _is_valid_weight_entry(name: object, value: object) -> bool:
    """校验未信任 schedule 映射中的名称和权重。"""
    return _is_non_empty_text(name) and _is_finite_positive_number(value)


class MixtureWeightPolicy(str, Enum):
    """声明数据集权重的解析规则。"""

    FIXED = "fixed"
    DATASET_SIZE = "dataset_size"
    TEMPERATURE = "temperature"
    SCHEDULED = "scheduled"


@dataclass(frozen=True, slots=True)
class MixtureSchedulePoint:
    """保存从指定 step 开始生效的组件原始权重。"""

    step: int
    weights: Mapping[str, float]

    def __post_init__(self) -> None:
        """校验 step、权重并冻结映射。"""
        if type(self.step) is not int or self.step < 0:
            raise ValueError("mixture schedule step must be non-negative")
        if not self.weights or any(
            not _is_valid_weight_entry(name, value) for name, value in self.weights.items()
        ):
            raise ValueError("mixture schedule weights must be finite and positive")
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))


@dataclass(frozen=True, slots=True)
class MixtureComponent:
    """描述一个数据集、规模、固定权重、上限和遥测身份。"""

    dataset: str
    source_fingerprint: str
    size: int | None = None
    weight: float = 1.0
    cap: int | None = None
    embodiment: str | None = None
    telemetry_label: str | None = None

    def __post_init__(self) -> None:
        """校验组件身份和采样边界。"""
        if not _is_non_empty_text(self.dataset) or not _is_non_empty_text(self.source_fingerprint):
            raise ValueError("mixture component identity must not be empty")
        if self.size is not None and (type(self.size) is not int or self.size <= 0):
            raise ValueError("mixture component size must be positive")
        if not _is_finite_positive_number(self.weight):
            raise ValueError("mixture component weight must be finite and positive")
        if self.cap is not None and (type(self.cap) is not int or self.cap <= 0):
            raise ValueError("mixture component cap must be positive")
        if self.embodiment is not None and not self.embodiment.strip():
            raise ValueError("mixture component embodiment must not be empty")
        if self.telemetry_label is not None and not self.telemetry_label.strip():
            raise ValueError("mixture telemetry label must not be empty")


@dataclass(frozen=True, slots=True)
class DatasetMixturePlan:
    """确定性、可序列化和可恢复的数据集混合计划。"""

    components: tuple[MixtureComponent, ...]
    policy: MixtureWeightPolicy = MixtureWeightPolicy.FIXED
    seed: int = 0
    temperature: float = 1.0
    replacement: bool = True
    finite_exhaustion: str = "renormalize"
    schedule: tuple[MixtureSchedulePoint, ...] = ()
    schema_version: str = "autovla.dataset_mixture_plan.v1"

    def __post_init__(self) -> None:
        """校验唯一组件、策略参数和完整 schedule。"""
        if self.schema_version != "autovla.dataset_mixture_plan.v1":
            raise ValueError("unsupported DatasetMixturePlan schema version")
        if not self.components:
            raise ValueError("mixture plan requires components")
        names = tuple(component.dataset for component in self.components)
        if len(set(names)) != len(names):
            raise ValueError("mixture component datasets must be unique")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("mixture seed must be non-negative")
        if not _is_finite_positive_number(self.temperature):
            raise ValueError("mixture temperature must be finite and positive")
        if type(self.replacement) is not bool:
            raise TypeError("mixture replacement must be bool")
        if self.finite_exhaustion not in {"stop", "renormalize", "cycle"}:
            raise ValueError("unsupported finite exhaustion policy")
        if self.policy is MixtureWeightPolicy.DATASET_SIZE and any(
            component.size is None for component in self.components
        ):
            raise ValueError("dataset_size mixture requires every component size")
        steps = tuple(point.step for point in self.schedule)
        if steps != tuple(sorted(set(steps))):
            raise ValueError("mixture schedule steps must be unique and ordered")
        if self.policy is MixtureWeightPolicy.SCHEDULED:
            if not self.schedule or self.schedule[0].step != 0:
                raise ValueError("scheduled mixture requires a step-zero schedule")
            expected = set(names)
            if any(set(point.weights) != expected for point in self.schedule):
                raise ValueError("every schedule point must name every dataset")

    def _raw_weights(self, step: int) -> dict[str, float]:
        """返回指定 step 的未归一化权重。"""
        if type(step) is not int or step < 0:
            raise ValueError("mixture step must be non-negative")
        if self.policy is MixtureWeightPolicy.SCHEDULED:
            selected = self.schedule[0]
            for point in self.schedule:
                if point.step > step:
                    break
                selected = point
            return dict(selected.weights)
        if self.policy is MixtureWeightPolicy.DATASET_SIZE:
            return {item.dataset: float(item.size or 0) for item in self.components}
        if self.policy is MixtureWeightPolicy.TEMPERATURE:
            exponent = 1.0 / self.temperature
            return {item.dataset: item.weight**exponent for item in self.components}
        return {item.dataset: item.weight for item in self.components}

    def resolved_weights(
        self,
        step: int,
        *,
        exhausted: Sequence[str] = (),
    ) -> Mapping[str, float]:
        """解析有效权重; 耗尽源按明确策略停止、循环或重归一化。"""
        raw = self._raw_weights(step)
        exhausted_set = set(exhausted)
        if exhausted_set - set(raw):
            raise ValueError("exhausted mixture dataset is unknown")
        if exhausted_set and self.finite_exhaustion == "stop":
            return MappingProxyType({name: 0.0 for name in raw})
        if self.finite_exhaustion == "renormalize":
            for name in exhausted_set:
                raw[name] = 0.0
        total = sum(raw.values())
        if total <= 0.0:
            raise ValueError("mixture has no effective source weight")
        return MappingProxyType({name: value / total for name, value in sorted(raw.items())})

    def select(
        self,
        *,
        step: int,
        global_position: int,
        rank: int,
        worker_id: int,
        exhausted: Sequence[str] = (),
        draw_counts: Mapping[str, int] | None = None,
    ) -> str:
        """用显式 rank/worker/全局位置产生可重放选择。"""
        if any(type(value) is not int for value in (step, global_position, rank, worker_id)):
            raise TypeError("mixture step and positions must be integers")
        if min(global_position, rank, worker_id) < 0:
            raise ValueError("mixture positions must be non-negative")
        counts = {} if draw_counts is None else dict(draw_counts)
        if any(
            name not in {item.dataset for item in self.components}
            or type(value) is not int
            or value < 0
            for name, value in counts.items()
        ):
            raise ValueError("mixture draw_counts must name known sources with non-negative ints")
        effective_exhausted = set(exhausted)
        for component in self.components:
            count = counts.get(component.dataset, 0)
            if component.cap is not None and count >= component.cap:
                effective_exhausted.add(component.dataset)
            if not self.replacement and component.size is not None and count >= component.size:
                effective_exhausted.add(component.dataset)
        weights = self.resolved_weights(step, exhausted=tuple(sorted(effective_exhausted)))
        payload = f"{self.fingerprint}:{step}:{global_position}:{rank}:{worker_id}".encode()
        value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / float(1 << 64)
        cumulative = 0.0
        for name, weight in weights.items():
            cumulative += weight
            if value < cumulative:
                return name
        return next(reversed(tuple(weights)))

    def to_dict(self) -> dict[str, object]:
        """返回稳定 JSON 安全表示。"""
        return {
            "schema_version": self.schema_version,
            "components": [
                {
                    "dataset": item.dataset,
                    "source_fingerprint": item.source_fingerprint,
                    "size": item.size,
                    "weight": item.weight,
                    "cap": item.cap,
                    "embodiment": item.embodiment,
                    "telemetry_label": item.telemetry_label,
                }
                for item in self.components
            ],
            "policy": self.policy.value,
            "seed": self.seed,
            "temperature": self.temperature,
            "replacement": self.replacement,
            "finite_exhaustion": self.finite_exhaustion,
            "schedule": [
                {"step": point.step, "weights": dict(sorted(point.weights.items()))}
                for point in self.schedule
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DatasetMixturePlan:
        """从严格 JSON 载荷恢复计划,并重新执行全部语义校验。"""
        expected = {
            "schema_version",
            "components",
            "policy",
            "seed",
            "temperature",
            "replacement",
            "finite_exhaustion",
            "schedule",
        }
        if set(payload) != expected:
            raise ValueError("mixture plan payload keys do not match schema")
        raw_components = payload["components"]
        raw_schedule = payload["schedule"]
        if not isinstance(raw_components, list) or not isinstance(raw_schedule, list):
            raise TypeError("mixture components and schedule must be lists")
        component_payloads = cast(list[object], raw_components)
        schedule_payloads = cast(list[object], raw_schedule)
        component_keys = {
            "dataset",
            "source_fingerprint",
            "size",
            "weight",
            "cap",
            "embodiment",
            "telemetry_label",
        }
        components: list[MixtureComponent] = []
        for item in component_payloads:
            if not isinstance(item, dict):
                raise ValueError("mixture component payload must be a mapping")
            item_payload = cast(dict[str, object], item)
            if set(item_payload) != component_keys:
                raise ValueError("mixture component payload keys do not match schema")
            components.append(
                MixtureComponent(
                    dataset=cast(str, item_payload["dataset"]),
                    source_fingerprint=cast(str, item_payload["source_fingerprint"]),
                    size=cast(int | None, item_payload["size"]),
                    weight=cast(float, item_payload["weight"]),
                    cap=cast(int | None, item_payload["cap"]),
                    embodiment=cast(str | None, item_payload["embodiment"]),
                    telemetry_label=cast(str | None, item_payload["telemetry_label"]),
                )
            )
        schedule: list[MixtureSchedulePoint] = []
        for item in schedule_payloads:
            if not isinstance(item, dict):
                raise ValueError("mixture schedule payload must be a mapping")
            item_payload = cast(dict[str, object], item)
            if set(item_payload) != {"step", "weights"}:
                raise ValueError("mixture schedule payload keys do not match schema")
            schedule.append(
                MixtureSchedulePoint(
                    step=cast(int, item_payload["step"]),
                    weights=cast(Mapping[str, float], item_payload["weights"]),
                )
            )
        return cls(
            components=tuple(components),
            policy=MixtureWeightPolicy(cast(str, payload["policy"])),
            seed=cast(int, payload["seed"]),
            temperature=cast(float, payload["temperature"]),
            replacement=cast(bool, payload["replacement"]),
            finite_exhaustion=cast(str, payload["finite_exhaustion"]),
            schedule=tuple(schedule),
            schema_version=cast(str, payload["schema_version"]),
        )

    @property
    def fingerprint(self) -> str:
        """返回包含全部混合语义的稳定指纹。"""
        return stable_fingerprint(self.to_dict())


@dataclass(frozen=True, slots=True)
class DatasetMixtureState:
    """保存下一次抽样位置、源游标和已交付计数。"""

    plan_fingerprint: str
    next_global_position: int
    source_cursors: Mapping[str, int] = field(default_factory=_empty_counts)
    draw_counts: Mapping[str, int] = field(default_factory=_empty_counts)

    def __post_init__(self) -> None:
        """校验非负状态并冻结映射。"""
        if (
            not self.plan_fingerprint.strip()
            or type(self.next_global_position) is not int
            or self.next_global_position < 0
        ):
            raise ValueError("invalid mixture state identity or position")
        for values in (self.source_cursors, self.draw_counts):
            if any(
                not name.strip() or type(value) is not int or value < 0
                for name, value in values.items()
            ):
                raise ValueError("mixture state entries must be non-negative")
        object.__setattr__(self, "source_cursors", MappingProxyType(dict(self.source_cursors)))
        object.__setattr__(self, "draw_counts", MappingProxyType(dict(self.draw_counts)))

    def to_dict(self) -> dict[str, object]:
        """返回检查点安全载荷。"""
        return {
            "plan_fingerprint": self.plan_fingerprint,
            "next_global_position": self.next_global_position,
            "source_cursors": dict(sorted(self.source_cursors.items())),
            "draw_counts": dict(sorted(self.draw_counts.items())),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DatasetMixtureState:
        """从严格检查点载荷恢复混合状态。"""
        expected = {"plan_fingerprint", "next_global_position", "source_cursors", "draw_counts"}
        if set(payload) != expected:
            raise ValueError("mixture state payload keys do not match schema")
        return cls(
            plan_fingerprint=cast(str, payload["plan_fingerprint"]),
            next_global_position=cast(int, payload["next_global_position"]),
            source_cursors=cast(Mapping[str, int], payload["source_cursors"]),
            draw_counts=cast(Mapping[str, int], payload["draw_counts"]),
        )


@dataclass(frozen=True, slots=True)
class WeightedDataset:
    """绑定已打开数据集及其正权重。"""

    dataset: DatasetHandle
    weight: float

    def __post_init__(self) -> None:
        """校验权重和非空数据集。"""
        if self.weight <= 0.0:
            raise ValueError("dataset weight must be positive")
        if len(self.dataset) <= 0:
            raise ValueError("mixed datasets must not be empty")


class DatasetMixer:
    """按 seed/epoch/全局位置确定性选择数据集和样本。"""

    def __init__(self, datasets: Sequence[WeightedDataset], *, seed: int) -> None:
        """拥有数据集序列并初始化独立局部游标。"""
        if not datasets:
            raise ValueError("datasets must not be empty")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        names = tuple(item.dataset.name for item in datasets)
        if len(set(names)) != len(names):
            raise ValueError("dataset names must be unique")
        self._datasets = tuple(datasets)
        self._seed = seed
        self._cursors: dict[str, int] = {name: 0 for name in names}
        total = sum(item.weight for item in datasets)
        cumulative = 0.0
        thresholds: list[float] = []
        for item in datasets:
            cumulative += item.weight / total
            thresholds.append(cumulative)
        thresholds[-1] = 1.0
        self._thresholds = tuple(thresholds)

    @property
    def datasets(self) -> tuple[WeightedDataset, ...]:
        """返回注册顺序稳定的加权数据集。"""
        return self._datasets

    def _choice(self, *, epoch: int, global_position: int) -> int:
        """用稳定摘要生成 ``[0,1)`` 选择值。"""
        payload = f"{self._seed}:{epoch}:{global_position}".encode("ascii")
        integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        value = integer / float(1 << 64)
        for index, threshold in enumerate(self._thresholds):
            if value < threshold:
                return index
        return len(self._thresholds) - 1

    def select(self, *, epoch: int, global_position: int) -> WeightedDataset:
        """按稳定位置选择加权数据集,但不推进任何读取游标。"""

        if epoch < 0 or global_position < 0:
            raise ValueError("epoch and global_position must be non-negative")
        return self._datasets[self._choice(epoch=epoch, global_position=global_position)]

    def read(
        self,
        local_position: int,
        *,
        epoch: int,
        partition: PartitionContext,
    ) -> TrainingSample:
        """选择一个数据集并从其循环局部游标读取样本。"""
        if epoch < 0:
            raise ValueError("epoch must be non-negative")
        global_position = partition.global_position(local_position)
        selected = self.select(epoch=epoch, global_position=global_position)
        name = selected.dataset.name
        cursor = self._cursors[name]
        self._cursors[name] = cursor + 1
        dataset_index = partition.global_position(cursor) % len(selected.dataset)
        return selected.dataset.read(dataset_index)

    def cursor_state(self) -> Mapping[str, int]:
        """返回可进入检查点元数据的数据集游标副本。"""
        return dict(self._cursors)

    def restore_cursors(self, state: Mapping[str, int]) -> None:
        """严格恢复所有数据集游标。"""
        if set(state) != set(self._cursors):
            raise ValueError("cursor state dataset names do not match mixer")
        for name, value in state.items():
            if value < 0:
                raise ValueError(f"cursor for {name!r} must be non-negative")
        self._cursors = dict(state)


__all__ = [
    "DatasetMixer",
    "DatasetMixturePlan",
    "DatasetMixtureState",
    "MixtureComponent",
    "MixtureSchedulePoint",
    "MixtureWeightPolicy",
    "WeightedDataset",
]
