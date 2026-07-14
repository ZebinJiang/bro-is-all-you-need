"""GPU-only 分布式与 DeepSpeed 配置契约测试。"""

import json

import pytest


class _IntSubclass(int):
    """提供必须被严格整数边界拒绝的测试值。"""


def test_deepspeed_config_is_deterministic_and_serializable() -> None:
    """验证 AutoVLA 生成稳定且批大小一致的 ZeRO-3 字典。"""

    from autovla.config.schema.distributed import DeepSpeedConfig

    config = DeepSpeedConfig(zero_stage=3)
    first = config.to_deepspeed_dict(
        micro_batch_size_per_gpu=2,
        gradient_accumulation_steps=4,
        data_parallel_world_size=8,
        gradient_clipping=1.0,
    )
    second = config.to_deepspeed_dict(
        micro_batch_size_per_gpu=2,
        gradient_accumulation_steps=4,
        data_parallel_world_size=8,
        gradient_clipping=1.0,
    )

    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["train_batch_size"] == 64
    assert first["zero_optimization"]["stage"] == 3
    assert "offload_optimizer" not in first["zero_optimization"]
    assert "offload_param" not in first["zero_optimization"]


@pytest.mark.parametrize(
    "kwargs",
    (
        {"zero_stage": 0},
        {"zero_stage": 4},
        {"zero_stage": True},
        {"zero_stage": _IntSubclass(2)},
        {"bf16_enabled": True, "fp16_enabled": True},
        {"bf16_enabled": False, "fp16_enabled": False},
        {"zero_stage": 2, "stage3_max_live_parameters": 1000},
    ),
)
def test_deepspeed_config_rejects_conflicting_fields(kwargs: dict[str, object]) -> None:
    """验证非法 stage、精度和 stage-3 专属字段 fail closed。"""

    from autovla.config.schema.distributed import DeepSpeedConfig

    with pytest.raises(ValueError):
        DeepSpeedConfig(**kwargs)


def test_gpu_strategy_aliases_and_removed_backends_are_explicit() -> None:
    """验证窄别名告警且 CPU/FSDP 不会恢复为生产路径。"""

    from autovla.config.schema.distributed import DistributedConfig

    with pytest.warns(DeprecationWarning, match="single_gpu"):
        assert DistributedConfig(strategy_key="single_device").strategy_key == "single_gpu"
    with pytest.warns(DeprecationWarning, match="distributed_data_parallel"):
        config = DistributedConfig(strategy_key="ddp", world_size=2)
        assert config.strategy_key == "distributed_data_parallel"
        assert config.deepspeed is None
    with pytest.raises(ValueError, match="CUDA-only"):
        DistributedConfig(device="cpu")
    with pytest.raises(ValueError, match="zero_stage=3"):
        DistributedConfig(strategy_key="fsdp2", world_size=2)


def test_deepspeed_section_is_required_only_for_deepspeed_strategy() -> None:
    """验证 typed DeepSpeed 段不会泄漏到 native 解析结果。"""

    from autovla.config.loader.validate import build_experiment_config
    from autovla.config.schema.distributed import DeepSpeedConfig, DistributedConfig

    assert DistributedConfig().deepspeed is None
    with pytest.raises(ValueError, match=r"requires training\.distributed\.deepspeed"):
        DistributedConfig(strategy_key="deepspeed", world_size=2)
    with pytest.raises(ValueError, match="allowed only"):
        DistributedConfig(deepspeed=DeepSpeedConfig())

    deepspeed = DeepSpeedConfig(zero_stage=3)
    configured = DistributedConfig(
        strategy_key="deepspeed",
        world_size=2,
        deepspeed=deepspeed,
    )
    assert configured.deepspeed is deepspeed

    resolved = build_experiment_config({}).to_resolved_dict()
    serialized = json.dumps(resolved, sort_keys=True)
    assert '"deepspeed": null' in serialized
    assert '"zero_stage"' not in serialized


def test_loader_rejects_missing_or_forbidden_deepspeed_sections() -> None:
    """验证 loader 对 DeepSpeed 段和策略选择执行双向约束。"""

    from autovla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"requires training\.distributed\.deepspeed"):
        build_experiment_config(
            {"training": {"distributed": {"strategy_key": "deepspeed", "world_size": 2}}}
        )
    with pytest.raises(ValueError, match="allowed only"):
        build_experiment_config({"training": {"distributed": {"deepspeed": {"zero_stage": 2}}}})


def test_legacy_runner_backends_are_parse_only_and_actionable() -> None:
    """验证 Accelerate/FSDP 可解析但不能映射到生产策略。"""

    from autovla.config.loader.validate import build_experiment_config
    from autovla.config.schema.runner import RunnerBackend

    assert RunnerBackend.ACCELERATE.value == "accelerate"
    assert RunnerBackend.FSDP.value == "fsdp"
    with pytest.raises(ValueError, match="Accelerate production runtime"):
        build_experiment_config({"runner": {"backend": "accelerate"}})
    with pytest.raises(ValueError, match=r"deepspeed.*zero_stage=3"):
        build_experiment_config({"runner": {"backend": "fsdp"}})


def test_loader_rejects_unknown_and_precision_conflicts() -> None:
    """验证 DeepSpeed 配置无高级透传且精度事实来源一致。"""

    from autovla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match="unknown config key"):
        build_experiment_config(
            {
                "training": {
                    "distributed": {
                        "strategy_key": "deepspeed",
                        "world_size": 2,
                        "deepspeed": {"zero_stage": 2, "pipeline_parallel_size": 2},
                    }
                }
            }
        )
    with pytest.raises(ValueError, match="invalid value"):
        build_experiment_config(
            {
                "training": {
                    "distributed": {
                        "strategy_key": "deepspeed",
                        "world_size": 2,
                        "deepspeed": {
                            "zero_stage": 2,
                            "bf16_enabled": False,
                            "fp16_enabled": True,
                        },
                    },
                    "precision": {"mode": "bfloat16"},
                }
            }
        )


@pytest.mark.parametrize("strategy_key", ("distributed_data_parallel", "deepspeed"))
def test_distributed_production_precision_is_bf16_only(strategy_key: str) -> None:
    """DDP 与 DeepSpeed 均在 typed composition 阶段拒绝 FP16/FP32。"""

    from autovla.config.loader.validate import build_experiment_config

    distributed: dict[str, object] = {"strategy_key": strategy_key, "world_size": 2}
    if strategy_key == "deepspeed":
        distributed["deepspeed"] = {"zero_stage": 2}
    with pytest.raises(ValueError, match="precision"):
        build_experiment_config(
            {
                "training": {
                    "distributed": distributed,
                    "precision": {"mode": "float16"},
                }
            }
        )

    from autovla.config.schema.distributed import DeepSpeedConfig

    if strategy_key == "deepspeed":
        with pytest.raises(ValueError, match="bf16_enabled=true"):
            DeepSpeedConfig(bf16_enabled=False, fp16_enabled=True)


def test_a100_experiments_compose_layers_and_global_batch() -> None:
    """验证 A100 profile 与策略 preset 分层组合且 batch 公式唯一。"""

    from autovla.config import load_yaml

    single = load_yaml("configs/experiments/gr00t_n1d6_webdataset.yaml")
    zero3 = load_yaml(
        "configs/experiments/gr00t_n1d6_webdataset_zero3.yaml",
        overrides=("training.distributed.world_size=4",),
    )

    assert single.environment.gpu_architecture == "a100"
    assert single.environment.distributed_backend == "nccl"
    assert single.environment.hf_hub_offline is True
    assert single.environment.slurm_partition == "a100"
    assert single.environment.cpus_per_gpu == 8
    assert single.environment.memory_request_convention == "per_node"
    assert single.environment.memory_gib_per_gpu == 64
    assert single.environment.deepspeed_profile == "training-deepspeed"
    assert single.environment.runtime_fingerprint_status == (
        "locks_and_fingerprints_collected_runtime_deferred"
    )
    assert (
        single.environment.declared_environment_status
        == "locked_profiles_bounded_pre_cuda_validation_only"
    )
    assert single.assets.store.root == "/home/cz-jzb/workspace/vla-flywheel/base_model"
    assert "asset_manifest_identity" in single.environment.environment_fingerprint_inputs
    assert "safetensors_version" in single.environment.environment_fingerprint_inputs
    assert "huggingface_hub_version" in single.environment.environment_fingerprint_inputs
    assert single.training.distributed.strategy_key == "single_gpu"
    assert zero3.training.distributed.strategy_key == "deepspeed"
    assert zero3.training.distributed.deepspeed is not None
    assert zero3.training.distributed.deepspeed.zero_stage == 3
    assert zero3.global_batch_size == (
        zero3.data.loader.batch_size
        * zero3.training.gradient_accumulation_steps
        * zero3.training.distributed.world_size
    )


def test_m8_defaulted_training_leaves_accept_strict_overrides() -> None:
    """验证 M8 四个默认叶可同时覆盖,未知拼写仍 fail closed。"""

    from autovla.config import load_yaml
    from autovla.config.errors import ConfigurationOverrideError

    experiment = "configs/experiments/gr00t_n1d6_webdataset_zero3.yaml"
    config = load_yaml(
        experiment,
        overrides=(
            "training.max_steps=2",
            "training.distributed.world_size=2",
            "training.checkpoint.directory=runs/tmp/wave8-proof/checkpoints",
            "training.logging.jsonl_path=runs/tmp/wave8-proof/metrics.jsonl",
        ),
    )

    assert config.training.max_steps == 2
    assert config.training.distributed.world_size == 2
    assert config.training.checkpoint.directory == "runs/tmp/wave8-proof/checkpoints"
    assert config.training.logging.jsonl_path == "runs/tmp/wave8-proof/metrics.jsonl"

    with pytest.raises(
        ConfigurationOverrideError,
        match=(
            r"unknown config key: training\.checkpoint\.directry; "
            r"did you mean training\.checkpoint\.directory"
        ),
    ):
        load_yaml(
            experiment,
            overrides=("training.checkpoint.directry=runs/tmp/wave8-proof/typo",),
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"slurm_partition": "gpu"},
        {"cpus_per_gpu": 0},
        {"cpus_per_gpu": True},
        {"memory_request_convention": "per_gpu"},
        {"memory_gib_per_gpu": 0},
        {"deepspeed_profile": "all-model-zoo"},
        {"environment_fingerprint_schema": "unversioned"},
        {"environment_fingerprint_inputs": ("source_sha",)},
        {"runtime_fingerprint_status": "collected"},
        {"declared_environment_status": "installed"},
    ),
)
def test_a100_environment_contract_rejects_undeclared_runtime_claims(
    changes: dict[str, object],
) -> None:
    """验证资源约束和 Wave 8 指纹状态使用闭集且不伪造安装事实。"""

    from autovla.config.schema.environment import EnvironmentConfig

    with pytest.raises(ValueError):
        EnvironmentConfig(**changes)


def test_single_device_remains_source_alias_not_active_preset() -> None:
    """验证迁移 alias 存在,但本地与包内 active preset 均已退休。"""

    from pathlib import Path

    from autovla.config.schema.distributed import DistributedConfig

    with pytest.warns(DeprecationWarning, match="single_gpu"):
        assert DistributedConfig(strategy_key="single_device").strategy_key == "single_gpu"
    assert not Path("configs/training/single_device.yaml").exists()
    assert not Path("autovla/resources/configs/training/single_device.yaml").exists()
