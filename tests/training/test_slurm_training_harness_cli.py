"""Slurm harness CLI 的入口与边界测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast


def _write_json(path: Path, payload: Mapping[str, object]) -> Path:
    """写入稳定 JSON。"""
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _microloop_config(tmp_path: Path) -> Path:
    """写入可供 harness 引用的 microloop 配置。"""
    return _write_json(
        tmp_path / "microloop.json",
        {
            "action_dim": 3,
            "action_horizon": 2,
            "dataset_fingerprint": "dataset-slurm-cli",
            "max_steps": 2,
            "mode": "dry-run",
            "model_registry_key": "deterministic.action.framework",
            "output_dir": str(tmp_path / "config-output"),
            "run_id": "slurm_cli_microloop",
            "seed": 13,
            "statistics_fingerprint": "stats-slurm-cli",
            "transform_fingerprint": "transform-slurm-cli",
        },
    )


def _slurm_config(tmp_path: Path, **overrides: object) -> Path:
    """写入安全 Slurm 配置。"""
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
    return _write_json(tmp_path / "slurm.json", payload)


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """通过模块入口运行 Training CLI。"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.cli", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
        env=env,
    )


def _harness_args(tmp_path: Path, action: str, output_dir: Path) -> list[str]:
    """构造 canonical slurm-harness CLI 参数。"""
    return [
        "slurm-harness",
        action,
        "--microloop-config",
        str(_microloop_config(tmp_path)),
        "--slurm-config",
        str(_slurm_config(tmp_path)),
        "--run-id",
        "slurm-cli-001",
        "--output-dir",
        str(output_dir),
    ]


def test_cli_help_should_show_slurm_harness_without_removing_existing_commands(
    tmp_path: Path,
) -> None:
    """验证顶层 help 公开 slurm-harness 且保留已有命令。"""
    result = _run_cli(["--help"], cwd=tmp_path)

    assert result.returncode == 0
    assert "slurm-harness" in result.stdout
    assert "microloop" in result.stdout
    assert "readiness" in result.stdout
    assert "--local-smoke" in result.stdout
    assert "real training" not in result.stdout.lower()


def test_cli_slurm_harness_render_should_write_deterministic_plan_and_manifest(
    tmp_path: Path,
) -> None:
    """验证 render 只写 deterministic JSON plan/manifest。"""
    output_dir = tmp_path / "out"

    first = _run_cli(_harness_args(tmp_path, "render", output_dir), cwd=tmp_path)
    second = _run_cli(_harness_args(tmp_path, "render", output_dir), cwd=tmp_path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    stdout = cast(dict[str, object], json.loads(first.stdout))
    plan_path = Path(cast(str, stdout["plan_path"]))
    manifest_path = Path(cast(str, stdout["manifest_path"]))
    assert stdout["mode"] == "slurm-harness"
    assert stdout["action"] == "render"
    assert stdout["submit_attempted"] is False
    assert plan_path == output_dir / "slurm-cli-001" / "slurm_harness_plan.json"
    assert manifest_path == output_dir / "slurm-cli-001" / "slurm_harness_manifest.json"
    sbatch_path = output_dir / "slurm-cli-001" / "autovla_microloop_smoke.sbatch"
    assert plan_path.resolve().is_relative_to(tmp_path.resolve())
    assert manifest_path.resolve().is_relative_to(tmp_path.resolve())
    assert sbatch_path.resolve().is_relative_to(tmp_path.resolve())
    assert sbatch_path.is_file()
    sbatch_text = sbatch_path.read_text("utf-8")
    assert "autovla.training.cli microloop" in sbatch_text
    assert f"{sys.executable} -m autovla.training.cli microloop" in sbatch_text
    assert "\npython -m autovla.training.cli microloop" not in sbatch_text
    assert (
        plan_path.read_text("utf-8")
        == json.dumps(
            json.loads(plan_path.read_text("utf-8")),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    plan = cast(dict[str, object], json.loads(plan_path.read_text("utf-8")))
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text("utf-8")))
    microloop_argv = cast(list[str], plan["microloop_command_argv"])
    assert microloop_argv[0] == sys.executable
    assert microloop_argv[0] != "python"
    assert Path(microloop_argv[0]).name.startswith("python")
    for data in (plan, manifest):
        assert data["dataset_fingerprint"] == "dataset-slurm-cli"
        assert data["transform_fingerprint"] == "transform-slurm-cli"
        assert data["statistics_fingerprint"] == "stats-slurm-cli"
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
        assert data["gpus_expected_for_test"] == 0
        assert data["real_training"] is False
        assert data["gpu_compute"] is False
    assert (
        manifest_path.read_text("utf-8")
        == json.dumps(
            json.loads(manifest_path.read_text("utf-8")),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def test_cli_slurm_harness_validate_should_not_invoke_slurm(tmp_path: Path) -> None:
    """验证 validate 不提交 Slurm, 只产出校验 manifest。"""
    output_dir = tmp_path / "out"

    result = _run_cli(_harness_args(tmp_path, "validate", output_dir), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    stdout = cast(dict[str, object], json.loads(result.stdout))
    manifest = cast(
        dict[str, object],
        json.loads(Path(cast(str, stdout["manifest_path"])).read_text("utf-8")),
    )
    assert manifest["action"] == "validate"
    assert manifest["submit_attempted"] is False
    assert manifest["submitted_job_id"] is None


def test_cli_slurm_harness_should_reject_invalid_inputs_without_partial_outputs(
    tmp_path: Path,
) -> None:
    """验证无效资源或 run_id 不留下局部输出。"""
    output_dir = tmp_path / "out"
    args = [
        "slurm-harness",
        "render",
        "--microloop-config",
        str(_microloop_config(tmp_path)),
        "--slurm-config",
        str(_slurm_config(tmp_path, nodes=2)),
        "--run-id",
        "bad;id",
        "--output-dir",
        str(output_dir),
    ]

    result = _run_cli(args, cwd=tmp_path)

    assert result.returncode == 2
    assert "run_id" in result.stderr
    assert not output_dir.exists()


def test_cli_slurm_harness_should_reject_output_dir_file(tmp_path: Path) -> None:
    """验证 output_dir 为文件时失败且不覆盖文件。"""
    output_file = tmp_path / "not-dir"
    output_file.write_text("occupied\n", encoding="utf-8")

    result = _run_cli(_harness_args(tmp_path, "render", output_file), cwd=tmp_path)

    assert result.returncode == 2
    assert "output_dir" in result.stderr
    assert output_file.read_text("utf-8") == "occupied\n"
