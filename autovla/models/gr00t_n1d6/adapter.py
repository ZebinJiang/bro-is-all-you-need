"""GR00T N1.6/N1.6.1 的元数据-only 适配器骨架。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.core.types import ActionChunk, FrameworkOutput, ModelInput
from autovla.models.contracts import (
    ModelAssetMetadata,
    ModelAssetsUnavailableError,
    ModelZooEntry,
    ReleaseReference,
)

GR00T_N1D6_RELEASE_REFERENCE = ReleaseReference(
    label="NVIDIA Isaac-GR00T N1.6.1",
    url="https://github.com/NVIDIA/Isaac-GR00T/releases/tag/n1.6.1-release",
    tag="n1.6.1-release",
    short_commit="5dc80c4",
    notes="Manager-confirmed release metadata only; no source or weight vendoring.",
)

GR00T_N1D6_ENTRY = ModelZooEntry(
    model_registry_key="gr00t-n1d6",
    display_name="GR00T N1.6/N1.6.1 metadata skeleton",
    source_family="GR00T",
    release_reference=GR00T_N1D6_RELEASE_REFERENCE,
    native_chain_policy=(
        "AutoVLA-native adapter skeleton only; no StarVLA compatibility shim and no "
        "heavy GR00T runtime import."
    ),
    checkpoint_policy=(
        "Checkpoint metadata must be explicitly provided with checksum; missing assets "
        "fail closed and never trigger download or cache probing."
    ),
    tokenizer_policy="No tokenizer construction, lookup, from_pretrained call, or download.",
    action_head_policy=(
        "Action-head compatibility is roadmap metadata only until a later Model task "
        "validates shapes, masks, and loss semantics."
    ),
    dataset_policy=(
        "May reference Data-owned DatasetArtifact metadata by fingerprint only; no "
        "dataset row, media, or parquet loading."
    ),
    training_policy=(
        "No training, optimizer, inference, GPU, CUDA, Slurm, HF, W&B, or endpoint use."
    ),
    support_status="unavailable_missing_assets",
    assets=ModelAssetMetadata(
        source_reference_url=GR00T_N1D6_RELEASE_REFERENCE.url,
        source_revision=GR00T_N1D6_RELEASE_REFERENCE.short_commit,
        source_checksum=None,
        checkpoint_uri=None,
        checkpoint_checksum=None,
        license_status="unknown",
        availability="missing",
    ),
    candidate_series=("gr00t-n1d6", "gr00t-n1d6.1", "gr00t-roadmap"),
    roadmap_tags=("gr00t-series", "native-adapter", "metadata-only"),
)


@dataclass(frozen=True, slots=True)
class Gr00tN1D6AdapterSkeleton:
    """GR00T N1.6/N1.6.1 的轻量适配器骨架。

    该类只暴露元数据和 fail-closed 行为,不构造真实模型、tokenizer、checkpoint
    reader、动作头或训练组件。
    """

    entry: ModelZooEntry = GR00T_N1D6_ENTRY

    @property
    def model_registry_key(self) -> str:
        """返回稳定模型注册键。"""
        return self.entry.model_registry_key

    def metadata(self) -> dict[str, object]:
        """返回模型动物园条目的 JSON 友好元数据。"""
        return self.entry.to_metadata()

    def require_runtime_assets(self) -> None:
        """真实运行前要求已治理源码和 checkpoint,否则 fail closed。"""
        self.entry.require_runtime_assets()

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        """拒绝执行真实前向,避免误触发模型运行。"""
        raise self._unavailable_error("forward")

    def predict_action(self, batch: ModelInput) -> ActionChunk:
        """拒绝生成动作,避免误声明推理能力。"""
        raise self._unavailable_error("predict_action")

    def _unavailable_error(self, operation: str) -> ModelAssetsUnavailableError:
        """构造包含操作名和缺失资产字段的错误。"""
        missing = ", ".join(self.entry.assets.missing_runtime_requirements())
        return ModelAssetsUnavailableError(
            f"{operation} is unavailable for {self.entry.model_registry_key}: "
            f"missing governed source/checkpoint assets ({missing})"
        )


def build_gr00t_n1d6_adapter_skeleton() -> Gr00tN1D6AdapterSkeleton:
    """构造 metadata-only GR00T adapter skeleton。"""
    return Gr00tN1D6AdapterSkeleton()
