"""M8 A100 Slurm request/render architecture tests。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "single_gpu": (1, 1, "gpu:1"),
    "same_node_ddp": (1, 2, "gpu:2"),
    "same_node_zero1": (1, 2, "gpu:2"),
    "same_node_zero2": (1, 2, "gpu:2"),
    "same_node_zero3": (1, 2, "gpu:2"),
    "cross_node_ddp": (2, 4, "gpu:2"),
    "cross_node_zero3": (2, 4, "gpu:2"),
}


@pytest.mark.parametrize(("target", "shape"), TARGETS.items())
def test_request_renders_exact_project_wrapper_without_submission(
    target: str, shape: tuple[int, int, str]
) -> None:
    """验证每个 target 只渲染 existing wrapper 和 A100 资源。"""

    result = subprocess.run(
        [
            "bash",
            "scripts/slurm/request_m8_a100_architecture_smoke.sh",
            "--target",
            target,
            "--run-id",
            f"m8-{target}",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "scripts/slurm/submit_sandbox_job.sh" in result.stdout
    assert f"configs/slurm/m8_a100_{target}.json" in result.stdout
    assert "partition=a100" in result.stdout
    assert "output_root=runs/slurm" in result.stdout
    expected_profile = "training-deepspeed" if "zero" in target else "model-gr00t-n1d6"
    assert f"runtime_profile={expected_profile}" in result.stdout
    assert "submission=not_requested" in result.stdout
    config = json.loads((ROOT / f"configs/slurm/m8_a100_{target}.json").read_text(encoding="utf-8"))
    assert (config["nodes"], config["ntasks"], config["gres"]) == shape
    assert config["partition"] == "a100"


def test_job_is_offline_local_only_and_has_no_retired_launcher() -> None:
    """验证 future job 只声明本地资产、GPU 策略和 scheduler 派生 rendezvous。"""

    source = (ROOT / "scripts/slurm/m8_a100_architecture_smoke.sbatch").read_text(encoding="utf-8")
    for required in (
        "AUTOVLA_MODEL_HOME=/home/cz-jzb/workspace/vla-flywheel/base_model",
        "HF_HUB_OFFLINE=1",
        "TRANSFORMERS_OFFLINE=1",
        "WANDB_MODE=disabled",
        "training.max_steps=2",
        'PROFILE_INTERPRETER="$SANDBOX_PROJECT_ROOT/envs/$PROFILE_ID/.venv/bin/python"',
        "No fallback is allowed",
        "training.checkpoint.directory=$CHECKPOINT_DIR",
        "training.logging.jsonl_path=$METRICS_PATH",
        "runtime-launch.json",
        "runtime-result.json",
        "source_sha",
        "package_versions",
        '"safetensors"',
        '"huggingface-hub"',
        '"numpy"',
        '"omegaconf"',
        "offline_asset_verification",
        "asset-verification.json",
        "srun --nodes=",
        "--distribution=block:block",
        "--kill-on-bad-exit=1",
        "SLURM_JOB_NODELIST",
        "SLURM_JOB_ID",
    ):
        assert required in source
    lowered = source.lower()
    assert "fsdp" not in lowered
    assert "device=cpu" not in lowered
    assert " python -m autovla" not in source
    assert "python3 -m autovla" not in source
    assert "hf_" not in source.replace("HF_HUB_OFFLINE", "").replace("HF_DATASETS_OFFLINE", "")


def test_job_profiles_are_narrow_and_zero_only_adds_deepspeed() -> None:
    """验证 GR00T+WebDataset 为共同基础,只有 ZeRO 目标选择 DeepSpeed profile。"""

    source = (ROOT / "scripts/slurm/m8_a100_architecture_smoke.sbatch").read_text(encoding="utf-8")

    assert 'PROFILE_ID="model-gr00t-n1d6"' in source
    assert source.count("PROFILE_ID=training-deepspeed") == 2
    assert "all-model-zoo" not in source


@pytest.mark.parametrize(
    ("target", "profile"),
    (
        ("single_gpu", "model-gr00t-n1d6"),
        ("same_node_zero3", "training-deepspeed"),
    ),
)
def test_submit_fails_before_wrapper_when_profile_interpreter_is_missing(
    tmp_path: Path,
    target: str,
    profile: str,
) -> None:
    """验证 submit 在临时 checkout 缺少受管解释器时不创建 run 或调用 wrapper。"""

    sandbox = tmp_path / "checkout"
    script_path = sandbox / "scripts/slurm/request_m8_a100_architecture_smoke.sh"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(
        (ROOT / "scripts/slurm/request_m8_a100_architecture_smoke.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    script_path.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            str(script_path),
            "--target",
            target,
            "--run-id",
            "missing-profile",
            "--submit",
        ],
        cwd=sandbox,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 127
    assert f"M8 runtime profile is unavailable: {profile}" in result.stderr
    assert f"envs/{profile}/.venv/bin/python" in result.stderr
    assert "Wave 8 must manually authorize and prepare this uv profile" in result.stderr
    assert "No fallback is allowed" in result.stderr
    assert "submit_sandbox_job.sh" not in result.stdout + result.stderr
    assert not (sandbox / "runs").exists()
