"""AutoVLA 确定性批平衡。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BalanceGroup:
    """描述一个批平衡组和正权重。"""

    name: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        """校验组名和权重。"""
        if not self.name.strip():
            raise ValueError("balance group name must not be empty")
        if self.weight <= 0.0:
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


__all__ = ["BalanceGroup", "BatchBalancer"]
