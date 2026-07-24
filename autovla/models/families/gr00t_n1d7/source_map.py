"""N1.7 固定上游来源、复用决策与风险映射。"""

from types import MappingProxyType

from autovla.models.families.gr00t_n1d7.config import (
    GR00T_N1D7_CHECKPOINT_REVISION,
    NVIDIA_GR00T_SOURCE_REVISION,
)

SOURCE_MAP = MappingProxyType(
    {
        "code": {
            "repository": "https://github.com/NVIDIA/Isaac-GR00T",
            "revision": NVIDIA_GR00T_SOURCE_REVISION,
            "license": "Apache-2.0",
            "reuse": "selective_family_private_adaptation",
            "copied_code": True,
            "paths_and_blobs": (
                (
                    "gr00t/model/modules/dit.py",
                    "4bb9994d3c89a738a830c5af927b1cd24d2854a5",
                ),
                (
                    "gr00t/model/modules/embodiment_conditioned_mlp.py",
                    "504785d57cc33a87613dd775cc415cc88574c2ee",
                ),
                (
                    "gr00t/model/gr00t_n1d7/gr00t_n1d7.py",
                    "346b597a4b9a115a9a5b1053621f47f07833da09",
                ),
            ),
            "runtime_dependency": "diffusers==0.35.1",
            "shared_dependency_change": "proposal_required_outside_family_write_scope",
            "shared_notice_change": "proposal_required_outside_family_write_scope",
        },
        "checkpoint": {
            "identifier": "nvidia/GR00T-N1.7-3B",
            "revision": GR00T_N1D7_CHECKPOINT_REVISION,
            "license": "conflicting_packaged_license_and_model_card_fail_closed",
        },
        "backbone": {
            "identifier": "nvidia/Cosmos-Reason2-2B",
            "access": "gated_receipt_and_immutable_revision_required",
        },
        "upstream_runtime": {
            "trainer": "rejected",
            "fsdp_or_fsdp2": "unproven_and_not_claimed",
            "trust_remote_code": False,
            "implicit_network": False,
        },
        "backend_decision": "NO_BACKEND_WINNER",
    }
)

__all__ = ["SOURCE_MAP"]
