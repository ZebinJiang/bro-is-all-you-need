"""Slurm harness plan 的纯函数边界测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.training.slurm_harness import (
    SLURM_HARNESS_MANIFEST_FILENAME,
    SLURM_HARNESS_PLAN_FILENAME,
    SlurmHarnessConfig,
    build_slurm_harness_plan,
    run_slurm_harness,
)


def _microloop_config(tmp_path: Path) -> Path:
    """写入严格 microloop dry-run 配置。"""
    path = tmp_path / "microloop.json"
    payload = {
        "action_dim": 3,
        "action_horizon": 2,
        "dataset_fingerprint": "dataset-slurm",
        "max_steps": 2,
        "mode": "dry-run",
        "model_registry_key": "deterministic.action.framework",
        "output_dir": str(tmp_path / "config-output"),
        "run_id": "slurm_microloop",
        "seed": 11,
        "statistics_fingerprint": "stats-slurm",
        "transform_fingerprint": "transform-slurm",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _slurm_config(tmp_path: Path, **overrides: object) -> Path:
    """写入最小安全 Slurm sandbox 配置。"""
    path = tmp_path / "slurm.json"
    payload: dict[str, object] = {
        "approved_cluster": "cz_hpc01",
        "cpus_per_task": 16,
        "gres": "none",
        "max_minutes": 30,
        "mem": "64G",
        "nodes": 1,
        "ntasks": 1,
        "partition": "a100",
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _config(tmp_path: Path, *, action: str = "render") -> SlurmHarnessConfig:
    """构造 harness 配置对象。"""
    return SlurmHarnessConfig(
        action=action,
        microloop_config_path=_microloop_config(tmp_path),
        output_dir=tmp_path / "out",
        run_id="slurm-smoke-001",
        slurm_config_path=_slurm_config(tmp_path),
    )


def test_build_plan_should_render_deterministic_safe_microloop_command(tmp_path: Path) -> None:
    """验证 plan 稳定且只组合 CPU microloop 命令。"""
    config = _config(tmp_path)

    first = build_slurm_harness_plan(config)
    second = build_slurm_harness_plan(config)

    assert first.to_json_dict() == second.to_json_dict()
    data = first.to_json_dict()
    assert data["schema_version"] == "m3-slurm-training-harness-plan.v1"
    assert data["package_name"] == "autovla"
    assert data["mode"] == "slurm-harness"
    assert data["action"] == "render"
    assert data["real_training"] is False
    assert data["gpu_compute"] is False
    assert data["dataset_fingerprint"] == "dataset-slurm"
    assert data["transform_fingerprint"] == "transform-slurm"
    assert data["statistics_fingerprint"] == "stats-slurm"
    assert (
        len(
            {
                data["dataset_fingerprint"],
                data["transform_fingerprint"],
                data["statistics_fingerprint"],
            }
        )
        == 3
    )
    assert data["submission_mode"] == "sbatch_for_harness_smoke"
    assert data["slurm_job_name"] == "autovla-slurm-smoke-001"
    assert data["gpus_expected_for_test"] == 0
    assert all(value is False for value in cast(dict[str, bool], data["external_effects"]).values())
    assert "genesisvla" not in json.dumps(data)

    command_argv = cast(list[str], data["command_argv"])
    microloop_argv = cast(list[str], data["microloop_command_argv"])
    assert command_argv[0] == "scripts/slurm/submit_autovla_microloop_smoke.sh"
    assert command_argv[1] == "--script"
    assert command_argv[2].endswith("autovla_microloop_smoke.sbatch")
    assert microloop_argv[0] == sys.executable
    assert microloop_argv[0] != "python"
    assert Path(microloop_argv[0]).name.startswith("python")
    assert microloop_argv == [
        sys.executable,
        "-m",
        "autovla.training.cli",
        "microloop",
        "--config",
        str(config.microloop_config_path),
        "--output-dir",
        str(config.output_dir / config.run_id / "microloop"),
        "--require-compute-node",
    ]


def test_render_and_validate_should_not_invoke_subprocess(tmp_path: Path) -> None:
    """验证 render/validate 不触碰 Slurm wrapper。"""

    def _forbidden_runner(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        """如果 render/validate 调用子进程则失败。"""
        del args, check, capture_output, text, timeout
        raise AssertionError("render/validate must not invoke subprocess")

    for action in ("render", "validate"):
        result = run_slurm_harness(_config(tmp_path, action=action), runner=_forbidden_runner)
        assert result.plan_path == (
            tmp_path / "out" / "slurm-smoke-001" / SLURM_HARNESS_PLAN_FILENAME
        )
        assert (
            result.manifest_path
            == tmp_path / "out" / "slurm-smoke-001" / SLURM_HARNESS_MANIFEST_FILENAME
        )
        assert result.manifest.submit_attempted is False
        assert result.manifest.submitted_job_id is None
        manifest = result.manifest.to_json_dict()
        assert manifest["dataset_fingerprint"] == "dataset-slurm"
        assert manifest["transform_fingerprint"] == "transform-slurm"
        assert manifest["statistics_fingerprint"] == "stats-slurm"
        assert (
            len(
                {
                    manifest["dataset_fingerprint"],
                    manifest["transform_fingerprint"],
                    manifest["statistics_fingerprint"],
                }
            )
            == 3
        )


def test_submit_should_construct_list_argv_without_shell(tmp_path: Path) -> None:
    """验证 submit 只用 list argv 调用 sbatch wrapper 并解析可选 job id。"""
    calls: list[list[str]] = []

    def _fake_runner(
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        """模拟 wrapper 成功提交。"""
        assert check is False
        assert capture_output is True
        assert text is True
        assert timeout == 30
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Submitted batch job 12345\n",
        )

    result = run_slurm_harness(_config(tmp_path, action="submit"), runner=_fake_runner)

    assert len(calls) == 1
    assert calls[0][0] == "scripts/slurm/submit_autovla_microloop_smoke.sh"
    assert calls[0][1] == "--script"
    assert calls[0][2].endswith("autovla_microloop_smoke.sbatch")
    assert result.manifest.submit_attempted is True
    assert result.manifest.subprocess_returncode == 0
    assert result.manifest.submitted_job_id == "12345"
    manifest = result.manifest.to_json_dict()
    assert manifest["submission_mode"] == "sbatch_for_harness_smoke"
    assert manifest["dataset_fingerprint"] == "dataset-slurm"
    assert manifest["transform_fingerprint"] == "transform-slurm"
    assert manifest["statistics_fingerprint"] == "stats-slurm"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("partition", "a100;rm", "unsafe"),
        ("partition", "TO_FILL", "TO_FILL"),
        ("nodes", 2, "nodes"),
        ("ntasks", 2, "ntasks"),
        ("cpus_per_task", 17, "cpus_per_task"),
        ("mem", "128G", "mem"),
        ("max_minutes", 31, "max_minutes"),
        ("gres", "gpu:1", "gres"),
        ("notes", "wandb upload", "external-effect"),
    ),
)
def test_build_plan_should_reject_unsafe_or_finetune_scale_resources(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    """验证 harness 不接受超出 CPU smoke 的资源或外部效果配置。"""
    config = SlurmHarnessConfig(
        action="render",
        microloop_config_path=_microloop_config(tmp_path),
        output_dir=tmp_path / "out",
        run_id="slurm-smoke-001",
        slurm_config_path=_slurm_config(tmp_path, **{field: value}),
    )

    with pytest.raises(ValueError, match=message):
        build_slurm_harness_plan(config)


def test_build_plan_should_reject_shell_injection_run_id(tmp_path: Path) -> None:
    """验证 run_id 不允许 shell 元字符或路径分隔符。"""
    config = SlurmHarnessConfig(
        action="render",
        microloop_config_path=_microloop_config(tmp_path),
        output_dir=tmp_path / "out",
        run_id="bad;id",
        slurm_config_path=_slurm_config(tmp_path),
    )

    with pytest.raises(ValueError, match="run_id"):
        build_slurm_harness_plan(config)
