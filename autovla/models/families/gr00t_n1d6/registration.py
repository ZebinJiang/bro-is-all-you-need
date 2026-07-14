"""GR00T N1.6.1 延迟注册元数据。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.core.registry import ImportStringFactory
from autovla.models.families.gr00t_n1d6.specification import (
    GR00T_N1D6_SPEC,
    Gr00tN1d6ModelSpec,
)


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Registration:
    """保存后续 Integration 写入模型注册表所需的轻量元数据。"""

    key: str
    aliases: tuple[str, ...]
    spec: Gr00tN1d6ModelSpec
    factory: ImportStringFactory[object]


def registration() -> Gr00tN1d6Registration:
    """返回不导入 torch/Transformers/GR00T runtime 的注册记录。"""
    return Gr00tN1d6Registration(
        key="gr00t_n1d6",
        aliases=("gr00t-n1d6", "gr00t_n1d6_metadata"),
        spec=GR00T_N1D6_SPEC,
        factory=ImportStringFactory(
            factory_path=GR00T_N1D6_SPEC.factory_path or "",
            optional_extra="model-gr00t-n1d6",
            required_modules=("torch", "transformers"),
            description="AutoVLA-native NVIDIA Isaac-GR00T N1.6.1 family factory",
            metadata={
                "family_key": "gr00t_n1d6",
                "local_files_only": True,
                "asset_key": "gr00t_n1d6",
                "implicit_download": False,
                "runtime_validation": "deferred",
            },
        ),
    )


__all__ = ["Gr00tN1d6Registration", "registration"]
