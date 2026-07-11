"""AutoVLA episode 窗口采样。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EpisodeWindow:
    """保存请求帧、边界钳制索引和严格 padding mask。"""

    indices: tuple[int, ...]
    padding_mask: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class EpisodeSampler:
    """按整数 delta 构造不会跨 episode 的确定性窗口。"""

    deltas: tuple[int, ...] = (0,)

    def __post_init__(self) -> None:
        """校验 delta 唯一并按声明顺序保留。"""
        if not self.deltas:
            raise ValueError("deltas must not be empty")
        if len(set(self.deltas)) != len(self.deltas):
            raise ValueError("deltas must not contain duplicates")

    def window(self, frame_index: int, *, episode_length: int) -> EpisodeWindow:
        """计算边界钳制窗口,mask 中 ``True`` 表示真实未钳制帧。"""
        if episode_length <= 0:
            raise ValueError("episode_length must be positive")
        if frame_index < 0 or frame_index >= episode_length:
            raise ValueError("frame_index must be inside episode")
        indices: list[int] = []
        mask: list[bool] = []
        for delta in self.deltas:
            requested = frame_index + delta
            clamped = min(max(requested, 0), episode_length - 1)
            indices.append(clamped)
            mask.append(requested == clamped)
        return EpisodeWindow(tuple(indices), tuple(mask))


__all__ = ["EpisodeSampler", "EpisodeWindow"]
