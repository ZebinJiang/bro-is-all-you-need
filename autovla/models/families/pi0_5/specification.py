"""Pi0.5 架构完整、运行时延后的规范定义。"""

from __future__ import annotations

from autovla.models.families.pi0.config import Pi0_5Config
from autovla.models.families.pi0.shared import build_pi_definition
from autovla.models.families.specification import ModelFamilyDefinition

PI0_5_SPEC = build_pi_definition(
    family_key="pi0_5",
    display_name="Pi0.5",
    config_type=Pi0_5Config,
    max_language_tokens=200,
    state_conditioning="discrete_state_in_language_tokens",
    normalization="r3_quantile_q01_q99",
    aliases=("pi05-roadmap", "pi05_metadata"),
)

Pi0_5ModelSpec = ModelFamilyDefinition

__all__ = ["PI0_5_SPEC", "Pi0_5ModelSpec"]
