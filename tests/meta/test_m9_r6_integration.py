"""验证 M9 R6 active/history 与规范注册收口。"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_default_packaged_preset_is_professional_gpu_only() -> None:
    """验证默认检查资源稳定解析单 GPU GR00T 架构。"""
    from autovla.cli.inspect_config import build_parser
    from autovla.config import load_yaml
    from autovla.config.resources import DEFAULT_EXPERIMENT, config_resource

    assert DEFAULT_EXPERIMENT == "pkg://experiments/m9_gr00t_gpu_architecture"
    assert build_parser().parse_args([]).config == DEFAULT_EXPERIMENT
    config = load_yaml(DEFAULT_EXPERIMENT)
    assert config.run.name == "m9_gr00t_gpu_architecture"
    assert config.model.registry_key == "gr00t_n1d6"
    assert (
        config.model.action_horizon,
        config.model.max_state_dim,
        config.model.max_action_dim,
    ) == (
        50,
        128,
        128,
    )
    assert config.topology.distributed.strategy_key == "single_gpu"
    assert config.topology.distributed.device == "cuda"
    for group, name in (
        ("experiments", "local_debug"),
        ("data", "local_debug"),
        ("models", "debug"),
    ):
        with pytest.raises(FileNotFoundError):
            config_resource(group, name)


def test_active_strategy_and_resource_surfaces_are_closed() -> None:
    """验证活动策略、资源和 launcher 只表达 M9 GPU 拓扑。"""
    from autovla.training.registry import build_training_strategy_registry

    assert set(build_training_strategy_registry().names()) == {
        "single_gpu",
        "distributed_data_parallel",
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
    }
    active_paths = (
        ROOT / "autovla/resources/configs",
        ROOT / "configs/data",
        ROOT / "configs/models",
        ROOT / "configs/topology",
        ROOT / "configs/distributed",
        ROOT / "configs/training",
        ROOT / "configs/experiments",
        ROOT / "scripts/runtime",
        ROOT / "scripts/slurm/m8_a100_architecture_smoke.sbatch",
        ROOT / "scripts/slurm/request_m8_a100_architecture_smoke.sh",
        ROOT / "docs/architecture/TRAINING_FRAMEWORK.md",
        ROOT / "docs/architecture/UPSTREAM_ARCHITECTURE_INTEGRATION.md",
    )
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in active_paths
        for path in ((root,) if root.is_file() else tuple(sorted(root.glob("*"))))
        if path.is_file()
    ).lower()
    assert all(token not in text for token in ("fsdp", "fully_sharded", "device: cpu"))
    assert "pkg://experiments/local_debug" not in text
    assert not tuple((ROOT / "configs/runtime").glob("m6*"))
    assert not tuple((ROOT / "configs/slurm").glob("m6*"))
    assert not tuple((ROOT / "scripts/runtime").glob("*m6*"))
    assert not tuple((ROOT / "scripts/slurm").glob("*m6*"))


def test_m6_and_duplicate_gr00t_surfaces_are_history_or_alias_only() -> None:
    """验证 M6 只留历史记录且 GR00T 兼容入口保持对象身份。"""
    from autovla.models.families.gr00t_n1d6.registration import (
        Gr00tN1d6Registration,
        registration,
    )
    from autovla.models.families.specification import ModelFamilyDefinition
    from autovla.models.registry import get_model_family_registration, get_model_family_spec

    assert (ROOT / "configs/history/m6_runtime/runtime-matrix.yaml").is_file()
    assert (ROOT / "scripts/history/m6_runtime/HISTORY.txt").is_file()
    assert (ROOT / "scripts/history/m7_runtime/m7_ddp_semlock_trace.sbatch").is_file()
    assert not (ROOT / "scripts/slurm/m7_ddp_semlock_trace.sbatch").exists()
    assert (ROOT / "docs/validation/M6_RUNTIME_VALIDATION_HISTORY.txt").is_file()
    assert Gr00tN1d6Registration is ModelFamilyDefinition
    assert registration() is get_model_family_spec("gr00t_n1d6")
    assert get_model_family_registration("gr00t_n1d6").spec is registration()
