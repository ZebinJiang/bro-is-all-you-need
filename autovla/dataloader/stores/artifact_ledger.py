"""生成物 ledger helper。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from autovla.dataloader.stores.common import DEFAULT_LEDGER_VERSION, stable_checksum, write_json


@dataclass(frozen=True, slots=True)
class ArtifactLedgerEntry:
    """描述单个候选生成物条目。"""

    candidate: str
    path: str
    size_bytes: int
    file_count: int
    checksum_manifest: str
    created_by: str
    safe_to_delete_later: bool = True
    tracked_status: str = "ignored_generated_artifact"

    def to_json_dict(self) -> dict[str, object]:
        """返回 JSON-safe ledger 行。"""
        return {
            "candidate": self.candidate,
            "checksum_manifest": self.checksum_manifest,
            "created_by": self.created_by,
            "file_count": self.file_count,
            "path": self.path,
            "safe_to_delete_later": self.safe_to_delete_later,
            "size_bytes": self.size_bytes,
            "tracked_status": self.tracked_status,
        }


def write_artifact_ledger(
    *,
    entries: Sequence[ArtifactLedgerEntry],
    path: Path,
) -> Path:
    """写出稳定 artifact ledger。"""
    payload: Mapping[str, object] = {
        "entries": [entry.to_json_dict() for entry in entries],
        "generated_artifacts_tracked": False,
        "schema_version": DEFAULT_LEDGER_VERSION,
        "source_dataset_mutated": False,
    }
    write_json(path, payload)
    return path


def summarize_artifact(candidate: str, path: Path, *, created_by: str) -> ArtifactLedgerEntry:
    """统计候选输出目录或单文件。"""
    if path.is_dir():
        files = sorted(item for item in path.rglob("*") if item.is_file())
        size_bytes = sum(item.stat().st_size for item in files)
        digest_payload = {item.relative_to(path).as_posix(): item.stat().st_size for item in files}
        file_count = len(files)
    else:
        files = [path]
        size_bytes = path.stat().st_size
        digest_payload = {path.name: size_bytes}
        file_count = 1
    return ArtifactLedgerEntry(
        candidate=candidate,
        path=path.as_posix(),
        size_bytes=size_bytes,
        file_count=file_count,
        checksum_manifest=stable_checksum(digest_payload),
        created_by=created_by,
    )
