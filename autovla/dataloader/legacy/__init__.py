"""M2 legacy dataloader adapter。"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from typing import Any, cast

from autovla.core.compat import from_legacy_dict
from autovla.core.types import RawSample


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
        required_modalities: Iterable[str] = (),
    ) -> None:
        if not robot_tag.strip():
            raise ValueError("robot_tag must not be empty")
        self.robot_tag = robot_tag
        self.action_dim = action_dim
        self.state_dim = state_dim
        self.required_modalities = tuple(required_modalities)

    def to_raw_sample(self, payload: Mapping[str, Any]) -> RawSample:
        """转换 legacy payload, 并把未知字段记录到 metadata。"""
        unsupported = {
            key: value for key, value in payload.items() if key not in self._known_fields
        }
        raw_metadata = payload.get("metadata")
        if raw_metadata is None:
            metadata: dict[str, Any] = {}
        elif isinstance(raw_metadata, Mapping):
            metadata = dict(cast(Mapping[str, Any], raw_metadata))
        else:
            raise TypeError("legacy metadata must be a mapping")
        legacy_robot_tag = payload.get("robot_tag", metadata.get("robot_tag"))
        if legacy_robot_tag:
            metadata["legacy_robot_tag"] = str(legacy_robot_tag)
        metadata["adapter_robot_tag"] = self.robot_tag
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
        sample = from_legacy_dict(
            converted,
            required_modalities=self.required_modalities,
            require_robot_tag=True,
        )

        if self.action_dim is not None:
            if sample.actions is None or sample.actions.shape[-1] != self.action_dim:
                raise ValueError("legacy action dimension does not match action_dim")
        if self.state_dim is not None:
            if sample.state is None or sample.state.shape[-1] != self.state_dim:
                raise ValueError("legacy state dimension does not match state_dim")
        return sample


__all__ = ["LegacyDataloaderAdapter"]
