"""Pi0 架构完整、运行时延后的规范定义。"""

from __future__ import annotations

from autovla.models.families.pi0.config import Pi0Config
from autovla.models.families.pi0.shared import build_pi_definition
from autovla.models.families.specification import ModelFamilyDefinition

PI0_SPEC = build_pi_definition(
    family_key="pi0",
    display_name="Pi0",
    config_type=Pi0Config,
    max_language_tokens=48,
    state_conditioning="continuous_state_suffix_token",
    normalization="r3_mean_std_zscore",
    aliases=("pi0-roadmap", "pi0_metadata"),
)

Pi0ModelSpec = ModelFamilyDefinition

__all__ = ["PI0_SPEC", "Pi0ModelSpec"]
