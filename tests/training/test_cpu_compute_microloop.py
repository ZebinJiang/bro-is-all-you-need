"""CPU-only microloop 的 CLI 和边界测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Protocol, cast

import numpy as np
import pytest

from autovla.core.types import FrameworkOutput, ModelInput
from autovla.training.config import build_local_runner_dry_run_config
from autovla.training.microloop import build_microloop_batch, run_microloop


class _ForwardOnlyFramework(Protocol):
    def forward(self, inputs: ModelInput) -> FrameworkOutput:
        """返回单批次训练输出。"""


class _NonFiniteFramework:
    def forward(self, inputs: ModelInput) -> FrameworkOutput:
        """模拟模型边界传回非有限损失。"""

        del inputs
        return FrameworkOutput(
            loss=float("nan"),
            losses={"action": float("nan")},
            metrics={"masked_action_mse": float("nan")},
        )


def _config_dict(output_dir: Path) -> dict[str, object]:
    return {
        "run_id": "microloop_test_run",
        "seed": 7,
        "model_registry_key": "deterministic.action.framework",
        "dataset_fingerprint": "dataset-fp",
        "transform_fingerprint": "transform-fp",
        "statistics_fingerprint": "statistics-fp",
        "action_horizon": 2,
        "action_dim": 3,
        "max_steps": 2,
        "output_dir": str(output_dir),
        "mode": "dry-run",
    }


def _write_config(tmp_path: Path, data: Mapping[str, object]) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    return path


def _subprocess_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "AUTOVLA_COMPUTE_NODE_VALIDATION": "1",
            "AUTOVLA_EXPECT_NO_GPU": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    if extra is not None:
        env.update(extra)
    return env


def _run_cli(
    tmp_path: Path,
    *args: str,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.cli", *args],
        cwd=Path(__file__).resolve().parents[2],
        env=_subprocess_env(env),
        text=True,
        capture_output=True,
        check=False,
    )


def _run_microloop_cli(
    tmp_path: Path,
    *,
    config_path: Path,
    output_dir: Path,
    env: Mapping[str, str] | None = None,
    resume_from: Path | None = None,
    require_compute_node: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        "microloop",
        "--config",
        str(config_path),
        "--output-dir",
        str(output_dir),
    ]
    if resume_from is not None:
        args.extend(["--resume-from", str(resume_from)])
    if require_compute_node:
        args.append("--require-compute-node")
    return _run_cli(tmp_path, *args, env=env)


def _read_manifest(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def test_cli_help_should_expose_microloop_without_removing_existing_commands(
    tmp_path: Path,
) -> None:
    help_result = _run_cli(tmp_path, "--help")
    assert help_result.returncode == 0
    assert "microloop" in help_result.stdout
    assert "--dry-run" in help_result.stdout
    assert "--local-smoke" in help_result.stdout
    assert "readiness" in help_result.stdout


def test_cli_microloop_should_write_deterministic_manifest(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _config_dict(tmp_path / "config-output"))
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = _run_microloop_cli(tmp_path, config_path=config_path, output_dir=first_output)
    second = _run_microloop_cli(tmp_path, config_path=config_path, output_dir=second_output)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_manifest = first_output / "microloop_test_run" / "microloop_manifest.json"
    second_manifest = second_output / "microloop_test_run" / "microloop_manifest.json"
    assert first_manifest.read_bytes() == second_manifest.read_bytes()

    manifest = _read_manifest(first_manifest)
    assert manifest["schema_version"] == "m3-cpu-compute-microloop.v1"
    assert manifest["mode"] == "microloop"
    assert manifest["package_name"] == "autovla"
    assert manifest["dataset_fingerprint"] == "dataset-fp"
    assert manifest["transform_fingerprint"] == "transform-fp"
    assert manifest["statistics_fingerprint"] == "statistics-fp"
    assert manifest["model_registry_key"] == "deterministic.action.framework"
    assert manifest["seed"] == 7
    assert manifest["max_steps"] == 2
    effects = cast(dict[str, bool], manifest["external_effects"])
    assert all(value is False for value in effects.values())
    compute_execution = cast(dict[str, object], manifest["compute_execution"])
    assert compute_execution["mode"] == "slurm_cpu"
    assert cast(dict[str, object], compute_execution["slurm_cpu"])["partition"] == "a100"
    assert manifest["checkpoint_manifest"] == "checkpoints/step-2.json"
    assert cast(dict[str, object], manifest["resume_validation"])["compatible"] is True


def test_cli_microloop_should_validate_resume_and_reject_incompatible_resume(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path, _config_dict(tmp_path / "config-output"))
    output_dir = tmp_path / "output"
    first = _run_microloop_cli(tmp_path, config_path=config_path, output_dir=output_dir)
    assert first.returncode == 0, first.stderr
    checkpoint_path = output_dir / "microloop_test_run" / "checkpoints" / "step-2.json"

    resumed = _run_microloop_cli(
        tmp_path,
        config_path=config_path,
        output_dir=tmp_path / "resumed",
        resume_from=checkpoint_path,
    )
    assert resumed.returncode == 0, resumed.stderr
    resumed_manifest = _read_manifest(
        tmp_path / "resumed" / "microloop_test_run" / "microloop_manifest.json"
    )
    assert cast(dict[str, object], resumed_manifest["resume_validation"])["requested"] is True

    bad_checkpoint = tmp_path / "bad_checkpoint.json"
    checkpoint_data = _read_manifest(checkpoint_path)
    checkpoint_data["model_registry_key"] = "different-model"
    bad_checkpoint.write_text(json.dumps(checkpoint_data, sort_keys=True), encoding="utf-8")

    incompatible = _run_microloop_cli(
        tmp_path,
        config_path=config_path,
        output_dir=tmp_path / "incompatible",
        resume_from=bad_checkpoint,
    )
    assert incompatible.returncode == 2
    assert "model_registry_key" in incompatible.stderr
    incompatible_manifest = tmp_path / "incompatible" / "microloop_test_run"
    assert not (incompatible_manifest / "microloop_manifest.json").exists()


@pytest.mark.parametrize("bad_seed", [True, "7", -1])
def test_cli_microloop_should_reject_invalid_seed(tmp_path: Path, bad_seed: object) -> None:
    config_data = _config_dict(tmp_path / "config-output")
    config_data["seed"] = bad_seed
    config_path = _write_config(tmp_path, config_data)

    result = _run_microloop_cli(tmp_path, config_path=config_path, output_dir=tmp_path / "out")

    assert result.returncode == 2
    assert "seed" in result.stderr
    assert not (tmp_path / "out" / "microloop_test_run" / "microloop_manifest.json").exists()


def test_cli_microloop_should_reject_unsafe_output_dir_and_external_effects(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path, _config_dict(tmp_path / "config-output"))
    file_output = tmp_path / "not-a-dir"
    file_output.write_text("occupied", encoding="utf-8")

    bad_output = _run_microloop_cli(tmp_path, config_path=config_path, output_dir=file_output)
    assert bad_output.returncode == 2
    assert "output_dir" in bad_output.stderr

    external_effect = _run_microloop_cli(
        tmp_path,
        config_path=config_path,
        output_dir=tmp_path / "external",
        env={"AUTOVLA_ATTEMPT_EXTERNAL_EFFECT": "1"},
    )
    assert external_effect.returncode == 2
    assert "external effects" in external_effect.stderr

    gpu_visible = _run_microloop_cli(
        tmp_path,
        config_path=config_path,
        output_dir=tmp_path / "gpu",
        env={"CUDA_VISIBLE_DEVICES": "0"},
    )
    assert gpu_visible.returncode == 2
    assert "gpu" in gpu_visible.stderr.lower()


def test_cli_microloop_should_require_compute_node_when_flag_is_set(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _config_dict(tmp_path / "config-output"))

    result = _run_microloop_cli(
        tmp_path,
        config_path=config_path,
        output_dir=tmp_path / "output",
        env={"AUTOVLA_COMPUTE_NODE_VALIDATION": ""},
        require_compute_node=True,
    )

    assert result.returncode == 2
    assert "compute node" in result.stderr
    assert not (tmp_path / "output" / "microloop_test_run" / "microloop_manifest.json").exists()


def test_microloop_should_reject_bad_masks_and_non_finite_metrics(tmp_path: Path) -> None:
    config = build_local_runner_dry_run_config(_config_dict(tmp_path / "output"))

    missing_mask_batch = build_microloop_batch(config, action_mask=None)
    with pytest.raises(ValueError, match="action_mask"):
        run_microloop(config, batch=missing_mask_batch)

    with pytest.raises((TypeError, ValueError), match="action_mask"):
        int_mask_batch = build_microloop_batch(
            config,
            action_mask=np.ones((1, config.action_horizon, config.action_dim), dtype=np.int64),
        )
        run_microloop(config, batch=int_mask_batch)

    with pytest.raises(ValueError, match="finite"):
        run_microloop(
            config,
            framework=cast(_ForwardOnlyFramework, _NonFiniteFramework()),
        )


def test_cli_microloop_should_keep_readiness_and_local_smoke_compatible(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _config_dict(tmp_path / "config-output"))

    readiness = _run_cli(
        tmp_path,
        "readiness",
        "--config",
        str(config_path),
        "--output-dir",
        str(tmp_path / "readiness-output"),
    )
    assert readiness.returncode == 0, readiness.stderr

    local_smoke = _run_cli(
        tmp_path,
        "--config",
        str(config_path),
        "--local-smoke",
        "--output-dir",
        str(tmp_path / "local-smoke-output"),
    )
    assert local_smoke.returncode == 0, local_smoke.stderr
