"""生产运行时依赖无关的配置和身份行为测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from autovla.config.loader.validate import build_experiment_config
from autovla.config.resources import config_resource
from autovla.training.checkpointing.identity import resolve_git_commit, stable_fingerprint


def test_reduced_config_requires_explicit_local_eagle_assets() -> None:
    """reduced 配置必须显式给出本地 Eagle 路径且禁止 checkpoint。"""

    base = {
        "schema_version": "1.0",
        "name": "reduced-validation-only",
        "model": {
            "schema_version": "1.0",
            "name": "GR00T reduced validation only",
            "registry_key": "gr00t_n1d6",
            "architecture_variant": "reduced_runtime",
            "local_files_only": True,
        },
        "data": {
            "schema_version": "1.0",
            "name": "data",
            "root": "datasets/working/local",
            "required_modalities": ["camera.rgb_0"],
        },
    }
    with pytest.raises(ValueError, match="eagle_asset_path"):
        build_experiment_config(base)
    base["model"]["eagle_asset_path"] = "/tmp/autovla-validation-only/eagle"
    base["model"]["checkpoint_path"] = "/tmp/forbidden-checkpoint"
    with pytest.raises(ValueError, match=r"forbids model\.checkpoint_path"):
        build_experiment_config(base)


def test_reduced_runtime_is_not_a_packaged_model_preset() -> None:
    """包资源不得把 smoke/validation reduced 模型暴露为生产默认。"""

    with pytest.raises(FileNotFoundError):
        config_resource("models", "gr00t_n1d6_reduced_runtime")


def test_checkpoint_identity_is_stable_and_uses_full_git_commit() -> None:
    """配置指纹与本地 Git 身份必须精确可重放。"""

    first = stable_fingerprint({"b": [2, 3], "a": {"x": True}})
    second = stable_fingerprint({"a": {"x": True}, "b": (2, 3)})
    assert first == second
    commit = resolve_git_commit(Path(__file__).parents[2])
    assert len(commit) == 40
    assert all(character in "0123456789abcdef" for character in commit)


def test_distributed_device_is_strict_and_affects_resolved_identity() -> None:
    """规范配置显式区分 CPU/CUDA 且拒绝未知设备。"""
    cpu = build_experiment_config({"training": {"distributed": {"device": "cpu"}}})
    cuda = build_experiment_config({"training": {"distributed": {"device": "cuda"}}})
    assert cpu.training.distributed.device == "cpu"
    assert cuda.training.distributed.device == "cuda"
    assert cpu.runner.device == "cpu"
    assert cuda.runner.device == "cuda"
    assert cpu.fingerprint != cuda.fingerprint
    with pytest.raises(ValueError, match=r"training\.distributed\.device"):
        build_experiment_config({"training": {"distributed": {"device": "auto"}}})
