# ruff: noqa: RUF001, RUF002
"""N1.7 固定上游来源、适配路径与独立资产门禁。

三个源码收据对应保留 NVIDIA 版权与 Apache-2.0 header 的本地适配文件。
checkpoint 与 Cosmos 条款不属于代码许可，继续独立失败关闭。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from autovla.models.families.gr00t_n1d7.config import (
    GR00T_N1D7_CHECKPOINT_REVISION,
    NVIDIA_GR00T_SOURCE_REVISION,
)

NVIDIA_GR00T_REPOSITORY = "https://github.com/NVIDIA/Isaac-GR00T"
NVIDIA_GR00T_LICENSE = "Apache-2.0"


@dataclass(frozen=True, slots=True)
class Gr00tN1d7SourceReceipt:
    """绑定一个 NVIDIA 上游 blob、对应本地适配文件与修改边界。"""

    upstream_path: str
    git_blob: str
    local_path: str
    reuse_class: str
    local_modifications: str
    dependency_impact: str

    def __post_init__(self) -> None:
        """拒绝空字段、短 blob 或非适配来源分类。"""

        text_values = (
            self.upstream_path,
            self.local_path,
            self.reuse_class,
            self.local_modifications,
            self.dependency_impact,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("N1.7 source receipt fields must not be empty")
        if len(self.git_blob) != 40 or any(
            character not in "0123456789abcdef" for character in self.git_blob
        ):
            raise ValueError("N1.7 source receipt requires a complete Git blob SHA-1")
        if self.reuse_class != "adapted":
            raise ValueError("N1.7 attributed source receipts must remain adapted")

    def to_json_dict(self) -> dict[str, object]:
        """返回 canonical 文档使用的稳定来源映射。"""

        return {
            "upstream_path": self.upstream_path,
            "git_blob": self.git_blob,
            "local_paths": [self.local_path],
            "reuse_class": self.reuse_class,
            "local_modifications": self.local_modifications,
            "dependency_impact": self.dependency_impact,
        }


GR00T_N1D7_SOURCE_RECEIPTS = (
    Gr00tN1d7SourceReceipt(
        upstream_path="gr00t/model/modules/dit.py",
        git_blob="4bb9994d3c89a738a830c5af927b1cd24d2854a5",
        local_path="autovla/models/families/gr00t_n1d7/_nvidia/dit.py",
        reuse_class="adapted",
        local_modifications=(
            "移除 ModelMixin/ConfigMixin 副作用，增加 Python 3.10 类型和失败关闭校验；"
            "保留官方参数模块、名称、mask、位置流和 timestep 条件张量流。"
        ),
        dependency_impact="复用 family runtime 已要求的 diffusers==0.35.1；本修复不改依赖。",
    ),
    Gr00tN1d7SourceReceipt(
        upstream_path="gr00t/model/modules/embodiment_conditioned_mlp.py",
        git_blob="504785d57cc33a87613dd775cc415cc88574c2ee",
        local_path="autovla/models/families/gr00t_n1d7/_nvidia/embodiment.py",
        reuse_class="adapted",
        local_modifications="增加 Python 3.10 类型、中文文档和严格 shape 校验。",
        dependency_impact="仅使用 family runtime 的 PyTorch；本修复不改依赖。",
    ),
    Gr00tN1d7SourceReceipt(
        upstream_path="gr00t/model/gr00t_n1d7/gr00t_n1d7.py",
        git_blob="346b597a4b9a115a9a5b1053621f47f07833da09",
        local_path="autovla/models/families/gr00t_n1d7/action_head.py",
        reuse_class="adapted",
        local_modifications=(
            "增加 AutoVLA 类型化输出、共享 flow schedule、确定性 hook、中文文档和"
            "运行门禁下的 namespace 限制配置。"
        ),
        dependency_impact="复用 family runtime 的 PyTorch 与现有共享 flow 合同；本修复不改依赖。",
    ),
)

SOURCE_MAP = MappingProxyType(
    {
        "code": {
            "repository": NVIDIA_GR00T_REPOSITORY,
            "revision": NVIDIA_GR00T_SOURCE_REVISION,
            "copyright": "Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.",
            "license": NVIDIA_GR00T_LICENSE,
            "reuse": "adapted",
            "copied_or_adapted_code": True,
            "verbatim_copy": False,
            "source_to_local": tuple(
                receipt.to_json_dict() for receipt in GR00T_N1D7_SOURCE_RECEIPTS
            ),
            "runtime_dependency": "diffusers==0.35.1",
            "dependency_change": "none",
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

__all__ = [
    "GR00T_N1D7_SOURCE_RECEIPTS",
    "NVIDIA_GR00T_LICENSE",
    "NVIDIA_GR00T_REPOSITORY",
    "SOURCE_MAP",
    "Gr00tN1d7SourceReceipt",
]
