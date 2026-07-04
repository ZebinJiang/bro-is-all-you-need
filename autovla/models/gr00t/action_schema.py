"""GR00T action schema metadata-only substrate。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.action_heads import ActionHeadKind
from autovla.models.embodiment import ModelFamilyActionContract


@dataclass(frozen=True, slots=True)
class GR00TActionSchema:
    """GR00T family action schema, 不导入上游 runtime。"""

    family_key: str
    action_horizon: int
    action_dim: int
    modality_fields: tuple[str, ...]
    embodiment_tags: tuple[str, ...]
    status: tuple[str, ...]

    def to_table_row(self) -> dict[str, object]:
        """返回 action_family_schema_table 行。"""
        contract = ModelFamilyActionContract(
            family_key=self.family_key,
            action_kind=ActionHeadKind.DIFFUSION_CONTINUOUS.value,
            action_horizon=self.action_horizon,
            action_dim=self.action_dim,
            normalization_policy="metadata_or_statistics_future",
            runtime_status="runtime_not_loaded",
        )
        row = contract.to_table_row()
        row.update(
            {
                "embodiment_tags": ",".join(self.embodiment_tags),
                "modality_fields": ",".join(self.modality_fields),
                "schema_status": ",".join(self.status),
            }
        )
        return row


def build_gr00t_action_schema(
    *,
    action_horizon: int,
    action_dim: int,
    modality_fields: tuple[str, ...],
    embodiment_tags: tuple[str, ...],
) -> GR00TActionSchema:
    """构造 GR00T metadata-only action schema。"""
    return GR00TActionSchema(
        family_key="gr00t-roadmap",
        action_horizon=action_horizon,
        action_dim=action_dim,
        modality_fields=modality_fields,
        embodiment_tags=embodiment_tags,
        status=("metadata_only", "local_schema_probe_only", "runtime_not_loaded"),
    )


def build_default_gr00t_action_schema_table() -> tuple[dict[str, object], ...]:
    """返回默认 GR00T action schema 表格行。"""
    return (
        build_gr00t_action_schema(
            action_horizon=16,
            action_dim=7,
            modality_fields=("language", "image", "state"),
            embodiment_tags=("metadata_only",),
        ).to_table_row(),
    )
