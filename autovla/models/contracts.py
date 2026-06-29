"""AutoVLA 模型动物园的轻量元数据契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

SupportStatus: TypeAlias = Literal[
    "metadata_only",
    "skeleton_only",
    "planned",
    "unavailable_missing_assets",
]
AssetAvailability: TypeAlias = Literal["missing", "metadata_only", "available"]


class ModelAssetsUnavailableError(RuntimeError):
    """表示模型骨架缺少已治理的源码或 checkpoint 资产。"""


@dataclass(frozen=True, slots=True)
class ReleaseReference:
    """记录外部发布引用,仅作元数据使用。

    Args:
        label: 人类可读发布名称。
        url: 用户或 Manager 已确认存在的发布页 URL。
        tag: 发布标签。
        short_commit: 发布对应短提交号。
        notes: 对发布说明的短描述,不替代源码或许可证审查。
    """

    label: str
    url: str
    tag: str
    short_commit: str
    notes: str

    def __post_init__(self) -> None:
        """校验发布引用字段均为非空文本。"""
        _require_non_empty_str(self.label, "release_reference.label")
        _require_non_empty_str(self.url, "release_reference.url")
        _require_non_empty_str(self.tag, "release_reference.tag")
        _require_non_empty_str(self.short_commit, "release_reference.short_commit")
        _require_non_empty_str(self.notes, "release_reference.notes")

    def to_metadata(self) -> dict[str, str]:
        """返回 JSON 友好的发布引用元数据。"""
        return {
            "label": self.label,
            "url": self.url,
            "tag": self.tag,
            "short_commit": self.short_commit,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ModelAssetMetadata:
    """描述模型源码与 checkpoint 的治理状态。

    该结构只保存元数据,不探测路径、不下载文件、不读取 checkpoint。
    """

    source_reference_url: str | None = None
    source_revision: str | None = None
    source_checksum: str | None = None
    checkpoint_uri: str | None = None
    checkpoint_checksum: str | None = None
    license_status: str = "unknown"
    availability: AssetAvailability = "missing"

    def __post_init__(self) -> None:
        """校验可选文本字段在出现时不为空。"""
        _require_optional_str(self.source_reference_url, "asset.source_reference_url")
        _require_optional_str(self.source_revision, "asset.source_revision")
        _require_optional_str(self.source_checksum, "asset.source_checksum")
        _require_optional_str(self.checkpoint_uri, "asset.checkpoint_uri")
        _require_optional_str(self.checkpoint_checksum, "asset.checkpoint_checksum")
        _require_non_empty_str(self.license_status, "asset.license_status")
        if self.availability not in {"missing", "metadata_only", "available"}:
            raise ValueError("asset.availability must be missing, metadata_only, or available")

    def missing_runtime_requirements(self) -> tuple[str, ...]:
        """列出真实运行前必须补齐的源码与 checkpoint 字段。"""
        missing: list[str] = []
        if self.source_checksum is None:
            missing.append("source_checksum")
        if self.checkpoint_uri is None:
            missing.append("checkpoint_uri")
        if self.checkpoint_checksum is None:
            missing.append("checkpoint_checksum")
        if self.license_status == "unknown":
            missing.append("license_status")
        return tuple(missing)

    def has_runtime_assets(self) -> bool:
        """判断是否具备真实模型运行所需的最小治理资产。"""
        return self.availability == "available" and not self.missing_runtime_requirements()

    def to_metadata(self) -> dict[str, str | None]:
        """返回 JSON 友好的资产元数据,不触发任何 IO。"""
        return {
            "source_reference_url": self.source_reference_url,
            "source_revision": self.source_revision,
            "source_checksum": self.source_checksum,
            "checkpoint_uri": self.checkpoint_uri,
            "checkpoint_checksum": self.checkpoint_checksum,
            "license_status": self.license_status,
            "availability": self.availability,
        }


@dataclass(frozen=True, slots=True)
class ModelZooEntry:
    """AutoVLA 模型动物园中的单个元数据条目。"""

    model_registry_key: str
    display_name: str
    source_family: str
    release_reference: ReleaseReference
    native_chain_policy: str
    checkpoint_policy: str
    tokenizer_policy: str
    action_head_policy: str
    dataset_policy: str
    training_policy: str
    support_status: SupportStatus
    assets: ModelAssetMetadata
    candidate_series: tuple[str, ...]
    roadmap_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        """校验注册条目的稳定元数据字段。"""
        _require_non_empty_str(self.model_registry_key, "model_registry_key")
        _require_non_empty_str(self.display_name, "display_name")
        _require_non_empty_str(self.source_family, "source_family")
        for field_name in (
            "native_chain_policy",
            "checkpoint_policy",
            "tokenizer_policy",
            "action_head_policy",
            "dataset_policy",
            "training_policy",
        ):
            _require_non_empty_str(str(getattr(self, field_name)), field_name)
        if self.support_status not in {
            "metadata_only",
            "skeleton_only",
            "planned",
            "unavailable_missing_assets",
        }:
            raise ValueError("support_status is not recognized")
        _require_non_empty_tuple(self.candidate_series, "candidate_series")
        _require_non_empty_tuple(self.roadmap_tags, "roadmap_tags")

    def require_runtime_assets(self) -> None:
        """在缺少真实运行资产时 fail closed。"""
        if self.assets.has_runtime_assets():
            return
        missing = ", ".join(self.assets.missing_runtime_requirements())
        raise ModelAssetsUnavailableError(
            f"{self.model_registry_key} is metadata-only and cannot run without "
            f"governed source/checkpoint assets: {missing}"
        )

    def to_metadata(self) -> dict[str, object]:
        """返回 JSON 友好的模型动物园条目。"""
        return {
            "model_registry_key": self.model_registry_key,
            "display_name": self.display_name,
            "source_family": self.source_family,
            "release_reference": self.release_reference.to_metadata(),
            "native_chain_policy": self.native_chain_policy,
            "checkpoint_policy": self.checkpoint_policy,
            "tokenizer_policy": self.tokenizer_policy,
            "action_head_policy": self.action_head_policy,
            "dataset_policy": self.dataset_policy,
            "training_policy": self.training_policy,
            "support_status": self.support_status,
            "assets": self.assets.to_metadata(),
            "candidate_series": self.candidate_series,
            "roadmap_tags": self.roadmap_tags,
        }


def _require_non_empty_str(value: str, field: str) -> None:
    """校验必填字符串。"""
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _require_optional_str(value: str | None, field: str) -> None:
    """校验可选字符串在出现时非空。"""
    if value is not None and not value.strip():
        raise ValueError(f"{field} must not be empty when provided")


def _require_non_empty_tuple(values: tuple[str, ...], field: str) -> None:
    """校验候选列表至少包含一个非空字符串。"""
    if not values:
        raise ValueError(f"{field} must not be empty")
    for index, value in enumerate(values):
        _require_non_empty_str(value, f"{field}[{index}]")
