"""AutoVLA 唯一生产训练组合根。"""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla import __version__ as autovla_version
from autovla.config import ExperimentConfig, load_yaml, to_resolved_dict
from autovla.core.registry import OptionalDependencyError
from autovla.training.checkpointing.identity import checkpoint_compatibility_fingerprint

if TYPE_CHECKING:
    import torch
    from torch import nn

    from autovla.models.assembly import (
        ModelAssemblyPlan,
        ModelAssemblyRequest,
        ModelRuntimeBundle,
    )
    from autovla.models.interfaces import ModelProcessor
    from autovla.training.engine import TrainingEngine
    from autovla.training.optimization import ParameterRole
    from autovla.training.plan import TrainingPlan
    from autovla.training.precision import PrecisionMode


class _TrainableParameter(Protocol):
    """描述参数角色分类所需的最小可训练状态。"""

    requires_grad: bool


class _NamedParameterModule(Protocol):
    """描述 Torch 模块在动态注册表边界后的参数迭代能力。"""

    def named_parameters(self) -> Iterator[tuple[str, _TrainableParameter]]:
        """按稳定名称返回模型参数。"""

        ...


@runtime_checkable
class _ModelFactory(Protocol):
    """约束注册模型工厂唯一运行包构造边界。"""

    def build_runtime_bundle(
        self,
        request: ModelAssemblyRequest,
        /,
    ) -> ModelRuntimeBundle[ModelProcessor, object, object, nn.Module, object, object]:
        """根据规范装配请求返回唯一家族运行包。"""

        ...


def _require_model_factory_result(
    value: object,
) -> ModelRuntimeBundle[ModelProcessor, object, object, nn.Module, object, object]:
    """在动态注册表边界验证并收窄家族运行包。"""
    from autovla.models.assembly import ModelRuntimeBundle

    if not isinstance(value, ModelRuntimeBundle):
        raise TypeError("model factory must return ModelRuntimeBundle")
    return cast(
        "ModelRuntimeBundle[ModelProcessor, object, object, nn.Module, object, object]",
        value,
    )


def _invoke_model_factory(
    request: ModelAssemblyRequest,
    model_factory: _ModelFactory,
) -> ModelRuntimeBundle[ModelProcessor, object, object, nn.Module, object, object]:
    """把同一规范请求交给 family 工厂并只接收运行包。"""
    return _require_model_factory_result(model_factory.build_runtime_bundle(request))


def _resolve_training_assembly(
    config: ExperimentConfig,
    request: ModelAssemblyRequest,
) -> tuple[ModelAssemblyPlan, TrainingPlan]:
    """从同一规范请求依次解析模型装配计划和训练计划。"""
    from autovla.models.assembly import resolve_model_assembly
    from autovla.training.plan import resolve_training_plan

    model_assembly_plan = resolve_model_assembly(request)
    training_plan = resolve_training_plan(config, model_assembly_plan)
    return model_assembly_plan, training_plan


def build_parser() -> argparse.ArgumentParser:
    """构造生产训练参数解析器。"""
    parser = argparse.ArgumentParser(prog="autovla-train")
    parser.add_argument(
        "config",
        help="本地 YAML 路径或 pkg://group/name 包资源",
    )
    parser.add_argument("--preset-root", help="命名预设根目录")
    parser.add_argument("--set", action="append", default=[], dest="overrides")
    return parser


def _require_training_extra() -> None:
    """在导入训练运行时前检查所选 training extra。"""
    if importlib.util.find_spec("torch") is None:
        raise OptionalDependencyError(
            "production training requires missing module torch; "
            "install the 'training' extra before composition"
        )


def _parameter_roles(model: object) -> dict[str, ParameterRole]:
    """按组合模型的显式模块边界标注每个可训练参数。"""
    from torch import nn

    from autovla.training.optimization import ParameterRole

    if not isinstance(model, nn.Module):
        raise TypeError("model factory must return a torch.nn.Module")
    roles: dict[str, ParameterRole] = {}
    parameter_module = cast(_NamedParameterModule, model)
    for name, parameter in parameter_module.named_parameters():
        if not parameter.requires_grad:
            continue
        role_name = name.removeprefix("module.")
        if role_name.startswith("backbone."):
            roles[name] = ParameterRole.BACKBONE
        elif role_name.startswith("action_head."):
            roles[name] = ParameterRole.ACTION_HEAD
        else:
            roles[name] = ParameterRole.OTHER
    return roles


def compose_training_engine(config: ExperimentConfig) -> TrainingEngine:
    """把严格配置延迟组合成唯一生产 TrainingEngine。

    该函数只在调用时解析可选运行时组件。导入 CLI、列举注册表或检查配置
    均不会构造模型、打开数据、初始化分布式环境或执行训练。
    """
    if config.run.intent != "training":
        raise ValueError("autovla-train requires run.intent='training'")
    from autovla.models.families.specification import RuntimeSupportState
    from autovla.models.registry import get_model_family_registration

    family = get_model_family_registration(config.model.registry_key)
    if family.spec.runtime_support is not RuntimeSupportState.EXECUTABLE:
        # 生命周期门必须早于训练依赖、CUDA 环境和模型资产副作用。
        raise ValueError(
            f"model family {family.spec.family_key!r} runtime is fail-closed: "
            f"{family.spec.runtime_support.value}"
        )
    if family.factory is None:
        raise ValueError(
            f"model family {family.spec.family_key!r} is specification-only and cannot train"
        )
    if not family.spec.assembly_eligible:
        raise ValueError(
            f"model family {family.spec.family_key!r} has no executable assembly evidence"
        )
    from autovla.assets.registry import DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY
    from autovla.training.runtime import resolve_verified_training_runtime

    asset_status = DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY.require(family.spec.family_key)
    if not asset_status.runtime_authorized:
        # C3 数据门和许可门都必须早于环境探测、CUDA、模型和数据副作用。
        raise ValueError(
            f"model family {family.spec.family_key!r} training is fail-closed: "
            f"{asset_status.first_blocker}"
        )
    repository_root = Path(__file__).resolve().parents[2]
    verified_runtime = resolve_verified_training_runtime(
        repository_root,
        family.spec.family_key,
    )
    _require_training_extra()

    from torch.optim import Optimizer

    from autovla.core.types.training import TrainingBatch
    from autovla.data.module import DataModule
    from autovla.data.registry import build_data_module_registry
    from autovla.models.assembly import TrainingAssemblyAdapter
    from autovla.models.interfaces import ModelProcessor
    from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
    from autovla.models.outputs import ActionPrediction, ModelInputBatch
    from autovla.training.callbacks import LoggingCallback, ProgressCallback
    from autovla.training.callbacks.base import TrainingCallback
    from autovla.training.checkpointing import BaseModelAssetProvenance, CheckpointManager
    from autovla.training.checkpointing.identity import resolve_git_commit, stable_fingerprint
    from autovla.training.context import TrainingContext
    from autovla.training.engine import TrainingEngine
    from autovla.training.optimization import (
        calculate_total_optimizer_steps,
        create_adamw,
        create_scheduler,
    )
    from autovla.training.precision import PrecisionPolicy
    from autovla.training.registry import build_training_strategy_registry
    from autovla.training.runtime import TrainingRuntimeIdentity
    from autovla.training.session import (
        PreparedTrainingSession,
        StrategyInitializationContextFactory,
        TrainingStrategy,
    )
    from autovla.training.state import StepStatus, TrainingState
    from autovla.training.step import TrainingStepOutput
    from autovla.training.telemetry.data import DataTelemetryRecord
    from autovla.training.telemetry.logger import MetricLogger

    precision = PrecisionPolicy(cast("PrecisionMode", config.training.precision.mode))
    strategy_entry = build_training_strategy_registry().get(
        config.training.distributed.strategy_key
    )
    strategy_factory = strategy_entry.factory.load()
    strategy_kwargs: dict[str, object] = {}
    strategy_key = config.training.distributed.strategy_key
    if strategy_key == "distributed_data_parallel":
        strategy_kwargs.update(
            expected_world_size=config.training.distributed.world_size,
            gradient_as_bucket_view=config.training.distributed.gradient_as_bucket_view,
            find_unused_parameters=config.training.distributed.find_unused_parameters,
        )
    elif strategy_key.startswith("deepspeed_zero_"):
        deepspeed_config = config.training.distributed.deepspeed
        if deepspeed_config is None:
            raise RuntimeError("validated deepspeed strategy requires a DeepSpeedConfig")
        strategy_kwargs.update(
            expected_world_size=config.training.distributed.world_size,
            deepspeed_config=deepspeed_config,
            micro_batch_size_per_gpu=config.data.loader.batch_size,
            gradient_accumulation_steps=config.training.gradient_accumulation_steps,
            gradient_clipping=config.training.gradient_clip_norm,
        )
    strategy = strategy_factory(precision, **strategy_kwargs)
    if not isinstance(strategy, TrainingStrategy):
        raise TypeError("training strategy factory must return TrainingStrategy")
    # DDP/DeepSpeed 必须在模型分配前绑定 local CUDA device。
    strategy.configure_process_environment()

    model_factory = family.factory.create()
    if not isinstance(model_factory, TrainingAssemblyAdapter):
        raise TypeError(
            f"model family {family.spec.family_key!r} lacks a production training adapter"
        )
    prepared_assembly = model_factory.prepare_training_assembly(
        config,
        StrategyInitializationContextFactory(strategy),
    )
    assembly_request = prepared_assembly.request
    if assembly_request.family_key != family.spec.family_key:
        raise ValueError("family training adapter returned a request for a different family")
    model_assembly_plan, training_plan = _resolve_training_assembly(config, assembly_request)
    if not isinstance(model_factory, _ModelFactory):
        raise TypeError("model factory must expose build_runtime_bundle")
    # family 工厂独占初始化上下文进入权,避免一次性 ZeRO-3 上下文被重复消费。
    runtime_bundle = _invoke_model_factory(assembly_request, model_factory)
    runtime_identity = TrainingRuntimeIdentity.from_bundle(
        runtime_bundle,
        verified_runtime,
    )
    components = runtime_bundle.assembly_result
    if components.plan != model_assembly_plan:
        raise ValueError("model factory result must bind the resolved ModelAssemblyPlan")
    model = components.model
    processor = components.processor
    checkpoint_adapter = components.checkpoint_adapter
    if not isinstance(checkpoint_adapter, ModelCheckpointAdapter):
        raise TypeError("model factory checkpoint adapter must implement ModelCheckpointAdapter")

    data_factory = build_data_module_registry().get("standard")
    data_module = data_factory.create(config.data)
    if not isinstance(data_module, DataModule):
        raise TypeError("standard data factory must return DataModule")

    def optimizer_factory(model: nn.Module) -> Optimizer:
        """针对策略准备后的规范参数身份创建优化器。"""

        return create_adamw(
            model,
            _parameter_roles(model),
            config.training.optimization,
        )

    def scheduler_factory(
        optimizer: Optimizer,
        total_steps: int,
    ) -> torch.optim.lr_scheduler.LRScheduler:
        """按真实每 rank loader 长度创建学习率调度器。"""

        calculated = calculate_total_optimizer_steps(
            batches_per_epoch=total_steps,
            epochs=config.training.epochs,
            accumulation_steps=config.training.gradient_accumulation_steps,
            max_steps=config.training.max_steps,
        )
        return create_scheduler(
            optimizer,
            config.training.optimization.scheduler,
            calculated_total_steps=calculated,
        )

    logger = MetricLogger(
        stdout=config.training.logging.stdout,
        jsonl_path=(
            None
            if config.training.logging.jsonl_path is None
            else Path(config.training.logging.jsonl_path)
        ),
    )
    source_names = (
        tuple(dataset.name for dataset in config.data.datasets)
        if config.data.datasets
        else (config.data.name,)
    )
    source_weights = (
        tuple(float(dataset.weight) for dataset in config.data.datasets)
        if config.data.datasets
        else (1.0,)
    )
    total_source_weight = sum(source_weights)
    requested_weights = {
        name: float(weight / total_source_weight)
        for name, weight in zip(source_names, source_weights, strict=True)
    }
    context_holder: list[TrainingContext] = []

    class _DataTelemetryProcessor(ModelProcessor):
        """在同一模型处理器边界捕获有效元素,不拥有训练 step。"""

        def __init__(self, delegate: ModelProcessor) -> None:
            """绑定唯一 family processor。"""
            self._delegate = delegate
            self._pending: tuple[DataTelemetryRecord, torch.Tensor] | None = None

        def prepare_batch(
            self,
            batch: TrainingBatch,
            *,
            device: torch.device,
            dtype: torch.dtype | None,
            training: bool,
        ) -> ModelInputBatch:
            """转发处理并保存本 step 的 rank-local 数据身份与有效计数。"""
            if self._pending is not None:
                raise RuntimeError("previous data telemetry record was not consumed")
            prepared = self._delegate.prepare_batch(
                batch,
                device=device,
                dtype=dtype,
                training=training,
            )
            if not context_holder or context_holder[0].session is None:
                raise RuntimeError("data telemetry requires the prepared training session")
            session = context_holder[0].session
            # 图像与动作计数来自 CPU batch, token 只保留设备标量到 flush 边界。
            self._pending = (
                DataTelemetryRecord.from_training_batch(
                    batch,
                    rank=session.rank,
                    world_size=session.world_size,
                    fallback_dataset=config.data.name,
                    requested_weights=requested_weights,
                    planned_source_fingerprints=training_plan.data.source_fingerprints,
                    valid_image_elements=sum(int(image.size) for image in batch.images.values()),
                    valid_token_elements=0,
                    valid_action_elements=int(batch.action_mask.sum()),
                ),
                prepared.attention_mask.sum(),
            )
            return prepared

        def decode_actions(
            self,
            actions: torch.Tensor,
            *,
            batch: ModelInputBatch,
        ) -> ActionPrediction:
            """保持 family processor 的动作逆变换所有权。"""
            return self._delegate.decode_actions(actions, batch=batch)

        def take_record(self) -> tuple[DataTelemetryRecord, torch.Tensor]:
            """把 host 记录和未物化 token 标量一次性交给 callback。"""
            if self._pending is None:
                raise RuntimeError("model processor produced no data telemetry record")
            pending = self._pending
            self._pending = None
            return pending

    telemetry_processor = _DataTelemetryProcessor(processor)

    class _DataTelemetryCallback(TrainingCallback):
        """按配置周期聚合 rank-local 记录并调用既有 session collective。"""

        def __init__(self) -> None:
            """初始化设备端 token 累计量和可恢复 host 余量。"""

            self._pending_token_elements: torch.Tensor | None = None
            self._restored_token_elements = 0
            self._pending_transform_fingerprint: str | None = None

        def _session(self) -> PreparedTrainingSession:
            """读取 Engine 已准备的唯一 session。"""
            if not context_holder or context_holder[0].session is None:
                raise RuntimeError("data telemetry requires the prepared training session")
            return context_holder[0].session

        def _accumulate_token_count(
            self,
            token_count: torch.Tensor,
            transform_fingerprint: str,
        ) -> None:
            """在设备端合并标量,不在普通微批路径触发 host 同步。"""

            if (
                self._pending_transform_fingerprint is not None
                and self._pending_transform_fingerprint != transform_fingerprint
            ):
                raise ValueError("pending data telemetry transform fingerprint drifted")
            self._pending_transform_fingerprint = transform_fingerprint
            self._pending_token_elements = (
                token_count
                if self._pending_token_elements is None
                else self._pending_token_elements + token_count
            )

        def _materialize_token_count(self) -> int:
            """仅在日志 flush 或 checkpoint 状态边界物化一个设备标量。"""

            device_total = (
                0
                if self._pending_token_elements is None
                else int(self._pending_token_elements.item())
            )
            return self._restored_token_elements + device_total

        def _queue_token_correction(self) -> None:
            """在 flush 前追加只携带 token 总数的可组合记录。"""

            total = self._materialize_token_count()
            transform = self._pending_transform_fingerprint
            if transform is None:
                if total != 0:
                    raise RuntimeError("pending token telemetry lacks transform identity")
                return
            session = self._session()
            logger.queue_data_telemetry(
                DataTelemetryRecord(
                    rank=session.rank,
                    world_size=session.world_size,
                    aggregate="rank_local",
                    requested_weights=requested_weights,
                    valid_token_elements=total,
                    transform_fingerprint=transform,
                )
            )
            self._pending_token_elements = None
            self._restored_token_elements = 0
            self._pending_transform_fingerprint = None

        def state_dict(self) -> Mapping[str, object]:
            """在 checkpoint 边界保存已排队 token 总数与变换身份。"""

            return {
                "pending_token_elements": self._materialize_token_count(),
                "transform_fingerprint": self._pending_transform_fingerprint,
            }

        def validate_state_dict(self, state: Mapping[str, object]) -> None:
            """验证可恢复 token 遥测状态,拒绝隐式类型转换。"""

            if set(state) != {"pending_token_elements", "transform_fingerprint"}:
                raise ValueError("data telemetry callback state is incomplete or unknown")
            count = state["pending_token_elements"]
            transform = state["transform_fingerprint"]
            if type(count) is not int or count < 0:
                raise ValueError("pending token telemetry count must be non-negative")
            if transform is not None and (type(transform) is not str or not transform.strip()):
                raise ValueError("pending token telemetry transform must be text or None")
            if count and transform is None:
                raise ValueError("pending token telemetry count requires transform identity")

        def load_state_dict(self, state: Mapping[str, object]) -> None:
            """恢复 host 计数,后续微批仍在设备端继续累计。"""

            self.validate_state_dict(state)
            if self._pending_token_elements is not None:
                raise RuntimeError("cannot restore over live token telemetry")
            self._restored_token_elements = cast(int, state["pending_token_elements"])
            self._pending_transform_fingerprint = cast(
                str | None,
                state["transform_fingerprint"],
            )

        def on_step_end(self, state: TrainingState, output: TrainingStepOutput) -> None:
            """补入真实 data-wait 时间,并在日志周期边界执行归约。"""
            raw_wait = cast(object, output.metrics.get("data_wait_seconds", 0.0))
            if isinstance(raw_wait, bool) or not isinstance(raw_wait, (int, float)):
                raise TypeError("training data_wait_seconds must be numeric")
            skipped_reason = {
                StepStatus.SKIPPED: "optimizer_overflow",
                StepStatus.NONFINITE: "nonfinite_loss",
            }.get(output.status)
            record, token_count = telemetry_processor.take_record()
            self._accumulate_token_count(token_count, record.transform_fingerprint)
            logger.queue_data_telemetry(
                replace(
                    record,
                    data_wait_seconds=float(raw_wait),
                    skipped_by_reason=({} if skipped_reason is None else {skipped_reason: 1}),
                )
            )
            if state.global_step % config.telemetry.logging.log_every_steps == 0:
                self._queue_token_correction()
                logger.flush_data_telemetry(
                    self._session(),
                    reduce_across_ranks=training_plan.telemetry.reduce_across_ranks,
                )

        def on_fit_end(self, state: TrainingState) -> None:
            """正常有界停止时写出不足一个日志周期的剩余记录。"""
            del state
            if logger.has_pending_data_telemetry:
                self._queue_token_correction()
                logger.flush_data_telemetry(
                    self._session(),
                    reduce_across_ranks=training_plan.telemetry.reduce_across_ranks,
                )

    callbacks = (
        _DataTelemetryCallback(),
        LoggingCallback(logger, config.training.logging.log_every_steps),
        ProgressCallback(config.training.max_steps),
    )
    declared_data = {
        "decision": "NO_BACKEND_WINNER",
        "training_data_plan": training_plan.data.to_dict(),
    }
    checkpoint_root = Path(config.training.checkpoint.directory).expanduser().resolve()
    resume_from = config.training.checkpoint.resume_from
    resolved_resume = None if resume_from is None else Path(resume_from).expanduser().resolve()
    base_asset_provenance = None
    if prepared_assembly.base_asset_identity is not None:
        base_identity = prepared_assembly.base_asset_identity
        base_asset_provenance = BaseModelAssetProvenance(
            key=base_identity.key,
            revision=base_identity.revision,
            spec_identity_sha256=base_identity.spec_identity_sha256,
        ).to_dict()
    model_config_fingerprint = assembly_request.config.fingerprint
    planned_data_fingerprints = {
        "training_data_plan": training_plan.data.fingerprint,
        "planned_manifest": training_plan.data.manifest_fingerprint,
        **{
            f"planned_source:{index:04d}": fingerprint
            for index, fingerprint in enumerate(training_plan.data.source_fingerprints)
        },
    }
    manager = CheckpointManager(
        root=checkpoint_root,
        run_id=config.name,
        model_family=family.spec.family_key,
        autovla_version=autovla_version,
        git_commit=resolve_git_commit(Path(__file__).resolve().parents[2]),
        config=to_resolved_dict(config),
        config_fingerprint=checkpoint_compatibility_fingerprint(to_resolved_dict(config)),
        model_config_fingerprint=model_config_fingerprint,
        model_capability_fingerprint=stable_fingerprint(family.spec),
        checkpoint_adapter_name=(
            f"{type(checkpoint_adapter).__module__}.{type(checkpoint_adapter).__qualname__}"
        ),
        data_manifest=declared_data,
        data_fingerprints=planned_data_fingerprints,
        normalization={"selection": config.data.normalization},
        provenance={
            "model_source_status": family.spec.source_status,
            "architecture_variant": config.model.architecture_variant,
            "runtime_validation": verified_runtime.report.to_dict(),
            "model_runtime_identity": runtime_identity.to_dict(),
            "base_model_asset": base_asset_provenance,
            "training_plan": training_plan.to_dict(),
        },
        keep_last=config.training.checkpoint.keep_last,
        save_optimizer=config.training.checkpoint.save_optimizer,
    )
    context = TrainingContext(
        config=config.training,
        plan=training_plan,
        model=model,
        processor=telemetry_processor,
        data_module=data_module,
        strategy=strategy,
        checkpoint_manager=manager,
        family_checkpoint_adapter=checkpoint_adapter,
        metric_logger=logger,
        callbacks=callbacks,
        resume_from=resolved_resume,
        optimizer_factory=optimizer_factory,
        scheduler_factory=scheduler_factory,
    )
    context_holder.append(context)
    return TrainingEngine(context)


def main(argv: Sequence[str] | None = None) -> int:
    """加载配置、组合引擎并显式执行训练。"""
    args = build_parser().parse_args(argv)
    config = load_yaml(
        args.config,
        preset_root=args.preset_root,
        overrides=tuple(args.overrides),
    )
    try:
        engine = compose_training_engine(config)
    except OptionalDependencyError as exc:
        raise SystemExit(f"optional dependency error: {exc}") from exc
    engine.fit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
