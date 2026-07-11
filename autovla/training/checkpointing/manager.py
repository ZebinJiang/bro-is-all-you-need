"""原子本地生产 checkpoint 保存和恢复。"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import torch
from torch import nn

from autovla.data.module import DataModule
from autovla.data.types import DataModuleState
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.training.checkpointing.manifest import (
    DATA_STATE_SCHEMA,
    RANK_RUNTIME_STATE_SCHEMA,
    ProductionCheckpointManifest,
)
from autovla.training.checkpointing.state_dict import (
    capture_rng_state,
    restore_rng_state,
    sha256_file,
    validate_rng_state,
)
from autovla.training.state import TrainingState
from autovla.training.strategy.base import TrainingStrategy, require_local_checkpoint_root


class CheckpointManager:
    """协调策略状态物化、模型族键映射和原子目录发布。"""

    def __init__(
        self,
        *,
        root: Path,
        run_id: str,
        model_family: str,
        config: Mapping[str, object],
        config_fingerprint: str,
        data_manifest: Mapping[str, object],
        data_fingerprints: Mapping[str, str],
        normalization: Mapping[str, object],
        provenance: Mapping[str, object],
        keep_last: int = 3,
        save_optimizer: bool = True,
    ) -> None:
        """保存完整 checkpoint 身份,构造阶段不创建目录。"""

        self.root = require_local_checkpoint_root(root)
        if not run_id.strip() or not model_family.strip() or not config_fingerprint.strip():
            raise ValueError("run_id, model_family, and config_fingerprint must not be empty")
        if keep_last <= 0:
            raise ValueError("keep_last must be positive")
        self.run_id = run_id
        self.model_family = model_family
        self.config = dict(config)
        self.config_fingerprint = config_fingerprint
        self.data_manifest = dict(data_manifest)
        self.data_fingerprints = dict(data_fingerprints)
        self.normalization = dict(normalization)
        self.provenance = dict(provenance)
        self.keep_last = keep_last
        self.save_optimizer = save_optimizer

    def save(
        self,
        *,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: TrainingStrategy,
        data_module: DataModule,
        state: TrainingState,
        reason: str,
    ) -> Path:
        """物化完整状态并由主 rank 原子发布 checkpoint 目录。"""

        local_runtime_state: dict[str, object] = {
            "schema_version": RANK_RUNTIME_STATE_SCHEMA,
            "rank": strategy.rank,
            "world_size": strategy.world_size,
            "data_module": dict(data_module.state_dict()),
            "rng": capture_rng_state(),
        }
        rank_runtime_state = strategy.collect_rank_runtime_state(local_runtime_state)
        local_id = (
            f"step-{state.optimizer_step:012d}-{uuid.uuid4().hex[:8]}"
            if strategy.is_primary
            else ""
        )
        checkpoint_id = strategy.broadcast_text(local_id)
        final_path = self.root / checkpoint_id
        model_state = strategy.model_state_dict(model)
        optimizer_state = strategy.optimizer_state_dict(optimizer) if self.save_optimizer else None
        payload: dict[str, object] = {
            "model": dict(model_state),
            "optimizer": optimizer_state,
            "scheduler": scheduler.state_dict(),
            "strategy": dict(strategy.strategy_state_dict()),
            "training_state": state.to_dict(),
            "rank_runtime_state": rank_runtime_state,
        }
        if strategy.is_primary:
            if rank_runtime_state is None:
                raise RuntimeError("primary rank did not receive rank runtime state")
            self._validate_rank_runtime_state(rank_runtime_state, strategy.world_size)
            self._publish(final_path, checkpoint_id, reason, payload, strategy, state)
            self._prune()
        strategy.barrier()
        return final_path

    def _publish(
        self,
        final_path: Path,
        checkpoint_id: str,
        reason: str,
        payload: Mapping[str, object],
        strategy: TrainingStrategy,
        state: TrainingState,
    ) -> None:
        """在同一父目录写临时树、fsync 并原子 rename。"""

        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.root / f".{checkpoint_id}.tmp-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            state_path = temporary / "state.pt"
            torch.save(dict(payload), state_path)
            self._fsync_file(state_path)
            sections = tuple(key for key, value in payload.items() if value is not None)
            manifest = ProductionCheckpointManifest(
                run_id=self.run_id,
                checkpoint_id=checkpoint_id,
                reason=reason,
                created_at_utc=datetime.now(timezone.utc).isoformat(),
                state_file=state_path.name,
                state_sha256=sha256_file(state_path),
                model_family=self.model_family,
                config_fingerprint=self.config_fingerprint,
                config=self.config,
                data_manifest=self.data_manifest,
                data_fingerprints=self.data_fingerprints,
                normalization=self.normalization,
                strategy_name=type(strategy).__name__,
                precision_mode=strategy.precision.mode,
                training_state=state.to_dict(),
                world_size=strategy.world_size,
                rank_runtime_schema=RANK_RUNTIME_STATE_SCHEMA,
                data_state_schema=DATA_STATE_SCHEMA,
                state_sections=sections,
                provenance=self.provenance,
            )
            manifest_path = temporary / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._fsync_file(manifest_path)
            self._fsync_directory(temporary)
            os.replace(temporary, final_path)
            self._fsync_directory(self.root)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def load(
        self,
        path: Path,
        *,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: TrainingStrategy,
        data_module: DataModule,
        family_adapter: ModelCheckpointAdapter,
    ) -> TrainingState:
        """校验完整兼容性和摘要后恢复模型、优化器、调度、策略、RNG 与进度。"""

        root = require_local_checkpoint_root(path)
        manifest = ProductionCheckpointManifest.read(root / "manifest.json")
        self._validate_manifest(manifest, strategy)
        state_path = root / manifest.state_file
        if sha256_file(state_path) != manifest.state_sha256:
            raise ValueError("checkpoint state digest mismatch")
        payload = torch.load(state_path, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            raise TypeError("checkpoint state payload must be a mapping")
        rank_runtime_state = payload.get("rank_runtime_state")
        if not isinstance(rank_runtime_state, Mapping):
            raise TypeError("checkpoint rank runtime state must be a mapping")
        runtime_states = self._validate_rank_runtime_state(
            cast(Mapping[str, object], rank_runtime_state), strategy.world_size
        )
        local_runtime = runtime_states[str(strategy.rank)]
        data_state = local_runtime["data_module"]
        rng_state = local_runtime["rng"]
        if not isinstance(data_state, Mapping) or not isinstance(rng_state, Mapping):
            raise TypeError("local rank runtime state is incomplete")
        local_data_state = cast(Mapping[str, object], data_state)
        local_rng_state = cast(Mapping[str, object], rng_state)
        DataModuleState.from_dict(local_data_state)
        data_module.validate_state_dict(local_data_state)
        validate_rng_state(local_rng_state)
        if local_rng_state["torch_cuda"] is not None and not torch.cuda.is_available():
            raise RuntimeError("local CUDA RNG state is incompatible with current runtime")

        model_state = payload.get("model")
        if not isinstance(model_state, Mapping):
            raise TypeError("checkpoint model state is missing")
        mapped = family_adapter.convert_state_dict(cast(Mapping[str, torch.Tensor], model_state))
        optimizer_state = payload.get("optimizer")
        if optimizer_state is not None:
            if not isinstance(optimizer_state, Mapping):
                raise TypeError("checkpoint optimizer state must be a mapping")
        elif self.save_optimizer:
            raise ValueError("checkpoint lacks required optimizer state")
        scheduler_state = payload.get("scheduler")
        strategy_state = payload.get("strategy")
        training_state = payload.get("training_state")
        for name, value in (
            ("scheduler", scheduler_state),
            ("strategy", strategy_state),
            ("training_state", training_state),
        ):
            if not isinstance(value, Mapping):
                raise TypeError(f"checkpoint {name} state must be a mapping")
        restored = TrainingState.from_dict(cast(Mapping[str, object], training_state))
        if restored.to_dict() != dict(manifest.training_state):
            raise ValueError("manifest and payload training states differ")

        strategy.load_model_state_dict(model, mapped)
        if optimizer_state is not None:
            strategy.load_optimizer_state_dict(
                optimizer,
                cast(Mapping[str, object], optimizer_state),
            )
        scheduler.load_state_dict(dict(cast(Mapping[str, object], scheduler_state)))
        strategy.load_strategy_state_dict(cast(Mapping[str, object], strategy_state))
        data_module.load_state_dict(local_data_state)
        restore_rng_state(local_rng_state)
        return restored

    @staticmethod
    def _validate_rank_runtime_state(
        state: Mapping[str, object], world_size: int
    ) -> Mapping[str, Mapping[str, object]]:
        """严格校验 rank 覆盖、局部 schema 和拓扑。"""

        expected = {str(rank) for rank in range(world_size)}
        if set(state) != expected:
            raise ValueError("checkpoint rank runtime coverage is incomplete")
        validated: dict[str, Mapping[str, object]] = {}
        for rank in range(world_size):
            value = state[str(rank)]
            if not isinstance(value, Mapping):
                raise TypeError("rank runtime payload must be a mapping")
            payload = cast(Mapping[str, object], value)
            if set(payload) != {"schema_version", "rank", "world_size", "data_module", "rng"}:
                raise ValueError("rank runtime payload fields are incomplete or unknown")
            if payload["schema_version"] != RANK_RUNTIME_STATE_SCHEMA:
                raise ValueError("rank runtime payload schema is unsupported")
            if payload["rank"] != rank or payload["world_size"] != world_size:
                raise ValueError("rank runtime payload topology is inconsistent")
            if not isinstance(payload["data_module"], Mapping) or not isinstance(
                payload["rng"], Mapping
            ):
                raise TypeError("rank runtime DataModule and RNG states must be mappings")
            DataModuleState.from_dict(cast(Mapping[str, object], payload["data_module"]))
            validate_rng_state(cast(Mapping[str, object], payload["rng"]))
            validated[str(rank)] = payload
        return validated

    def _validate_manifest(
        self, manifest: ProductionCheckpointManifest, strategy: TrainingStrategy
    ) -> None:
        """在任何状态写入前完成恢复兼容性校验。"""

        checks = {
            "run_id": (manifest.run_id, self.run_id),
            "model_family": (manifest.model_family, self.model_family),
            "config_fingerprint": (manifest.config_fingerprint, self.config_fingerprint),
            "strategy_name": (manifest.strategy_name, type(strategy).__name__),
            "precision_mode": (manifest.precision_mode, strategy.precision.mode),
            "world_size": (manifest.world_size, strategy.world_size),
            "rank_runtime_schema": (manifest.rank_runtime_schema, RANK_RUNTIME_STATE_SCHEMA),
            "data_state_schema": (manifest.data_state_schema, DATA_STATE_SCHEMA),
            "data_manifest": (dict(manifest.data_manifest), self.data_manifest),
            "data_fingerprints": (dict(manifest.data_fingerprints), self.data_fingerprints),
            "normalization": (dict(manifest.normalization), self.normalization),
        }
        mismatches = [name for name, (actual, expected) in checks.items() if actual != expected]
        if mismatches:
            raise ValueError(f"checkpoint resume compatibility mismatch: {mismatches}")

    def _prune(self) -> None:
        """仅删除本 run 超出保留数的已完成 checkpoint 目录。"""

        completed: list[tuple[str, Path]] = []
        for path in self.root.glob("step-*"):
            manifest_path = path / "manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = ProductionCheckpointManifest.read(manifest_path)
            if manifest.run_id == self.run_id:
                completed.append((manifest.created_at_utc, path))
        for _, path in sorted(completed)[: -self.keep_last]:
            shutil.rmtree(path)

    @staticmethod
    def _fsync_file(path: Path) -> None:
        """同步单个已关闭文件内容。"""

        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        """同步目录项以持久化 rename。"""

        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


__all__ = ["CheckpointManager"]
