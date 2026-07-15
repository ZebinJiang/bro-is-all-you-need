"""R5 十一组配置和活动注册键契约。"""

import subprocess
from pathlib import Path

import pytest

from autovla.config.errors import UnknownConfigurationFieldError
from autovla.config.loader.validate import build_experiment_config
from autovla.data.registry import build_data_backend_registry
from autovla.training.registry import build_training_strategy_registry


def test_config_groups_fingerprint_and_unknown_keys() -> None:
    """canonical 配置只导出十一组, 覆盖和指纹保持确定。"""
    payload = {
        "run": {"name": "m9", "seed": 11, "output_dir": "runs/local/m9"},
        "topology": {
            "distributed": {
                "strategy_key": "deepspeed_zero_2",
                "world_size": 2,
                "device": "cuda",
                "deepspeed": {"zero_stage": 2},
            },
            "precision": {"mode": "bfloat16"},
        },
    }
    first = build_experiment_config(payload)
    second = build_experiment_config(dict(reversed(tuple(payload.items()))))
    assert first.fingerprint == second.fingerprint
    assert tuple(first.to_resolved_dict()) == (
        "schema_version",
        "run",
        "data",
        "model",
        "transforms",
        "topology",
        "training",
        "optimization",
        "checkpoint",
        "telemetry",
        "inference",
        "deployment",
    )
    assert first.training.distributed is first.topology.distributed
    assert first.training.optimization is first.optimization
    with pytest.raises(UnknownConfigurationFieldError):
        build_experiment_config({"run": {"name": "m9", "mystery": 1}})


def test_production_registry_keys_are_professional_and_import_light() -> None:
    """活动数据/策略键无临时、CPU 或 FSDP 名称。"""
    data_keys = set(build_data_backend_registry().names())
    strategy_keys = set(build_training_strategy_registry().names())
    assert data_keys == {"lerobot_local", "robodm_container", "webdataset"}
    assert strategy_keys == {
        "single_gpu",
        "distributed_data_parallel",
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
    }
    text = " ".join(sorted(data_keys | strategy_keys)).lower()
    assert all(token not in text for token in ("roadmap", "metadata", "skeleton", "test_double"))


def test_lerobot_root_and_packaged_presets_share_canonical_dispatch_identity() -> None:
    """root 单后端与 package 数据集形式均严格派发到 lerobot_local。"""
    from autovla.config import load_yaml
    from autovla.config.schema.data import ACTIVE_DATA_BACKEND_KEYS, DataConfig, DatasetConfig

    root = load_yaml("configs/data/lerobot_local.yaml")
    packaged = load_yaml("pkg://data/lerobot_local")

    assert root.data.backend_identities == packaged.data.backend_identities == ("lerobot_local",)
    assert frozenset(build_data_backend_registry().names()) == ACTIVE_DATA_BACKEND_KEYS
    assert DatasetConfig("legacy", "lerobot_v3_local", "datasets/working/legacy").backend == (
        "lerobot_local"
    )
    with pytest.raises(ValueError, match=r"unknown data\.backend"):
        DataConfig(backend="implicit_default")
    with pytest.raises(ValueError, match=r"unknown dataset\.backend"):
        DatasetConfig("unknown", "winner", "datasets/working/unknown")


def test_active_configs_and_git_contain_no_training_assets_cpu_or_fsdp() -> None:
    """活动配置无 CPU/FSDP, 且模型资产不进入 Git 或包目录。"""
    root = Path(__file__).resolve().parents[2]
    active_roots = (
        root / "configs/data",
        root / "configs/models",
        root / "configs/topology",
        root / "configs/distributed",
        root / "configs/training",
        root / "configs/experiments",
    )
    active_text = "\n".join(
        path.read_text(encoding="utf-8")
        for directory in active_roots
        for path in directory.glob("*.yaml")
    ).lower()
    assert all(token not in active_text for token in ("fsdp", "fully_sharded", "device: cpu"))

    tracked = subprocess.run(
        (
            "git",
            "ls-files",
            "base_model/**",
            "datasets/**",
            "checkpoints/**",
            "*.pt",
            "*.pth",
            "*.safetensors",
            "*.ckpt",
        ),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    staged = subprocess.run(
        ("git", "diff", "--cached", "--name-only"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    package_assets = tuple(
        path
        for suffix in ("*.pt", "*.pth", "*.safetensors", "*.ckpt")
        for path in (root / "autovla").rglob(suffix)
    )
    assert not tracked.stdout.strip()
    assert not staged.stdout.strip()
    assert not package_assets
