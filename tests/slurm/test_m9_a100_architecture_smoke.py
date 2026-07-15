"""验证 M9 单 A100 计算 harness 的静态治理与 wrapper 组合边界。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from autovla.config import load_yaml

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "scripts/slurm/m9_a100_architecture_smoke.sbatch"
CONFIG = ROOT / "configs/slurm/m9_a100_single_gpu.json"
EXPERIMENT = ROOT / "configs/experiments/gr00t_n1d6_webdataset.yaml"
WRAPPER = ROOT / "scripts/slurm/submit_sandbox_job.sh"
M8_JOB = ROOT / "scripts/slurm/m8_a100_architecture_smoke.sbatch"
M8_CONFIG = ROOT / "configs/slurm/m8_a100_single_gpu.json"
TASK_ID = "AUTOVLA-M9-ARCHITECTURE-COMPLETION-UNIFIED-SEMANTICS-UPSTREAM-INTEGRATION-001"


def _source() -> str:
    """返回待审查的 M9 作业脚本文本。"""
    return JOB.read_text(encoding="utf-8")


def test_slurm_config_is_exactly_one_bounded_a100() -> None:
    """资源配置必须固定为单节点、单任务、单 A100 与短时限。"""
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert config["partition"] == "a100"
    assert config["nodes"] == 1
    assert config["ntasks"] == 1
    assert config["gres"] == "gpu:1"
    assert 0 < config["max_minutes"] <= 15
    assert "performance" not in config["notes"].lower()


def test_runtime_request_is_mandatory_and_precedes_runtime_work() -> None:
    """请求解析必须早于资产、配置、CUDA 与生产训练阶段。"""
    source = _source()

    assert "${SANDBOX_RUNTIME_REQUEST:?--runtime-request under project runs/ is required}" in source
    validation = source.index('CURRENT_PHASE="validate_runtime_request"')
    assert validation < source.index('CURRENT_PHASE="verify_local_asset_bundle"')
    assert validation < source.index('CURRENT_PHASE="materialize_resolved_config"')
    assert validation < source.index('CURRENT_PHASE="probe_single_a100_runtime"')
    assert validation < source.index('CURRENT_PHASE="production_train_one_step"')
    for required_field in (
        "schema_version",
        "candidate_digest",
        "fixture_root",
        "fixture_identity",
        "fixture_sample_count",
        "model_profile",
        "max_steps",
        "embodiment",
        "base_asset_spec_identity",
        "base_asset_revision",
        "eagle_asset_spec_identity",
        "eagle_asset_revision",
    ):
        assert f'"{required_field}"' in source


def test_runtime_request_is_fail_closed_and_task_local() -> None:
    """请求必须精确匹配固定 schema、资产身份和受治理 fixture 根。"""
    source = _source()

    assert "set(request) != required" in source
    assert 'r"[0-9a-f]{64}"' in source
    assert 'request["model_profile"] != "model-gr00t-n1d6"' in source
    assert 'type(request["max_steps"]) is not int or request["max_steps"] != 1' in source
    assert "fixture_sample_count must be a positive integer" in source
    assert 'root / "runs" / "tmp" / task_id' in source
    assert 'root / "datasets" / "working"' in source
    assert "Gr00tModelAssetBundle.resolve" in source
    assert "validated runtime request mismatch" in source


def test_config_uses_only_current_canonical_overrides() -> None:
    """配置必须从 tracked 实验生成且只写 canonical 顶层组。"""
    source = _source()

    assert "configs/experiments/gr00t_n1d6_webdataset.yaml" in source
    assert "git ls-files --error-unmatch" in source
    for override in (
        "run.intent=training",
        "model.asset_key=gr00t_n1d6",
        "data.backend=null",
        "data.loader.batch_size=1",
        "data.loader.num_workers=0",
        "topology.distributed.strategy_key=single_gpu",
        "topology.distributed.world_size=1",
        "topology.distributed.device=cuda",
        "topology.precision.mode=bfloat16",
        "training.max_steps=1",
        "checkpoint.save_every_steps=null",
        "checkpoint.save_final=false",
        "checkpoint.save_optimizer=true",
        "telemetry.remote_logging=false",
    ):
        assert override in source
    assert "training.distributed." not in source
    assert '"distributed" in resolved["training"]' in source


def test_canonical_materialization_overrides_resolve_valid_config() -> None:
    """真实调用 canonical load_yaml 验证 M9 物化覆盖可通过严格 schema。"""
    fixture_root = ROOT / "runs" / "tmp" / TASK_ID / "integration" / "fixture"
    camera_keys = ["camera.rgb_0", "camera.rgb_1", "camera.rgb_2"]
    dataset = {
        "name": "m9-runtime-fixture",
        "backend": "webdataset",
        "root": str(fixture_root),
        "split": "train",
        "weight": 1.0,
        "embodiment": "m9-test-embodiment",
        "sample_count": 1,
        "image_keys": camera_keys,
        "language_key": "language",
        "state_key": "state",
        "action_key": "action",
        "action_mask_key": "action_mask",
        "access_mode": "streaming",
        "stream_mode": "finite_epoch",
        "nominal_epoch_size": 1,
        "temporal_query": None,
    }

    def encoded(value: object) -> str:
        """按 harness 的严格 dotted override 规则编码动态值。"""
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))

    overrides = (
        "run.name=m9_a100_architecture_smoke",
        "run.output_dir=runs/slurm/m9-test/outputs/training",
        "run.intent=training",
        "model.asset_key=gr00t_n1d6",
        "model.eagle_asset_path=/governed/local/eagle",
        "data.name=m9-a100-webdataset-fixture",
        "data.backend=null",
        f"data.root={encoded(str(fixture_root))}",
        f"data.required_modalities={encoded(camera_keys)}",
        f"data.datasets={encoded([dataset])}",
        "data.loader.batch_size=1",
        "data.loader.num_workers=0",
        "topology.distributed.strategy_key=single_gpu",
        "topology.distributed.world_size=1",
        "topology.distributed.device=cuda",
        "topology.precision.mode=bfloat16",
        "training.max_steps=1",
        "checkpoint.directory=runs/slurm/m9-test/outputs/checkpoints",
        "checkpoint.save_every_steps=null",
        "checkpoint.save_final=false",
        "checkpoint.save_optimizer=true",
        "telemetry.logging.jsonl_path=runs/slurm/m9-test/outputs/metrics.jsonl",
        "telemetry.remote_logging=false",
    )

    config = load_yaml(EXPERIMENT, overrides=overrides)

    assert config.data.backend is None
    assert len(config.data.datasets) == 1
    resolved_dataset = config.data.datasets[0]
    assert resolved_dataset.backend == "webdataset"
    assert resolved_dataset.access_mode == "streaming"
    assert resolved_dataset.stream_mode == "finite_epoch"
    assert config.topology.distributed.strategy_key == "single_gpu"
    assert config.topology.distributed.world_size == 1
    assert config.training.max_steps == 1
    assert config.checkpoint.save_final is False
    assert config.checkpoint.save_every_steps is None
    assert config.checkpoint.save_optimizer is True


def test_dataset_is_one_finite_stream_with_canonical_cameras() -> None:
    """fixture 必须映射为单个有限 WebDataset 与三路规范相机。"""
    source = _source()

    assert '"backend": "webdataset"' in source
    assert '"access_mode": "streaming"' in source
    assert '"stream_mode": "finite_epoch"' in source
    assert '"nominal_epoch_size": request["fixture_sample_count"]' in source
    assert '["camera.rgb_0", "camera.rgb_1", "camera.rgb_2"]' in source
    assert "len(config.data.datasets) != 1" in source
    for forbidden_creation in (
        'mkdir -p "$FIXTURE',
        'cp "$FIXTURE',
        'tar -xf "$FIXTURE',
        "generate_fixture",
    ):
        assert forbidden_creation not in source


def test_runtime_is_offline_project_local_and_has_no_fallback() -> None:
    """所有缓存、临时、遥测和输出必须本地化且禁止网络回退。"""
    source = _source()

    for declaration in (
        'export HOME="$SANDBOX_RUN_DIR/home"',
        'export TMPDIR="$SANDBOX_RUN_DIR/tmp"',
        "export HF_HUB_OFFLINE=1",
        "export TRANSFORMERS_OFFLINE=1",
        "export HF_DATASETS_OFFLINE=1",
        "export WANDB_MODE=disabled",
        "export WANDB_DISABLED=true",
    ):
        assert declaration in source
    assert 'PROFILE_ID="model-gr00t-n1d6"' in source
    assert "no fallback is allowed" in source
    assert "trust_remote_code" not in source
    assert "http://" not in source and "https://" not in source


def test_runtime_is_one_step_single_gpu_without_disallowed_matrices() -> None:
    """生产命令只能覆盖单 GPU 一步训练,不得扩展运行矩阵。"""
    source = _source().lower()

    assert "training.max_steps=1" in source
    assert "topology.distributed.strategy_key=single_gpu" in source
    assert "topology.distributed.world_size=1" in source
    assert "torch.cuda.device_count() != 1" in source
    assert "-m autovla.cli.train" in source
    for forbidden in (
        "distributed_data_parallel",
        "deepspeed",
        "fully_sharded",
        "fsdp",
        "srun ",
        "benchmark",
        "throughput",
        "device=cpu",
    ):
        assert forbidden not in source


def test_result_trap_preserves_primary_status_and_records_evidence() -> None:
    """EXIT trap 必须保留主退出码并记录完整身份与首因失败。"""
    source = _source()

    assert "trap record_result EXIT" in source
    assert 'local primary_status="$?"' in source
    assert 'write_result_evidence "$primary_status"' in source
    assert 'exit "$primary_status"' in source
    for evidence_key in (
        '"source_head"',
        '"candidate_digest"',
        '"config_fingerprint"',
        '"asset_bundle"',
        '"runtime"',
        '"command"',
        '"exit_code"',
        '"first_causal_failure"',
    ):
        assert evidence_key in source


def test_m8_reference_files_are_untouched() -> None:
    """M9 harness 不得改写 M8 脚本或单卡配置。"""
    result = subprocess.run(
        ["git", "diff", "--exit-code", "--", str(M8_JOB), str(M8_CONFIG)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_wrapper_dry_run_composes_without_submission() -> None:
    """正式 wrapper 必须携带 request 并仅生成单卡 sbatch 命令。"""
    request_dir = ROOT / "runs" / "tmp" / TASK_ID / "integration" / "test-requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    request = request_dir / "m9-a100-dry-run.json"
    request.write_text("{}\n", encoding="utf-8")
    run_id = "m9-a100-harness-pytest-dry-run"
    result = subprocess.run(
        [
            str(WRAPPER),
            "--config",
            str(CONFIG),
            "--experiment-config",
            str(EXPERIMENT),
            "--job-script",
            str(JOB),
            "--run-id",
            run_id,
            "--runtime-request",
            str(request),
            "--dry-run",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRY RUN: no job submitted" in result.stdout
    assert "--nodes=1" in result.stdout
    assert "--ntasks=1" in result.stdout
    assert "--gres=gpu:1" in result.stdout
    assert f"runtime_request={request.resolve()}" in result.stdout
