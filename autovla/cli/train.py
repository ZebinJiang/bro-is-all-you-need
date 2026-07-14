"""AutoVLA 唯一生产训练组合根。"""

from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla import __version__ as autovla_version
from autovla.config import ExperimentConfig, load_yaml, to_resolved_dict
from autovla.core.registry import OptionalDependencyError
from autovla.training.checkpointing.identity import checkpoint_compatibility_fingerprint

if TYPE_CHECKING:
    import torch
    from torch import nn

    from autovla.assets import ResolvedModelAsset
    from autovla.models.interfaces import ModelProcessor
    from autovla.training.engine import TrainingEngine
    from autovla.training.optimization import ParameterRole
    from autovla.training.precision import PrecisionMode


@runtime_checkable
class _FamilyConfigLoader(Protocol):
    """约束模型 checkpoint 适配器的本地配置加载边界。"""

    def load_family_config(
        self,
        checkpoint_path: str | Path | ResolvedModelAsset,
        *,
        eagle_asset_path: str | Path | None = None,
    ) -> object:
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
    def model(self) -> nn.Module:
        """返回待运行时收窄的模型。"""

        ...

    @property
    def processor(self) -> ModelProcessor:
        """返回待运行时收窄的处理器。"""

        ...


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
    resolved_base_asset = None
    if config.model.architecture_variant == "official_n1d6" and config.model.asset_key:
        from autovla.assets import (
            DEFAULT_MODEL_ASSET_REGISTRY,
            ModelAssetResolver,
            ModelAssetStore,
        )

        # 先完成纯标准库本地验证;此路径不会调用 provider 或网络。
        resolved_base_asset = ModelAssetResolver(
            ModelAssetStore(config.assets.store.root),
            DEFAULT_MODEL_ASSET_REGISTRY,
        ).resolve(config.model.asset_key)
    _require_training_extra()

    from torch import nn
    from torch.optim import Optimizer

    from autovla.core.types.training import TrainingBatch
    from autovla.data.module import DataModule
    from autovla.data.registry import build_data_module_registry
    from autovla.models.interfaces import ModelProcessor
    from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
    from autovla.models.outputs import ActionPrediction, ModelInputBatch
    from autovla.models.registry import get_model_family_registration
    from autovla.training.callbacks import LoggingCallback, ProgressCallback
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
    from autovla.training.session import TrainingStrategy
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
    elif strategy_key == "deepspeed":
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

    family = get_model_family_registration(config.model.registry_key)
    if family.factory is None or family.checkpoint_adapter is None:
        raise ValueError(
            f"model family {family.spec.family_key!r} is specification-only and cannot train"
        )
    reduced_runtime = config.model.architecture_variant == "reduced_runtime"
    if config.model.registry_key != "gr00t_n1d6":
        raise ValueError("production training currently supports only gr00t_n1d6")
    checkpoint_adapter = family.checkpoint_adapter.create()
    if not isinstance(checkpoint_adapter, ModelCheckpointAdapter):
        raise TypeError("model checkpoint factory must return ModelCheckpointAdapter")
    if not isinstance(checkpoint_adapter, _FamilyConfigLoader):
        raise TypeError("model checkpoint adapter lacks load_family_config")
    from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config

    if reduced_runtime:
        if config.model.checkpoint_path is not None:
            raise ValueError("reduced_runtime random initialization requires checkpoint_path=null")
        if config.model.eagle_asset_path is None:
            from autovla.models.families.gr00t_n1d6.errors import LocalModelAssetError

            raise LocalModelAssetError(
                "eagle_asset_path",
                None,
                (
                    "config.json",
                    "preprocessor_config.json",
                    "processor_config.json",
                    "tokenizer_config.json",
                    "vocab.json",
                    "merges.txt",
                    "special_tokens_map.json",
                    "chat_template.json",
                ),
            )
        eagle_asset_path = Path(config.model.eagle_asset_path).expanduser()
        if not eagle_asset_path.is_absolute():
            from autovla.models.families.gr00t_n1d6.errors import LocalModelAssetError

            raise LocalModelAssetError(
                "eagle_asset_path",
                eagle_asset_path,
                ("absolute local Eagle asset directory",),
                detail="path must be absolute",
            )
        family_config = Gr00tN1d6Config.reduced_runtime(
            eagle_asset_path=str(eagle_asset_path.resolve(strict=False))
        )
    else:
        selected_path = (
            resolved_base_asset.root
            if resolved_base_asset is not None
            else Path(cast(str, config.model.checkpoint_path)).expanduser()
        )
        checkpoint_path = Path(selected_path).expanduser()
        if not checkpoint_path.is_absolute():
            from autovla.models.families.gr00t_n1d6.errors import LocalModelAssetError

            raise LocalModelAssetError(
                "checkpoint_path",
                checkpoint_path,
                ("absolute local checkpoint directory",),
                detail="path must be absolute",
            )
        checkpoint_path = checkpoint_path.resolve(strict=False)
        family_config = checkpoint_adapter.load_family_config(
            resolved_base_asset if resolved_base_asset is not None else checkpoint_path,
            eagle_asset_path=config.model.eagle_asset_path,
        )
        if (
            getattr(family_config, "architecture_variant", None)
            != config.model.architecture_variant
        ):
            raise ValueError(
                "checkpoint architecture_variant does not match requested model configuration"
            )
    model_factory = family.factory.create()
    if not isinstance(model_factory, _ModelFactory):
        raise TypeError("model factory must be callable")
    deepspeed_config = config.training.distributed.deepspeed
    partitioned_zero3 = (
        strategy_key == "deepspeed"
        and deepspeed_config is not None
        and deepspeed_config.zero_stage == 3
    )

    if partitioned_zero3:

        class _PartitionedComponents(nn.Module):
            """把完整组件构造延迟到 DeepSpeed ZeRO.Init 官方边界。"""

            _components: _ModelComponents | None = None

            def construct_model(self) -> nn.Module:
                """在策略拥有的分区上下文中构造模型并加载 checkpoint。"""

                if self._components is not None:
                    raise RuntimeError("partitioned model construction may run only once")
                value = model_factory(family_config)
                if not isinstance(value, _ModelComponents):
                    raise TypeError("model factory must return model and processor components")
                self._components = value
                return value.model

            def components(self) -> _ModelComponents:
                """返回已完成构造的模型组件。"""

                if self._components is None:
                    raise RuntimeError("partitioned model components are not constructed")
                return self._components

            def forward(self, *_args: object, **_kwargs: object) -> object:
                """禁止把构造请求误当成可执行模型。"""

                raise RuntimeError("partitioned construction request cannot execute forward")

        class _DeferredProcessor(ModelProcessor):
            """在 ZeRO-3 构造提交后转发到同一工厂产生的处理器。"""

            def __init__(self, request: _PartitionedComponents) -> None:
                """绑定唯一分区构造请求。"""

                self._request = request

            def prepare_batch(
                self,
                batch: TrainingBatch,
                *,
                device: torch.device,
                dtype: torch.dtype | None,
                training: bool,
            ) -> ModelInputBatch:
                """构造完成后转发规范 CPU 到 CUDA 张量准备。"""

                return self._request.components().processor.prepare_batch(
                    batch,
                    device=device,
                    dtype=dtype,
                    training=training,
                )

            def decode_actions(
                self,
                actions: torch.Tensor,
                *,
                batch: ModelInputBatch,
            ) -> ActionPrediction:
                """构造完成后转发物理动作解码。"""

                return self._request.components().processor.decode_actions(actions, batch=batch)

        construction = _PartitionedComponents()
        model = construction
        processor = _DeferredProcessor(construction)
    else:
        components = model_factory(family_config)
        if not isinstance(components, _ModelComponents):
            raise TypeError("model factory must return model and processor components")
        model = components.model
        processor = components.processor

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
    base_asset_provenance = None
    if resolved_base_asset is not None:
        base_asset_provenance = BaseModelAssetProvenance(
            key=resolved_base_asset.manifest.key,
            revision=resolved_base_asset.manifest.revision,
            spec_identity_sha256=resolved_base_asset.identity,
        ).to_dict()
    fingerprint_config = (
        replace(family_config, resolved_model_asset=None)
        if isinstance(family_config, Gr00tN1d6Config)
        else family_config
    )
    manager = CheckpointManager(
        root=checkpoint_root,
        run_id=config.name,
        model_family=family.spec.family_key,
        autovla_version=autovla_version,
        git_commit=resolve_git_commit(Path(__file__).resolve().parents[2]),
        config=to_resolved_dict(config),
        config_fingerprint=checkpoint_compatibility_fingerprint(to_resolved_dict(config)),
        model_config_fingerprint=stable_fingerprint(fingerprint_config),
        model_capability_fingerprint=stable_fingerprint(family.spec),
        checkpoint_adapter_name=(
            f"{type(checkpoint_adapter).__module__}.{type(checkpoint_adapter).__qualname__}"
        ),
        data_manifest=declared_data,
        data_fingerprints={"configured_data": config.data.name},
        normalization={"selection": config.data.normalization},
        provenance={
            "model_source_status": family.spec.source_status,
            "architecture_variant": config.model.architecture_variant,
            "runtime_validation": "deferred",
            "base_model_asset": base_asset_provenance,
        },
        keep_last=config.training.checkpoint.keep_last,
        save_optimizer=config.training.checkpoint.save_optimizer,
    )
    context = TrainingContext(
        config=config.training,
        model=model,
        processor=processor,
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
