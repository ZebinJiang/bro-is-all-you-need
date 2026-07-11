"""AutoVLA 唯一生产训练组合根。"""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla.config import ExperimentConfig, load_yaml, to_resolved_dict
from autovla.core.registry import OptionalDependencyError

if TYPE_CHECKING:
    from autovla.training.engine import TrainingEngine
    from autovla.training.optimization import ParameterRole
    from autovla.training.precision import PrecisionMode


@runtime_checkable
class _FamilyConfigLoader(Protocol):
    """约束模型 checkpoint 适配器的本地配置加载边界。"""

    def load_family_config(self, checkpoint_path: str | Path) -> object:
        """从显式本地 checkpoint 路径加载模型族配置。"""


@runtime_checkable
class _ModelFactory(Protocol):
    """约束注册模型工厂的调用边界。"""

    def __call__(self, config: object, /) -> object:
        """根据模型族配置构造待验证的组件对象。"""


@runtime_checkable
class _ModelComponents(Protocol):
    """约束模型工厂结果必须暴露模型与处理器。"""

    @property
    def model(self) -> object:
        """返回待运行时收窄的模型。"""

    @property
    def processor(self) -> object:
        """返回待运行时收窄的处理器。"""


def build_parser() -> argparse.ArgumentParser:
    """构造生产训练参数解析器。"""
    parser = argparse.ArgumentParser(prog="autovla-train")
    parser.add_argument("config", help="本地实验 YAML 路径")
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
    for name, parameter in model.named_parameters():
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
    _require_training_extra()

    from torch import nn
    from torch.optim import Optimizer

    from autovla.data.module import DataModule
    from autovla.data.registry import build_data_module_registry
    from autovla.models.interfaces import ModelProcessor
    from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
    from autovla.models.registry import get_model_family_registration
    from autovla.training.callbacks import LoggingCallback, ProgressCallback
    from autovla.training.checkpointing import CheckpointManager
    from autovla.training.context import TrainingContext
    from autovla.training.engine import TrainingEngine
    from autovla.training.optimization import (
        calculate_total_optimizer_steps,
        create_adamw,
        create_scheduler,
    )
    from autovla.training.precision import PrecisionPolicy
    from autovla.training.registry import build_training_strategy_registry
    from autovla.training.strategy.base import TrainingStrategy
    from autovla.training.telemetry.logger import MetricLogger

    family = get_model_family_registration(config.model.registry_key)
    if family.factory is None or family.checkpoint_adapter is None:
        raise ValueError(
            f"model family {family.spec.family_key!r} is specification-only and cannot train"
        )
    if config.model.checkpoint_path is None:
        raise ValueError(
            "GR00T N1.6.1 requires an explicit local model.checkpoint_path; "
            "no asset or checkpoint is downloaded or selected by default"
        )
    checkpoint_adapter = family.checkpoint_adapter.create()
    if not isinstance(checkpoint_adapter, ModelCheckpointAdapter):
        raise TypeError("model checkpoint factory must return ModelCheckpointAdapter")
    if not isinstance(checkpoint_adapter, _FamilyConfigLoader):
        raise TypeError("model checkpoint adapter lacks load_family_config")
    checkpoint_path = Path(config.model.checkpoint_path).expanduser().resolve()
    family_config = checkpoint_adapter.load_family_config(checkpoint_path)
    model_factory = family.factory.create()
    if not isinstance(model_factory, _ModelFactory):
        raise TypeError("model factory must be callable")
    components = model_factory(family_config)
    if not isinstance(components, _ModelComponents):
        raise TypeError("model factory must return model and processor components")

    data_factory = build_data_module_registry().get("standard")
    data_module = data_factory.create(config.data)
    if not isinstance(data_module, DataModule):
        raise TypeError("standard data factory must return DataModule")
    precision = PrecisionPolicy(cast("PrecisionMode", config.training.precision.mode))
    strategy_entry = build_training_strategy_registry().get(
        config.training.distributed.strategy_key
    )
    strategy_factory = strategy_entry.factory.load()
    strategy_kwargs: dict[str, object] = {}
    if config.training.distributed.strategy_key == "distributed_data_parallel":
        strategy_kwargs.update(
            expected_world_size=config.training.distributed.world_size,
            gradient_as_bucket_view=config.training.distributed.gradient_as_bucket_view,
            find_unused_parameters=config.training.distributed.find_unused_parameters,
        )
    elif config.training.distributed.strategy_key == "fully_sharded_data_parallel":
        strategy_kwargs["expected_world_size"] = config.training.distributed.world_size
        strategy_kwargs["reshard_after_forward"] = (
            config.training.distributed.fsdp_reshard_after_forward
        )
    strategy = strategy_factory(precision, **strategy_kwargs)
    if not isinstance(strategy, TrainingStrategy):
        raise TypeError("training strategy factory must return TrainingStrategy")

    model = components.model
    processor = components.processor
    if not isinstance(processor, ModelProcessor):
        raise TypeError("model factory processor must implement ModelProcessor")

    def optimizer_factory(prepared_model: object):
        """针对策略准备后的规范参数身份创建优化器。"""

        if not isinstance(prepared_model, nn.Module):
            raise TypeError("prepared model must be a torch.nn.Module")
        return create_adamw(
            prepared_model,
            _parameter_roles(prepared_model),
            config.training.optimization,
        )

    def scheduler_factory(optimizer: object, batches_per_epoch: int):
        """按真实每 rank loader 长度创建学习率调度器。"""

        if not isinstance(optimizer, Optimizer):
            raise TypeError("scheduler optimizer must be torch.optim.Optimizer")
        calculated = calculate_total_optimizer_steps(
            batches_per_epoch=batches_per_epoch,
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
    callbacks = (
        LoggingCallback(logger, config.training.logging.log_every_steps),
        ProgressCallback(config.training.max_steps),
    )
    declared_data = {
        "decision": "NO_BACKEND_WINNER",
        "config": asdict(config.data),
    }
    checkpoint_root = Path(config.training.checkpoint.directory).expanduser().resolve()
    resume_from = config.training.checkpoint.resume_from
    resolved_resume = None if resume_from is None else Path(resume_from).expanduser().resolve()
    manager = CheckpointManager(
        root=checkpoint_root,
        run_id=config.name,
        model_family=family.spec.family_key,
        config=to_resolved_dict(config),
        config_fingerprint=config.fingerprint,
        data_manifest=declared_data,
        data_fingerprints={"configured_data": config.data.name},
        normalization={"selection": config.data.normalization},
        provenance={
            "model_source_status": family.spec.source_status,
            "runtime_validation": "deferred",
        },
        keep_last=config.training.checkpoint.keep_last,
        save_optimizer=config.training.checkpoint.save_optimizer,
    )
    context = TrainingContext(
        config=config.training,
        model=model,
        processor=processor,
        data_module=data_module,
        optimizer=None,
        scheduler=None,
        strategy=strategy,
        checkpoint_manager=manager,
        family_checkpoint_adapter=checkpoint_adapter,
        metric_logger=logger,
        callbacks=callbacks,
        resume_from=resolved_resume,
        optimizer_factory=optimizer_factory,
        scheduler_factory=scheduler_factory,
    )
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
