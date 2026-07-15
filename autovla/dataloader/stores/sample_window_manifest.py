"""共享 sample/window manifest 合同。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.dataloader.stores.common import (
    CAMERA_VIEWS,
    DEFAULT_MANIFEST_VERSION,
    MultiformatDatastoreConfig,
    SourceSample,
    load_source_samples,
    stable_checksum,
)

MANIFEST_VERSION = DEFAULT_MANIFEST_VERSION


@dataclass(frozen=True, slots=True)
class SampleWindowManifest:
    """描述所有候选共享的有界 sample/window 选择。"""

    dataset_root: str
    source_format: str
    seed: int
    max_episodes: int
    max_samples: int
    window_size: int
    camera_views: tuple[str, str, str]
    action_horizon: int
    action_dim: int
    selected_episodes: tuple[str, ...]
    selected_sample_ids: tuple[str, ...]
    selected_window_ids: tuple[str, ...]
    language_present_count: int
    state_present_count: int
    camera_ref_count: int
    checksum: str
    sample_count: int
    episode_count: int

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON-safe manifest。"""
        return {
            "action_dim": self.action_dim,
            "action_horizon": self.action_horizon,
            "camera_ref_count": self.camera_ref_count,
            "camera_views": list(self.camera_views),
            "checksum": self.checksum,
            "dataset_root": self.dataset_root,
            "episode_count": self.episode_count,
            "language_present_count": self.language_present_count,
            "manifest_version": MANIFEST_VERSION,
            "max_episodes": self.max_episodes,
            "max_samples": self.max_samples,
            "sample_count": self.sample_count,
            "seed": self.seed,
            "selected_episodes": list(self.selected_episodes),
            "selected_sample_ids": list(self.selected_sample_ids),
            "selected_window_ids": list(self.selected_window_ids),
            "source_format": self.source_format,
            "state_present_count": self.state_present_count,
            "window_size": self.window_size,
        }


def build_sample_window_manifest(config: MultiformatDatastoreConfig) -> SampleWindowManifest:
    """从 source dataset 构造确定性共享 manifest。"""
    return build_sample_window_manifest_from_samples(config, load_source_samples(config))


def build_sample_window_manifest_from_samples(
    config: MultiformatDatastoreConfig,
    samples: list[SourceSample],
) -> SampleWindowManifest:
    """基于已读取样本构造共享 manifest。"""
    action_dim = len(samples[0].action)
    selected_episodes = tuple(dict.fromkeys(sample.episode_id for sample in samples))
    selected_sample_ids = tuple(sample.sample_id for sample in samples)
    selected_window_ids = tuple(sample.window_id for sample in samples)
    payload = {
        "action_dim": action_dim,
        "action_horizon": config.action_horizon,
        "camera_views": list(CAMERA_VIEWS),
        "dataset_root": config.source_dataset.as_posix(),
        "max_episodes": config.max_episodes,
        "max_samples": config.max_samples,
        "sample_count": len(samples),
        "seed": config.seed,
        "selected_episodes": list(selected_episodes),
        "selected_sample_ids": list(selected_sample_ids),
        "selected_window_ids": list(selected_window_ids),
        "source_format": "zjh_lerobot_v21",
        "window_size": config.window_size,
    }
    checksum = stable_checksum(payload)
    return SampleWindowManifest(
        dataset_root=config.source_dataset.as_posix(),
        source_format="zjh_lerobot_v21",
        seed=config.seed,
        max_episodes=config.max_episodes,
        max_samples=config.max_samples,
        window_size=config.window_size,
        camera_views=CAMERA_VIEWS,
        action_horizon=config.action_horizon,
        action_dim=action_dim,
        selected_episodes=selected_episodes,
        selected_sample_ids=selected_sample_ids,
        selected_window_ids=selected_window_ids,
        language_present_count=sum(1 for sample in samples if sample.language),
        state_present_count=sum(1 for sample in samples if sample.state),
        camera_ref_count=sum(len(sample.camera_refs) for sample in samples),
        checksum=checksum,
        sample_count=len(samples),
        episode_count=len(selected_episodes),
    )
