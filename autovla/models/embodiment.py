"""Embodiment 和 modality schema substrate。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModalitySpec:
    """输入 modality metadata。"""

    name: str
    role: str
    status: str = "metadata_only"


@dataclass(frozen=True, slots=True)
class CameraViewSpec:
    """相机视角 metadata。"""

    name: str
    modality: str
    resolution: str


@dataclass(frozen=True, slots=True)
class StateFieldSpec:
    """状态字段 metadata。"""

    name: str
    state_dim: int
    units: str


@dataclass(frozen=True, slots=True)
class ActionFieldSpec:
    """动作字段 metadata。"""

    name: str
    action_dim: int
    units: str


@dataclass(frozen=True, slots=True)
class EmbodimentSpec:
    """Embodiment metadata-only 契约。"""

    embodiment_key: str
    display_name: str
    cameras: tuple[CameraViewSpec, ...]
    actions: tuple[ActionFieldSpec, ...]
    tags: tuple[str, ...]

    def to_table_row(self) -> dict[str, object]:
        """返回 embodiment 表格行。"""
        action_dim = sum(action.action_dim for action in self.actions)
        return {
            "action_dim": action_dim,
            "camera_count": len(self.cameras),
            "display_name": self.display_name,
            "embodiment_key": self.embodiment_key,
            "status": "metadata_only",
            "tags": ",".join(self.tags),
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyActionContract:
    """模型族 action contract metadata。"""

    family_key: str
    action_kind: str
    action_horizon: int | str
    action_dim: int | str
    normalization_policy: str
    runtime_status: str

    def to_table_row(self) -> dict[str, object]:
        """返回 action family schema 表格行。"""
        return {
            "action_dim": self.action_dim,
            "action_horizon": self.action_horizon,
            "action_kind": self.action_kind,
            "family_key": self.family_key,
            "normalization_policy": self.normalization_policy,
            "runtime_status": self.runtime_status,
        }
