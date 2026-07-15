"""Pi0-FAST 架构完整、运行时延后的规范定义。"""

from __future__ import annotations

from autovla.models.families.pi0.config import Pi0FastConfig
from autovla.models.families.pi0.shared import build_pi_definition
from autovla.models.families.specification import ModelFamilyDefinition

PI0_FAST_SPEC = build_pi_definition(
    family_key="pi0_fast",
    display_name="Pi0-FAST",
    config_type=Pi0FastConfig,
    max_language_tokens=48,
    state_conditioning="continuous_state_in_fast_token_prefix",
    normalization="r3_quantile_q01_q99",
    aliases=("pi0-fast-roadmap",),
)

Pi0FastModelSpec = ModelFamilyDefinition

__all__ = ["PI0_FAST_SPEC", "Pi0FastModelSpec"]
