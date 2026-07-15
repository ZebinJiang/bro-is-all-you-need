"""AutoVLA-native 本地 LeRobot v3-style 候选构建。"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from autovla.dataloader.stores.common import SourceSample, require_int, write_json
from autovla.dataloader.stores.lerobot_compat import (
    build_v3_candidate_rows,
    prepare_lerobot_v3_local_root,
    write_episode_parquet_rows,
    write_lerobot_meta_and_indices,
)


def build_lerobot_v3_local_candidate(
    root: Path,
    source_dataset: Path,
    samples: Sequence[SourceSample],
) -> Path:
    """构建 Isaac 可消费的本地 LeRobot v3-style 候选目录。"""
    prepare_lerobot_v3_local_root(
        root=root,
        source_dataset=source_dataset,
        samples=samples,
    )
    records_root = root / "records"
    if records_root.exists():
        shutil.rmtree(records_root)
    records_root.mkdir(parents=True, exist_ok=True)
    sample_index, episode_index, rows_by_episode = build_v3_candidate_rows(samples)
    relative_data_paths = write_episode_parquet_rows(root=root, rows_by_episode=rows_by_episode)
    for row in sample_index:
        episode_index_value = require_int(row["episode_index"], "episode_index")
        row["data_path"] = relative_data_paths[episode_index_value]
    write_lerobot_meta_and_indices(
        root=root,
        source_dataset=source_dataset,
        samples=samples,
        sample_index=sample_index,
        episode_index=episode_index,
    )
    for sample in samples:
        record_path = records_root / f"{sample.sample_id}.json"
        payload = sample.payload("lerobot_v3_local_artifact")
        record_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    write_json(
        root / "candidate_manifest.json",
        {
            "candidate_id": "zjh_lerobot_v3_local",
            "dependency_mode": "autovla_owned_local_v3_style_no_upstream_package",
            "format_contract": "lerobot_v3_local_isaac_compatible_v2",
            "prototype_only": False,
            "sample_count": len(samples),
            "status": "PASS",
        },
    )
    return root
