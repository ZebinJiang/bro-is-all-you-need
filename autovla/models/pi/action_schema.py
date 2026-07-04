"""OpenPI / π family action schema metadata-only substrate。"""

from __future__ import annotations

from autovla.models.action_heads import ActionHeadKind
from autovla.models.embodiment import ModelFamilyActionContract


def build_pi_action_schema_table() -> tuple[dict[str, object], ...]:
    """返回 π family roadmap-only action schema 表格行。"""
    contracts = (
        ModelFamilyActionContract(
            family_key="pi0-roadmap",
            action_kind=ActionHeadKind.FLOW_MATCHING_CONTINUOUS.value,
            action_horizon="roadmap",
            action_dim="roadmap",
            normalization_policy="roadmap_metadata_only",
            runtime_status="runtime_not_loaded",
        ),
        ModelFamilyActionContract(
            family_key="pi0-fast-roadmap",
            action_kind=ActionHeadKind.AUTOREGRESSIVE_DISCRETE_TOKEN.value,
            action_horizon="roadmap",
            action_dim="token_vocab_roadmap",
            normalization_policy="roadmap_metadata_only",
            runtime_status="runtime_not_loaded",
        ),
        ModelFamilyActionContract(
            family_key="pi05-roadmap",
            action_kind=ActionHeadKind.FLOW_MATCHING_CONTINUOUS.value,
            action_horizon="roadmap",
            action_dim="roadmap",
            normalization_policy="roadmap_metadata_only",
            runtime_status="runtime_not_loaded",
        ),
    )
    return tuple(contract.to_table_row() for contract in contracts)
