"""完整、版本化的生产 checkpoint manifest。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from autovla.training.checkpointing.identity import JsonValue, canonicalize_json_value

PRODUCTION_CHECKPOINT_SCHEMA = "autovla.production_training_checkpoint.v3"
LEGACY_PRODUCTION_CHECKPOINT_SCHEMAS = {
    "autovla.production_training_checkpoint.v1",
    "autovla.production_training_checkpoint.v2",
}
RANK_RUNTIME_STATE_SCHEMA = "autovla.rank_runtime_state.v1"
DATA_STATE_SCHEMA = "autovla.data_module_state.v1"


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """校验字符串键 mapping。"""

    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    raw = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{name} must be an object")
    return cast(Mapping[str, object], raw)


def _canonical_mapping(value: object, name: str) -> dict[str, JsonValue]:
    """校验并深度规范化一个 manifest JSON 对象。"""

    normalized = canonicalize_json_value(_mapping(value, name), f"$.{name}")
    if not isinstance(normalized, dict):
        raise ValueError(f"{name} must be an object")
    return normalized


@dataclass(frozen=True, slots=True)
class ProductionCheckpointManifest:
    """记录可恢复训练 checkpoint 的所有身份和状态文件。

    张量状态保存在 ``state.pt``,manifest 明确记录模型、优化器、调度器、
    策略、训练状态、配置、数据、归一化、RNG 与 provenance 的存在和身份。
    """

    run_id: str
    checkpoint_id: str
    reason: str
    created_at_utc: str
    state_file: str
    state_sha256: str
    model_family: str
    autovla_version: str
    git_commit: str
    config_fingerprint: str
    model_config_fingerprint: str
    model_capability_fingerprint: str
    config: Mapping[str, object]
    data_manifest: Mapping[str, object]
    data_fingerprints: Mapping[str, str]
    normalization: Mapping[str, object]
    strategy_name: str
    precision_mode: str
    training_state: Mapping[str, object]
    world_size: int
    rank_runtime_schema: str
    data_state_schema: str
    state_sections: tuple[str, ...]
    state_storage: str
    distributed_state_path: str | None
    checkpoint_adapter_report: Mapping[str, object]
    provenance: Mapping[str, object]
    schema_version: str = PRODUCTION_CHECKPOINT_SCHEMA

    def __post_init__(self) -> None:
        """冻结 mappings 并校验生产 schema 必需字段。"""

        for name in (
            "run_id",
            "checkpoint_id",
            "reason",
            "created_at_utc",
            "state_file",
            "state_sha256",
            "model_family",
            "autovla_version",
            "git_commit",
            "config_fingerprint",
            "model_config_fingerprint",
            "model_capability_fingerprint",
            "strategy_name",
            "precision_mode",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if self.schema_version != PRODUCTION_CHECKPOINT_SCHEMA:
            raise ValueError("unsupported production checkpoint schema")
        if type(self.world_size) is not int or self.world_size <= 0:
            raise ValueError("world_size must be a positive integer")
        if len(self.git_commit) != 40 or any(
            character not in "0123456789abcdef" for character in self.git_commit
        ):
            raise ValueError("git_commit must be a full lowercase hexadecimal commit")
        if self.rank_runtime_schema != RANK_RUNTIME_STATE_SCHEMA:
            raise ValueError("unsupported rank runtime state schema")
        if self.data_state_schema != DATA_STATE_SCHEMA:
            raise ValueError("unsupported data state schema")
        required = {
            "scheduler",
            "strategy",
            "training_state",
            "callback_state",
            "logger_state",
            "rank_runtime_state",
        }
        if self.state_storage == "consolidated":
            required.update(("model", "optimizer"))
            if self.distributed_state_path is not None:
                raise ValueError("consolidated checkpoint cannot declare distributed state")
        elif self.state_storage == "distributed_sharded":
            if self.distributed_state_path != "distributed_state":
                raise ValueError("sharded checkpoint must use distributed_state")
            if "model" in self.state_sections or "optimizer" in self.state_sections:
                raise ValueError("sharded checkpoint cannot embed model or optimizer state")
        else:
            raise ValueError("unsupported checkpoint state storage")
        if not required.issubset(self.state_sections):
            raise ValueError("checkpoint state sections are incomplete")
        if len(set(self.state_sections)) != len(self.state_sections):
            raise ValueError("checkpoint state sections must be unique")
        object.__setattr__(
            self, "config", MappingProxyType(_canonical_mapping(self.config, "config"))
        )
        object.__setattr__(
            self,
            "data_manifest",
            MappingProxyType(_canonical_mapping(self.data_manifest, "data_manifest")),
        )
        object.__setattr__(
            self,
            "data_fingerprints",
            MappingProxyType(_canonical_mapping(self.data_fingerprints, "data_fingerprints")),
        )
        object.__setattr__(
            self,
            "normalization",
            MappingProxyType(_canonical_mapping(self.normalization, "normalization")),
        )
        object.__setattr__(
            self,
            "training_state",
            MappingProxyType(_canonical_mapping(self.training_state, "training_state")),
        )
        object.__setattr__(
            self,
            "checkpoint_adapter_report",
            MappingProxyType(
                _canonical_mapping(self.checkpoint_adapter_report, "checkpoint_adapter_report")
            ),
        )
        object.__setattr__(
            self,
            "provenance",
            MappingProxyType(_canonical_mapping(self.provenance, "provenance")),
        )

    def to_dict(self) -> dict[str, object]:
        """返回稳定 JSON 字典。"""

        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "checkpoint_id": self.checkpoint_id,
            "reason": self.reason,
            "created_at_utc": self.created_at_utc,
            "state_file": self.state_file,
            "state_sha256": self.state_sha256,
            "model_family": self.model_family,
            "autovla_version": self.autovla_version,
            "git_commit": self.git_commit,
            "config_fingerprint": self.config_fingerprint,
            "model_config_fingerprint": self.model_config_fingerprint,
            "model_capability_fingerprint": self.model_capability_fingerprint,
            "config": dict(self.config),
            "data_manifest": dict(self.data_manifest),
            "data_fingerprints": dict(self.data_fingerprints),
            "normalization": dict(self.normalization),
            "strategy_name": self.strategy_name,
            "precision_mode": self.precision_mode,
            "training_state": dict(self.training_state),
            "world_size": self.world_size,
            "rank_runtime_schema": self.rank_runtime_schema,
            "data_state_schema": self.data_state_schema,
            "state_sections": list(self.state_sections),
            "state_storage": self.state_storage,
            "distributed_state_path": self.distributed_state_path,
            "checkpoint_adapter_report": dict(self.checkpoint_adapter_report),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ProductionCheckpointManifest":
        """严格读取生产 manifest 的版本和字段类型。"""

        schema = payload.get("schema_version")
        if schema in LEGACY_PRODUCTION_CHECKPOINT_SCHEMAS:
            raise ValueError(
                "production checkpoint v1 cannot resume deterministically: "
                "rank-local RNG and DataModule state are missing"
            )
        expected_fields = {
            "schema_version",
            "run_id",
            "checkpoint_id",
            "reason",
            "created_at_utc",
            "state_file",
            "state_sha256",
            "model_family",
            "autovla_version",
            "git_commit",
            "config_fingerprint",
            "model_config_fingerprint",
            "model_capability_fingerprint",
            "config",
            "data_manifest",
            "data_fingerprints",
            "normalization",
            "strategy_name",
            "precision_mode",
            "training_state",
            "world_size",
            "rank_runtime_schema",
            "data_state_schema",
            "state_sections",
            "state_storage",
            "distributed_state_path",
            "checkpoint_adapter_report",
            "provenance",
        }
        if set(payload) != expected_fields:
            raise ValueError("production checkpoint manifest fields are incomplete or unknown")

        def _text(name: str) -> str:
            """读取必需的非空文本字段。"""

            value = payload.get(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
            return value

        raw_sections = payload.get("state_sections")
        if not isinstance(raw_sections, list):
            raise ValueError("state_sections must be a string list")
        sections = cast(list[object], raw_sections)
        if not all(isinstance(item, str) for item in sections):
            raise ValueError("state_sections must be a string list")
        fingerprints = _mapping(payload.get("data_fingerprints"), "data_fingerprints")
        if not all(isinstance(value, str) for value in fingerprints.values()):
            raise ValueError("data_fingerprints values must be strings")
        world_size = payload.get("world_size")
        if type(world_size) is not int or world_size <= 0:
            raise ValueError("world_size must be a positive integer")
        return cls(
            schema_version=_text("schema_version"),
            run_id=_text("run_id"),
            checkpoint_id=_text("checkpoint_id"),
            reason=_text("reason"),
            created_at_utc=_text("created_at_utc"),
            state_file=_text("state_file"),
            state_sha256=_text("state_sha256"),
            model_family=_text("model_family"),
            autovla_version=_text("autovla_version"),
            git_commit=_text("git_commit"),
            config_fingerprint=_text("config_fingerprint"),
            model_config_fingerprint=_text("model_config_fingerprint"),
            model_capability_fingerprint=_text("model_capability_fingerprint"),
            config=_canonical_mapping(payload.get("config"), "config"),
            data_manifest=_canonical_mapping(payload.get("data_manifest"), "data_manifest"),
            data_fingerprints=cast(Mapping[str, str], fingerprints),
            normalization=_canonical_mapping(payload.get("normalization"), "normalization"),
            strategy_name=_text("strategy_name"),
            precision_mode=_text("precision_mode"),
            training_state=_canonical_mapping(payload.get("training_state"), "training_state"),
            world_size=world_size,
            rank_runtime_schema=_text("rank_runtime_schema"),
            data_state_schema=_text("data_state_schema"),
            state_sections=tuple(cast(list[str], sections)),
            state_storage=_text("state_storage"),
            distributed_state_path=(
                None
                if payload.get("distributed_state_path") is None
                else _text("distributed_state_path")
            ),
            checkpoint_adapter_report=_canonical_mapping(
                payload.get("checkpoint_adapter_report"),
                "checkpoint_adapter_report",
            ),
            provenance=_canonical_mapping(payload.get("provenance"), "provenance"),
        )

    @classmethod
    def read(cls, path: Path) -> "ProductionCheckpointManifest":
        """读取本地 JSON manifest。"""

        return cls.from_dict(_mapping(json.loads(path.read_text(encoding="utf-8")), "manifest"))


__all__ = [
    "DATA_STATE_SCHEMA",
    "LEGACY_PRODUCTION_CHECKPOINT_SCHEMAS",
    "PRODUCTION_CHECKPOINT_SCHEMA",
    "RANK_RUNTIME_STATE_SCHEMA",
    "ProductionCheckpointManifest",
]
