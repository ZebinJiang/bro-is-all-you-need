"""原子本地生产 checkpoint 保存、预验证、恢复和回滚。"""

from __future__ import annotations

import copy
import json
import os
import shutil
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import torch
from torch import nn

from autovla.data.types import DataModuleState, DatasetManifest
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.training.callbacks.base import TrainingCallback
from autovla.training.checkpointing.identity import (
    canonicalize_json_value,
    checkpoint_compatibility_fingerprint,
    checkpoint_compatibility_projection,
    stable_fingerprint,
)
from autovla.training.checkpointing.manifest import (
    DATA_STATE_SCHEMA,
    RANK_RUNTIME_STATE_SCHEMA,
    ProductionCheckpointManifest,
)
from autovla.training.checkpointing.state_dict import (
    capture_rng_state,
    restore_rng_state,
    sha256_directory,
    sha256_file,
    validate_rng_state,
)
from autovla.training.session import PreparedTrainingSession
from autovla.training.state import TrainingState
from autovla.training.strategy.base import (
    CheckpointCollectiveProtocol,
    require_local_checkpoint_root,
)
from autovla.training.telemetry.logger import MetricLogger

if TYPE_CHECKING:
    from autovla.data.module import DataModule


class _TorchSave(Protocol):
    """描述 checkpoint 使用的 Torch 保存调用。"""

    def __call__(self, obj: object, path: str) -> None:
        """把对象保存到本地路径。"""

        ...


class _TorchLoad(Protocol):
    """描述 checkpoint 使用的安全 Torch 加载调用。"""

    def __call__(self, path: str, *, map_location: str, weights_only: bool) -> object:
        """从本地路径加载仅权重对象。"""

        ...


def _torch_member(name: str) -> object:
    """从 Torch 模块命名空间读取 checkpoint 可调用对象。"""

    namespace = cast(Mapping[str, object], vars(torch))
    try:
        return namespace[name]
    except KeyError as exc:
        raise RuntimeError(f"required Torch checkpoint member is missing: {name}") from exc


def _callback_key(index: int, callback: TrainingCallback) -> str:
    """返回顺序敏感且稳定的 callback 身份。"""

    cls = type(callback)
    return f"{index}:{cls.__module__}.{cls.__qualname__}"


def _callback_state(callbacks: Sequence[TrainingCallback]) -> dict[str, object]:
    """捕获全部 callback 状态和顺序身份。"""

    return {
        _callback_key(index, callback): dict(callback.state_dict())
        for index, callback in enumerate(callbacks)
    }


def _state_layout(state: Mapping[str, torch.Tensor]) -> dict[str, object]:
    """生成不含参数值的模型键、形状和 dtype 布局。"""

    return {
        name: {"shape": tuple(tensor.shape), "dtype": str(tensor.dtype)}
        for name, tensor in sorted(state.items())
    }


def _cpu_copy(value: object) -> object:
    """递归复制回滚状态并把 tensor 移到 CPU,避免占用双份 GPU 内存。"""

    if isinstance(value, torch.Tensor):
        return value.detach().to(device="cpu", copy=True)
    if isinstance(value, Mapping):
        return {key: _cpu_copy(item) for key, item in cast(Mapping[object, object], value).items()}
    if isinstance(value, list):
        return [_cpu_copy(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_cpu_copy(item) for item in cast(tuple[object, ...], value))
    return copy.deepcopy(value)


def _validate_scheduler_state(
    scheduler: torch.optim.lr_scheduler.LRScheduler,
    state: Mapping[str, object],
) -> None:
    """不修改 scheduler 地验证字段及容器形状。"""

    expected = cast(dict[str, object], scheduler.state_dict())
    if set(state) != set(expected):
        raise ValueError("checkpoint scheduler fields mismatch")
    for name, value in state.items():
        current = expected[name]
        if isinstance(current, list):
            if not isinstance(value, list) or len(cast(list[object], value)) != len(
                cast(list[object], current)
            ):
                raise ValueError(f"checkpoint scheduler list {name!r} mismatch")
        elif isinstance(current, Mapping):
            if not isinstance(value, Mapping) or set(cast(Mapping[object, object], value)) != set(
                cast(Mapping[object, object], current)
            ):
                raise ValueError(f"checkpoint scheduler mapping {name!r} mismatch")
        elif current is not None and type(value) is not type(current):
            raise TypeError(f"checkpoint scheduler field {name!r} has invalid type")


def _string_key_mapping(value: object, name: str) -> dict[str, object]:
    """验证反序列化对象为字符串键映射并建立独立所有权。"""

    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, object] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings")
        result[key] = item
    return result


class CheckpointManager:
    """协调策略状态、完整身份、原子发布和无部分变异恢复。"""

    def __init__(
        self,
        *,
        root: Path,
        run_id: str,
        model_family: str,
        autovla_version: str,
        git_commit: str,
        config: Mapping[str, object],
        config_fingerprint: str,
        model_config_fingerprint: str,
        model_capability_fingerprint: str,
        checkpoint_adapter_name: str,
        data_manifest: Mapping[str, object],
        data_fingerprints: Mapping[str, str],
        normalization: Mapping[str, object],
        provenance: Mapping[str, object],
        keep_last: int = 3,
        save_optimizer: bool = True,
    ) -> None:
        """保存完整 checkpoint 身份,构造阶段不创建目录。"""

        self.root = require_local_checkpoint_root(root)
        required = (
            run_id,
            model_family,
            autovla_version,
            git_commit,
            config_fingerprint,
            model_config_fingerprint,
            model_capability_fingerprint,
            checkpoint_adapter_name,
        )
        if any(not value.strip() for value in required):
            raise ValueError("checkpoint identity fields must not be empty")
        if len(git_commit) != 40 or any(
            character not in "0123456789abcdef" for character in git_commit
        ):
            raise ValueError("checkpoint Git identity must be a full lowercase commit")
        if keep_last <= 0:
            raise ValueError("keep_last must be positive")
        if not save_optimizer:
            raise ValueError("production checkpoint requires complete optimizer state")
        self.run_id = run_id
        self.model_family = model_family
        self.autovla_version = autovla_version
        self.git_commit = git_commit
        canonical_config = canonicalize_json_value(config, "$.config")
        if not isinstance(canonical_config, dict):
            raise TypeError("checkpoint config must be a canonical JSON object")
        self.config = canonical_config
        expected_config_fingerprint = checkpoint_compatibility_fingerprint(self.config)
        if config_fingerprint != expected_config_fingerprint:
            raise ValueError("config_fingerprint must use the canonical checkpoint projection")
        self.config_compatibility = checkpoint_compatibility_projection(self.config)
        self.config_fingerprint = config_fingerprint
        self.model_config_fingerprint = model_config_fingerprint
        self.model_capability_fingerprint = model_capability_fingerprint
        self.checkpoint_adapter_name = checkpoint_adapter_name
        self.data_manifest = self._canonical_identity_mapping(data_manifest, "data_manifest")
        canonical_fingerprints = self._canonical_identity_mapping(
            data_fingerprints, "data_fingerprints"
        )
        if not all(isinstance(value, str) for value in canonical_fingerprints.values()):
            raise TypeError("data_fingerprints values must be strings")
        self.data_fingerprints = {
            key: cast(str, value) for key, value in canonical_fingerprints.items()
        }
        self.normalization = self._canonical_identity_mapping(normalization, "normalization")
        self.provenance = self._canonical_identity_mapping(provenance, "provenance")
        self._runtime_data_identity: str | None = None
        self.keep_last = keep_last
        self.save_optimizer = save_optimizer

    @staticmethod
    def _canonical_identity_mapping(value: Mapping[str, object], name: str) -> dict[str, object]:
        """在 manager 构造边界深度规范化一个持久化身份对象。"""

        normalized = canonicalize_json_value(value, f"$.{name}")
        if not isinstance(normalized, dict):
            raise TypeError(f"{name} must be a canonical JSON object")
        return cast(dict[str, object], normalized)

    def save(
        self,
        *,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: PreparedTrainingSession,
        data_module: DataModule,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
        state: TrainingState,
        reason: str,
    ) -> Path:
        """保存完整控制状态和策略拥有的模型/优化器状态。"""

        self._bind_runtime_data_identity(data_module)
        state.validate_resume_boundary()
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
        payload: dict[str, object] = {
            "scheduler": scheduler.state_dict(),
            "strategy": dict(strategy.strategy_state_dict()),
            "training_state": state.to_dict(),
            "callback_state": _callback_state(callbacks),
            "logger_state": metric_logger.state_dict(),
            "rank_runtime_state": rank_runtime_state,
        }
        if strategy.uses_sharded_checkpoint:
            if not self.save_optimizer:
                raise ValueError("distributed strategy checkpoint requires optimizer state")
            return self._save_sharded(
                final_path=final_path,
                checkpoint_id=checkpoint_id,
                reason=reason,
                payload=payload,
                model=model,
                optimizer=optimizer,
                strategy=strategy,
                state=state,
                rank_runtime_state=rank_runtime_state,
            )
        model_state = dict(strategy.model_state_dict(model))
        optimizer_state = strategy.optimizer_state_dict(optimizer) if self.save_optimizer else None
        payload["model"] = model_state
        payload["optimizer"] = optimizer_state
        adapter_report = self._adapter_report(model_state, storage="consolidated")
        if strategy.is_primary:
            if rank_runtime_state is None:
                raise RuntimeError("primary rank did not receive rank runtime state")
            self._validate_rank_runtime_state(rank_runtime_state, strategy.world_size)
            self._publish(
                final_path=final_path,
                checkpoint_id=checkpoint_id,
                reason=reason,
                payload=payload,
                strategy=strategy,
                state=state,
                adapter_report=adapter_report,
                state_storage="consolidated",
                distributed_state_path=None,
            )
            self._prune()
        strategy.barrier()
        return final_path

    def _save_sharded(
        self,
        *,
        final_path: Path,
        checkpoint_id: str,
        reason: str,
        payload: Mapping[str, object],
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        strategy: PreparedTrainingSession,
        state: TrainingState,
        rank_runtime_state: Mapping[str, Mapping[str, object]] | None,
    ) -> Path:
        """在同父临时树中由全部 rank 保存 DCP 分片后原子发布。"""

        local_temporary = f".{checkpoint_id}.tmp-{uuid.uuid4().hex}" if strategy.is_primary else ""
        temporary_name = strategy.broadcast_text(local_temporary)
        temporary = self.root / temporary_name
        collective = CheckpointCollectiveProtocol(strategy)
        owns_checkpoint_paths = False

        def prepare_tree() -> None:
            """由 rank 0 创建本次保存独占的临时树。"""

            nonlocal owns_checkpoint_paths
            self.root.mkdir(parents=True, exist_ok=True)
            if final_path.exists() or temporary.exists():
                raise FileExistsError(f"checkpoint path already exists: {final_path}")
            temporary.mkdir()
            owns_checkpoint_paths = True

        def cleanup_tree() -> None:
            """仅清理本次保存实际拥有的临时树或已发布目录。"""

            if not owns_checkpoint_paths:
                return
            self._remove_tree(temporary)
            self._remove_tree(final_path)

        collective.run_phase(
            "save.prepare",
            prepare_tree,
            primary_only=True,
            cleanup=cleanup_tree,
        )
        distributed_report: Mapping[str, object] = {}

        def save_distributed_state() -> None:
            """让每个 rank 写入自身 DCP 分片并保留本地报告。"""

            nonlocal distributed_report
            distributed_report = strategy.save_sharded_checkpoint(
                temporary / "distributed_state",
                model,
                optimizer,
            )

        collective.run_phase(
            "save.distributed_state",
            save_distributed_state,
            cleanup=cleanup_tree,
        )
        validation_report: Mapping[str, object] = {}

        def validate_distributed_state() -> None:
            """让每个 rank 在发布前验证本地 DCP 读取计划。"""

            nonlocal validation_report
            validation_report = strategy.validate_sharded_checkpoint(
                temporary / "distributed_state",
                model,
                optimizer,
            )

        collective.run_phase(
            "save.validate",
            validate_distributed_state,
            cleanup=cleanup_tree,
        )

        def publish_checkpoint() -> None:
            """由 rank 0 写控制状态、摘要和完成标记后原子发布。"""

            if rank_runtime_state is None:
                raise RuntimeError("primary rank did not receive rank runtime state")
            self._validate_rank_runtime_state(rank_runtime_state, strategy.world_size)
            adapter_report = {
                "adapter": self.checkpoint_adapter_name,
                "model_config_fingerprint": self.model_config_fingerprint,
                "model_capability_fingerprint": self.model_capability_fingerprint,
                "distributed_state_sha256": sha256_directory(temporary / "distributed_state"),
                **dict(distributed_report),
                **dict(validation_report),
            }
            self._publish(
                final_path=final_path,
                checkpoint_id=checkpoint_id,
                reason=reason,
                payload=payload,
                strategy=strategy,
                state=state,
                adapter_report=adapter_report,
                state_storage="distributed_sharded",
                distributed_state_path="distributed_state",
                temporary=temporary,
            )

        collective.run_phase(
            "save.publish",
            publish_checkpoint,
            primary_only=True,
            cleanup=cleanup_tree,
        )
        collective.run_phase(
            "save.prune",
            self._prune,
            primary_only=True,
            cleanup=cleanup_tree,
        )
        return final_path

    def _adapter_report(
        self,
        state: Mapping[str, torch.Tensor],
        *,
        storage: str,
    ) -> dict[str, object]:
        """记录 checkpoint adapter 和模型布局摘要。"""

        layout = _state_layout(state)
        return {
            "adapter": self.checkpoint_adapter_name,
            "storage": storage,
            "model_key_count": len(layout),
            "model_layout_fingerprint": stable_fingerprint(layout),
            "model_config_fingerprint": self.model_config_fingerprint,
            "model_capability_fingerprint": self.model_capability_fingerprint,
        }

    def _publish(
        self,
        *,
        final_path: Path,
        checkpoint_id: str,
        reason: str,
        payload: Mapping[str, object],
        strategy: PreparedTrainingSession,
        state: TrainingState,
        adapter_report: Mapping[str, object],
        state_storage: str,
        distributed_state_path: str | None,
        temporary: Path | None = None,
    ) -> None:
        """写控制状态、manifest、完成标记并原子 rename。"""

        self.root.mkdir(parents=True, exist_ok=True)
        owned_temporary = temporary is None
        if temporary is None:
            temporary = self.root / f".{checkpoint_id}.tmp-{uuid.uuid4().hex}"
            temporary.mkdir()
        try:
            state_path = temporary / "state.pt"
            save = cast(_TorchSave, _torch_member("save"))
            save(dict(payload), str(state_path))
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
                autovla_version=self.autovla_version,
                git_commit=self.git_commit,
                config_fingerprint=self.config_fingerprint,
                model_config_fingerprint=self.model_config_fingerprint,
                model_capability_fingerprint=self.model_capability_fingerprint,
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
                state_storage=state_storage,
                distributed_state_path=distributed_state_path,
                checkpoint_adapter_report=adapter_report,
                provenance=self.provenance,
            )
            manifest_path = temporary / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._fsync_file(manifest_path)
            completion_path = temporary / "COMPLETED.json"
            completion_path.write_text(
                json.dumps(
                    {
                        "checkpoint_id": checkpoint_id,
                        "manifest_sha256": sha256_file(manifest_path),
                        "state_sha256": manifest.state_sha256,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            self._fsync_file(completion_path)
            self._fsync_directory(temporary)
            if final_path.exists():
                raise FileExistsError(f"checkpoint already exists: {final_path}")
            os.replace(temporary, final_path)
            self._fsync_directory(self.root)
        except BaseException:
            if owned_temporary:
                shutil.rmtree(temporary, ignore_errors=True)
            raise

    def load(
        self,
        path: Path,
        *,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: PreparedTrainingSession,
        data_module: DataModule,
        family_adapter: ModelCheckpointAdapter,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
    ) -> TrainingState:
        """完整预验证后恢复;意外应用失败时回滚所有 live 状态。"""

        root = require_local_checkpoint_root(path)
        manifest: ProductionCheckpointManifest | None = None
        prepared: dict[str, object] = {}

        def prevalidate() -> None:
            """读取并验证本 rank 的完整 checkpoint,不修改 live 状态。"""

            nonlocal manifest, prepared
            self._bind_runtime_data_identity(data_module)
            manifest = self._read_completed_manifest(root)
            self._validate_manifest(manifest, strategy)
            state_path = root / manifest.state_file
            if sha256_file(state_path) != manifest.state_sha256:
                raise ValueError("checkpoint state digest mismatch")
            load = cast(_TorchLoad, _torch_member("load"))
            payload = _string_key_mapping(
                load(str(state_path), map_location="cpu", weights_only=True),
                "checkpoint state payload",
            )
            expected_sections = set(manifest.state_sections)
            if set(payload) != expected_sections:
                raise ValueError("checkpoint state sections differ from manifest")
            prepared = self._prevalidate_payload(
                root=root,
                manifest=manifest,
                payload=payload,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                strategy=strategy,
                data_module=data_module,
                family_adapter=family_adapter,
                callbacks=callbacks,
                metric_logger=metric_logger,
            )

        if strategy.uses_sharded_checkpoint:
            CheckpointCollectiveProtocol(strategy).run_phase(
                "restore.prevalidate",
                prevalidate,
            )
        else:
            prevalidate()
        if manifest is None:
            raise RuntimeError("checkpoint prevalidation produced no manifest")
        return self._apply_with_rollback(
            root=root,
            manifest=manifest,
            prepared=prepared,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            strategy=strategy,
            data_module=data_module,
            callbacks=callbacks,
            metric_logger=metric_logger,
        )

    def _read_completed_manifest(self, root: Path) -> ProductionCheckpointManifest:
        """验证完成标记和 manifest 摘要。"""

        manifest_path = root / "manifest.json"
        completion_path = root / "COMPLETED.json"
        if not completion_path.is_file():
            raise ValueError("checkpoint is partial: COMPLETED.json is missing")
        completion = _string_key_mapping(
            json.loads(completion_path.read_text(encoding="utf-8")),
            "checkpoint completion marker",
        )
        if completion.get("manifest_sha256") != sha256_file(manifest_path):
            raise ValueError("checkpoint manifest digest mismatch")
        manifest = ProductionCheckpointManifest.read(manifest_path)
        if completion.get("checkpoint_id") != manifest.checkpoint_id:
            raise ValueError("checkpoint completion marker identity mismatch")
        if completion.get("state_sha256") != manifest.state_sha256:
            raise ValueError("checkpoint completion marker state digest mismatch")
        return manifest

    def _prevalidate_payload(
        self,
        *,
        root: Path,
        manifest: ProductionCheckpointManifest,
        payload: Mapping[str, object],
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: PreparedTrainingSession,
        data_module: DataModule,
        family_adapter: ModelCheckpointAdapter,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
    ) -> dict[str, object]:
        """验证每个状态子系统并返回已收窄对象,不修改 live 状态。"""

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

        scheduler_state = self._require_mapping(payload, "scheduler")
        strategy_state = self._require_mapping(payload, "strategy")
        training_state = self._require_mapping(payload, "training_state")
        callback_state = self._require_mapping(payload, "callback_state")
        logger_state = self._require_mapping(payload, "logger_state")
        _validate_scheduler_state(scheduler, scheduler_state)
        strategy.validate_strategy_state_dict(strategy_state)
        restored = TrainingState.from_dict(training_state)
        restored.validate_resume_boundary()
        if restored.to_dict() != dict(manifest.training_state):
            raise ValueError("manifest and payload training states differ")
        self._validate_callback_state(callbacks, callback_state)
        metric_logger.validate_state_dict(logger_state)

        prepared: dict[str, object] = {
            "data": local_data_state,
            "rng": local_rng_state,
            "scheduler": scheduler_state,
            "strategy": strategy_state,
            "training": restored,
            "callbacks": callback_state,
            "logger": logger_state,
        }
        if manifest.state_storage == "distributed_sharded":
            distributed = root / cast(str, manifest.distributed_state_path)
            report = manifest.checkpoint_adapter_report
            if report.get("distributed_state_sha256") != sha256_directory(distributed):
                raise ValueError("distributed checkpoint directory digest mismatch")
            strategy.validate_sharded_checkpoint(distributed, model, optimizer)
            prepared["distributed"] = distributed
            return prepared

        model_state = self._require_mapping(payload, "model")
        mapped = family_adapter.convert_state_dict(cast(Mapping[str, torch.Tensor], model_state))
        strategy.validate_model_state_dict(model, mapped)
        optimizer_state = payload.get("optimizer")
        if optimizer_state is None:
            if self.save_optimizer:
                raise ValueError("checkpoint lacks required optimizer state")
        elif not isinstance(optimizer_state, Mapping):
            raise TypeError("checkpoint optimizer state must be a mapping")
        else:
            strategy.validate_optimizer_state_dict(
                optimizer,
                cast(Mapping[str, object], optimizer_state),
            )
        expected_report = self._adapter_report(
            mapped,
            storage="consolidated",
        )
        if dict(manifest.checkpoint_adapter_report) != expected_report:
            raise ValueError("checkpoint adapter report or model layout mismatch")
        prepared["model"] = mapped
        prepared["optimizer"] = optimizer_state
        return prepared

    def _apply_with_rollback(
        self,
        *,
        root: Path,
        manifest: ProductionCheckpointManifest,
        prepared: Mapping[str, object],
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        strategy: PreparedTrainingSession,
        data_module: DataModule,
        callbacks: Sequence[TrainingCallback],
        metric_logger: MetricLogger,
    ) -> TrainingState:
        """应用预验证状态并在任一失败后恢复进入函数时的完整快照。"""

        snapshots: dict[str, object] = {}

        def capture_control_state() -> None:
            """捕获不属于 DCP 的本 rank 控制状态。"""

            snapshots.update(
                {
                    "scheduler": copy.deepcopy(scheduler.state_dict()),
                    "strategy": copy.deepcopy(dict(strategy.strategy_state_dict())),
                    "data": copy.deepcopy(dict(data_module.state_dict())),
                    "rng": capture_rng_state(),
                    "callbacks": copy.deepcopy(_callback_state(callbacks)),
                    "logger": copy.deepcopy(metric_logger.state_dict()),
                }
            )

        def apply_control_state(source: Mapping[str, object]) -> None:
            """按固定顺序应用本 rank 的控制状态。"""

            scheduler.load_state_dict(dict(cast(Mapping[str, object], source["scheduler"])))
            strategy.load_strategy_state_dict(cast(Mapping[str, object], source["strategy"]))
            data_module.load_state_dict(cast(Mapping[str, object], source["data"]))
            restore_rng_state(cast(Mapping[str, object], source["rng"]))
            self._load_callback_state(
                callbacks,
                cast(Mapping[str, object], source["callbacks"]),
            )
            metric_logger.load_state_dict(cast(Mapping[str, object], source["logger"]))

        if manifest.state_storage == "distributed_sharded":

            def apply_sharded_state() -> None:
                """由策略公共 API 恢复分片状态后应用控制状态。"""

                strategy.load_sharded_checkpoint(
                    cast(Path, prepared["distributed"]), model, optimizer
                )
                apply_control_state(prepared)

            # ZeRO-3 不支持同一 engine 先保存回滚快照再立即加载。
            # 任一失败都会停止全体 rank,后续必须从已完成 checkpoint 重启。
            CheckpointCollectiveProtocol(strategy).run_phase(
                "restore.distributed",
                apply_sharded_state,
            )
            return cast(TrainingState, prepared["training"])

        capture_control_state()
        snapshots["model"] = {
            name: tensor.detach().to(device="cpu", copy=True)
            for name, tensor in strategy.model_state_dict(model).items()
        }
        snapshots["optimizer"] = _cpu_copy(strategy.optimizer_state_dict(optimizer))
        try:
            strategy.load_model_state_dict(
                model,
                cast(Mapping[str, torch.Tensor], prepared["model"]),
            )
            optimizer_state = prepared.get("optimizer")
            if optimizer_state is not None:
                strategy.load_optimizer_state_dict(
                    optimizer,
                    cast(Mapping[str, object], optimizer_state),
                )
            apply_control_state(prepared)
        except BaseException as error:
            try:
                strategy.load_model_state_dict(
                    model,
                    cast(Mapping[str, torch.Tensor], snapshots["model"]),
                )
                strategy.load_optimizer_state_dict(
                    optimizer,
                    cast(Mapping[str, object], snapshots["optimizer"]),
                )
                apply_control_state(snapshots)
            except BaseException as rollback_error:
                error.args = (*error.args, f"checkpoint rollback failed: {rollback_error!r}")
            raise
        return cast(TrainingState, prepared["training"])

    @staticmethod
    def _dataset_manifest_payload(manifest: DatasetManifest) -> dict[str, object]:
        """把运行时 DatasetManifest 投影为无路径、可持久化的完整身份。"""
        return {
            "schema_version": manifest.schema_version,
            "datasets": list(manifest.datasets),
            "backends": list(manifest.backends),
            "splits": list(manifest.splits),
            "sample_counts": list(manifest.sample_counts),
            "source_fingerprints": list(manifest.source_fingerprints),
            "schema_fingerprints": list(manifest.schema_fingerprints),
            "temporal_query_fingerprints": list(manifest.temporal_query_fingerprints),
            "weights": list(manifest.weights),
            "embodiments": list(manifest.embodiments),
            "mix_strategy": manifest.mix_strategy,
            "mix_seed": manifest.mix_seed,
            "balance_by": manifest.balance_by,
            "loader_batch_size": manifest.loader_batch_size,
            "loader_drop_last": manifest.loader_drop_last,
            "transform_fingerprint": manifest.transform_fingerprint,
            "statistics_fingerprint": manifest.statistics_fingerprint,
            "metadata": dict(manifest.metadata),
        }

    def _bind_runtime_data_identity(self, data_module: DataModule) -> None:
        """把 DataModule 真实 manifest/source/transform/statistics 绑定到兼容性。"""
        raw_manifest = cast(object, data_module.dataset_manifest())
        if not isinstance(raw_manifest, DatasetManifest):
            raise TypeError("DataModule.dataset_manifest must return DatasetManifest")
        manifest = raw_manifest
        manifest_payload = self._dataset_manifest_payload(manifest)
        runtime_identity = {
            "manifest": manifest_payload,
            "manifest_fingerprint": manifest.fingerprint,
            "source_fingerprints": {
                name: fingerprint
                for name, fingerprint in zip(
                    manifest.datasets,
                    manifest.source_fingerprints,
                    strict=True,
                )
            },
            "transform_fingerprint": manifest.transform_fingerprint,
            "statistics_fingerprint": manifest.statistics_fingerprint,
        }
        identity = stable_fingerprint(runtime_identity)
        if self._runtime_data_identity is not None:
            if self._runtime_data_identity != identity:
                raise ValueError("runtime dataset identity changed after checkpoint binding")
            return
        planned_manifest = self.data_manifest
        self.data_manifest = self._canonical_identity_mapping(
            {
                "planned": planned_manifest,
                "resolved": runtime_identity,
            },
            "data_manifest",
        )
        runtime_fingerprints = {
            "runtime_manifest": manifest.fingerprint,
            "runtime_transform": manifest.transform_fingerprint,
            "runtime_statistics": manifest.statistics_fingerprint,
            **{
                f"runtime_source:{name}": fingerprint
                for name, fingerprint in zip(
                    manifest.datasets,
                    manifest.source_fingerprints,
                    strict=True,
                )
            },
        }
        overlaps = {
            key
            for key, value in runtime_fingerprints.items()
            if key in self.data_fingerprints and self.data_fingerprints[key] != value
        }
        if overlaps:
            raise ValueError(f"planned/runtime data fingerprint conflict: {sorted(overlaps)}")
        self.data_fingerprints = {
            **self.data_fingerprints,
            **runtime_fingerprints,
        }
        self.provenance = self._canonical_identity_mapping(
            {
                **self.provenance,
                "runtime_data_identity": runtime_identity,
            },
            "provenance",
        )
        self._runtime_data_identity = identity

    @staticmethod
    def _require_mapping(payload: Mapping[str, object], name: str) -> Mapping[str, object]:
        """读取必需 mapping 状态段。"""

        value = payload.get(name)
        if not isinstance(value, Mapping):
            raise TypeError(f"checkpoint {name} state must be a mapping")
        return cast(Mapping[str, object], value)

    @staticmethod
    def _validate_callback_state(
        callbacks: Sequence[TrainingCallback],
        state: Mapping[str, object],
    ) -> None:
        """不修改 callback 地验证顺序、身份和状态。"""

        expected = tuple(_callback_key(index, callback) for index, callback in enumerate(callbacks))
        if tuple(state) != expected:
            raise ValueError("checkpoint callback identity or order mismatch")
        for key, callback in zip(expected, callbacks, strict=True):
            value = state[key]
            if not isinstance(value, Mapping):
                raise TypeError("checkpoint callback state must be a mapping")
            callback.validate_state_dict(cast(Mapping[str, object], value))

    @staticmethod
    def _load_callback_state(
        callbacks: Sequence[TrainingCallback],
        state: Mapping[str, object],
    ) -> None:
        """按已验证顺序恢复 callback 状态。"""

        CheckpointManager._validate_callback_state(callbacks, state)
        for key, callback in zip(state, callbacks, strict=True):
            callback.load_state_dict(cast(Mapping[str, object], state[key]))

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
        self, manifest: ProductionCheckpointManifest, strategy: PreparedTrainingSession
    ) -> None:
        """在任何状态写入前完成恢复身份和兼容性校验。"""

        expected_storage = (
            "distributed_sharded" if strategy.uses_sharded_checkpoint else "consolidated"
        )
        checks = {
            "run_id": (manifest.run_id, self.run_id),
            "model_family": (manifest.model_family, self.model_family),
            "autovla_version": (manifest.autovla_version, self.autovla_version),
            "git_commit": (manifest.git_commit, self.git_commit),
            "config_fingerprint": (manifest.config_fingerprint, self.config_fingerprint),
            "config_compatibility": (
                checkpoint_compatibility_projection(manifest.config),
                self.config_compatibility,
            ),
            "model_config_fingerprint": (
                manifest.model_config_fingerprint,
                self.model_config_fingerprint,
            ),
            "model_capability_fingerprint": (
                manifest.model_capability_fingerprint,
                self.model_capability_fingerprint,
            ),
            "checkpoint_adapter": (
                manifest.checkpoint_adapter_report.get("adapter"),
                self.checkpoint_adapter_name,
            ),
            "state_storage": (manifest.state_storage, expected_storage),
            "strategy_name": (manifest.strategy_name, type(strategy).__name__),
            "precision_mode": (manifest.precision_mode, strategy.precision.mode),
            "world_size": (manifest.world_size, strategy.world_size),
            "rank_runtime_schema": (manifest.rank_runtime_schema, RANK_RUNTIME_STATE_SCHEMA),
            "data_state_schema": (manifest.data_state_schema, DATA_STATE_SCHEMA),
            "data_manifest": (manifest.data_manifest, self.data_manifest),
            "data_fingerprints": (manifest.data_fingerprints, self.data_fingerprints),
            "normalization": (manifest.normalization, self.normalization),
            "provenance": (manifest.provenance, self.provenance),
        }
        mismatches = [name for name, (actual, expected) in checks.items() if actual != expected]
        if checkpoint_compatibility_fingerprint(manifest.config) != manifest.config_fingerprint:
            mismatches.append("manifest_config_fingerprint")
        if mismatches:
            raise ValueError(f"checkpoint resume compatibility mismatch: {mismatches}")

    def _prune(self) -> None:
        """仅删除本 run 超出保留数的已完成 checkpoint 目录。"""

        completed: list[tuple[str, Path]] = []
        for path in self.root.glob("step-*"):
            manifest_path = path / "manifest.json"
            completion_path = path / "COMPLETED.json"
            if not manifest_path.is_file() or not completion_path.is_file():
                continue
            manifest = ProductionCheckpointManifest.read(manifest_path)
            if manifest.run_id == self.run_id:
                completed.append((manifest.created_at_utc, path))
        for _, path in sorted(completed)[: -self.keep_last]:
            shutil.rmtree(path)

    @staticmethod
    def _remove_tree(path: Path) -> None:
        """删除本次操作拥有的目录并让文件系统错误进入集体状态。"""

        if path.exists():
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
