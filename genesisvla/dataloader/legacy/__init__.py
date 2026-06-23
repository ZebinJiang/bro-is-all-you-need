"""M2 legacy dataloader adapter。"""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any, cast

from genesisvla.core.compat import from_legacy_dict
from genesisvla.core.types import RawSample


class LegacyDataloaderAdapter:
    """把旧 dataloader 字典转换为 M1 RawSample 契约。"""

    _known_fields = frozenset(
        {
            "images",
            "language",
            "instruction",
            "task",
            "actions",
            "action",
            "state",
            "proprio",
            "observation.state",
            "metadata",
            "episode_id",
            "robot_tag",
        }
    )

    def __init__(
        self,
        *,
        robot_tag: str,
        action_dim: int | None = None,
        state_dim: int | None = None,
    ) -> None:
        if not robot_tag.strip():
            raise ValueError("robot_tag must not be empty")
        self.robot_tag = robot_tag
        self.action_dim = action_dim
        self.state_dim = state_dim

    def to_raw_sample(self, payload: Mapping[str, Any]) -> RawSample:
        """转换 legacy payload, 并把未知字段记录到 metadata。"""
        unsupported = {
            key: value for key, value in payload.items() if key not in self._known_fields
        }
        metadata = dict(cast(Mapping[str, Any], payload.get("metadata", {})))
        if unsupported:
            warnings.warn(
                f"unsupported legacy fields kept in metadata: {tuple(sorted(unsupported))}",
                UserWarning,
                stacklevel=2,
            )
            metadata["unsupported_fields"] = unsupported

        converted = dict(payload)
        converted["robot_tag"] = self.robot_tag
        converted["metadata"] = metadata
        sample = from_legacy_dict(converted, require_robot_tag=True)

        if self.action_dim is not None:
            if sample.actions is None or sample.actions.shape[-1] != self.action_dim:
                raise ValueError("legacy action dimension does not match action_dim")
        if self.state_dim is not None:
            if sample.state is None or sample.state.shape[-1] != self.state_dim:
                raise ValueError("legacy state dimension does not match state_dim")
        return sample


__all__ = ["LegacyDataloaderAdapter"]
