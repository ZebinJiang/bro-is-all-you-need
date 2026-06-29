"""AutoVLA 模型动物园注册表。"""

from __future__ import annotations

from autovla.core.registry import Registry
from autovla.models.contracts import ModelZooEntry
from autovla.models.gr00t_n1d6 import GR00T_N1D6_ENTRY

GR00T_SERIES_CANDIDATES = (
    "gr00t-n1d6",
    "gr00t-n1d6.1",
    "qwen-gr00t-bridge-reference",
)
PI_SERIES_CANDIDATES = (
    "pi0-roadmap",
    "pi0.5-roadmap",
    "qwen-pi-bridge-reference",
)


def build_model_zoo_registry() -> Registry[ModelZooEntry]:
    """构造急切的模型动物园注册表,不执行懒加载或导入重型运行时。"""
    registry: Registry[ModelZooEntry] = Registry("autovla-model-zoo")
    registry.register(GR00T_N1D6_ENTRY.model_registry_key, GR00T_N1D6_ENTRY)
    return registry


_MODEL_ZOO = build_model_zoo_registry()


def get_model_zoo_entry(model_registry_key: str) -> ModelZooEntry:
    """按模型注册键返回模型动物园元数据条目。"""
    return _MODEL_ZOO.get(model_registry_key)


def list_model_zoo_keys() -> tuple[str, ...]:
    """返回已注册模型键。"""
    return _MODEL_ZOO.names()


def list_model_family_candidates() -> dict[str, tuple[str, ...]]:
    """返回路线图候选族,仅供文档和 readiness manifest 使用。"""
    return {
        "gr00t": GR00T_SERIES_CANDIDATES,
        "pi": PI_SERIES_CANDIDATES,
    }
