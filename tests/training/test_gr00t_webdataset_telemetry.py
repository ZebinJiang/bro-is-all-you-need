"""GR00T N1.6 WebDataset telemetry dry-run scaffold 测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from autovla.training.gr00t_webdataset_telemetry import (
    GR00T_TELEMETRY_REPORT_FILENAME,
    Gr00tTelemetryConfigError,
    build_telemetry_report,
    check_checkpoint_manifest,
    check_data_gate,
    check_env_gate,
    load_gr00t_telemetry_config,
)

ROOT = Path(__file__).resolve().parents[2]


def _write_yaml(path: Path, *, tmp_path: Path, max_steps: int = 20) -> Path:
    """写入 tiny telemetry YAML 配置。"""
    path.write_text(
        "\n".join(
            [
                "schema_version: autovla.gr00t_webdataset_telemetry_dryrun.v1",
                "run_id: tiny-gr00t-telemetry",
                "mode: gr00t-n1d6-webdataset-telemetry-dryrun",
                f"max_steps: {max_steps}",
                "environment:",
                "  profile: model-gr00t-n1d6",
                "  uv_project: envs/model-gr00t-n1d6",
                "  offline: true",
                "paths:",
                f"  dataset_root: {tmp_path / 'dataset'}",
                f"  webdataset_store: {tmp_path / 'webdataset_store'}",
                f"  gr00t_source_root: {tmp_path / 'Isaac-GR00T17'}",
                f"  checkpoint: {tmp_path / 'GR00T-N1.6-3B'}",
                f"  output_root: {tmp_path / 'runs'}",
                "policy:",
                "  checkpoint_write: false",
                "  hf_network: false",
                "  wandb_network: false",
                "  compute_node_model_load_only: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_webdataset_manifest(store: Path) -> Path:
    """写入 tiny WebDataset gate manifest。"""
    store.mkdir(parents=True)
    manifest = {
        "action_dim": 98,
        "action_mask_policy": "source_mask_or_bool_all_true_derivable",
        "build_status": "PASS",
        "episode_count": 2,
        "external_effects": {
            "checkpoint_load": False,
            "hf_network": False,
            "model_load": False,
            "real_training": False,
            "source_dataset_mutation": False,
            "tokenizer_load": False,
            "wandb_network": False,
        },
        "format_name": "webdataset_native",
        "sample_count": 512,
        "schema_version": "autovla.data_format_pipeline.v1",
        "source_dataset_fingerprint": "dataset-fingerprint",
        "state_dim": 72,
        "worker_count": 8,
    }
    path = store / "webdataset_store_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_checkpoint_manifest(path: Path, checkpoint: Path, source_root: Path) -> Path:
    """写入 tiny GR00T checkpoint candidate manifest。"""
    checkpoint.mkdir(parents=True)
    source_root.mkdir(parents=True)
    payload = {
        "allowed_use_status": "local_read_only_candidate_pending_bounded_dryrun_approval",
        "checkpoint_path": checkpoint.as_posix(),
        "completeness_status": "complete",
        "config_files": [
            "config.json",
            "model.safetensors.index.json",
            "processor_config.json",
            "statistics.json",
        ],
        "local_only": True,
        "missing_files": [],
        "model_registry_key": "gr00t-n1d6",
        "no_download": True,
        "no_network": True,
        "source_project_path": source_root.as_posix(),
        "tokenizer_or_processor_files": ["processor_config.json"],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _offline_env() -> dict[str, str]:
    """返回 dry-run 必需离线环境变量。"""
    env = os.environ.copy()
    env.update(
        {
            "AUTOVLA_NO_NETWORK": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "WANDB_DISABLED": "true",
        }
    )
    return env


def _run_module(
    args: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """通过 canonical module 命令运行 telemetry scaffold。"""
    merged_env = os.environ.copy()
    merged_env["PYTHONDONTWRITEBYTECODE"] = "1"
    merged_env["PYTHONPATH"] = str(ROOT)
    if env is not None:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.gr00t_webdataset_telemetry", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=merged_env,
    )


def test_example_config_should_use_placeholders_without_absolute_local_paths() -> None:
    """验证 tracked example 不泄露本机 GR00T/dataset 绝对路径。"""
    config = ROOT / "configs/dryrun/gr00t_n1d6_webdataset_telemetry_dryrun.example.yaml"
    text = config.read_text(encoding="utf-8")

    for placeholder in (
        "${AUTOVLA_DATASET_ROOT}",
        "${AUTOVLA_WEBDATASET_STORE}",
        "${AUTOVLA_GR00T_SOURCE_ROOT}",
        "${AUTOVLA_GR00T_N1D6_CHECKPOINT}",
        "${AUTOVLA_DRYRUN_OUTPUT_ROOT}",
    ):
        assert placeholder in text
    assert "/home/" not in text
    assert "Isaac-GR00T17" not in text


def test_config_schema_should_enforce_step_cap_and_no_external_effects(tmp_path: Path) -> None:
    """验证配置 schema 限制 20 步、离线和禁止 checkpoint 写入。"""
    config_path = _write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path)

    config = load_gr00t_telemetry_config(config_path)

    assert config.max_steps == 20
    assert config.environment_profile == "model-gr00t-n1d6"
    assert config.checkpoint_write is False
    assert config.hf_network is False
    assert config.wandb_network is False
    assert config.compute_node_model_load_only is True

    too_many_steps = _write_yaml(tmp_path / "too-many.yaml", tmp_path=tmp_path, max_steps=21)
    with pytest.raises(Gr00tTelemetryConfigError, match="max_steps"):
        load_gr00t_telemetry_config(too_many_steps)


def test_env_gate_should_require_offline_vars_and_model_special_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 env gate 只接受 model-gr00t-n1d6 且拒绝网络环境。"""
    config = load_gr00t_telemetry_config(_write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path))
    for name in ("AUTOVLA_NO_NETWORK", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "WANDB_DISABLED"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(Gr00tTelemetryConfigError, match="offline"):
        check_env_gate(config, profile_root=ROOT / "configs/env/profiles")

    monkeypatch.setenv("AUTOVLA_NO_NETWORK", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("WANDB_DISABLED", "true")
    result = check_env_gate(config, profile_root=ROOT / "configs/env/profiles")

    assert result["profile"] == "model-gr00t-n1d6"
    assert result["sync_profile_allowed"] is False
    assert result["install_status"] == "not_installed"


def test_data_and_checkpoint_gates_should_accept_tiny_manifests(tmp_path: Path) -> None:
    """验证 data/checkpoint gate 只读检查 manifest schema, 不读取权重。"""
    config = load_gr00t_telemetry_config(_write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path))
    data_manifest = _write_webdataset_manifest(config.webdataset_store)
    checkpoint_manifest = _write_checkpoint_manifest(
        tmp_path / "checkpoint-manifest.json",
        config.checkpoint_path,
        config.gr00t_source_root,
    )

    data_gate = check_data_gate(config)
    checkpoint_gate = check_checkpoint_manifest(config, checkpoint_manifest)

    assert data_gate["manifest_path"] == data_manifest.as_posix()
    assert data_gate["sample_count"] == 512
    assert data_gate["worker_count"] == 8
    assert checkpoint_gate["checkpoint_manifest_path"] == checkpoint_manifest.as_posix()
    assert checkpoint_gate["local_only"] is True
    assert checkpoint_gate["no_download"] is True
    assert checkpoint_gate["tokenizer_or_processor_present"] is True


def test_run_dryrun_should_write_deterministic_blocked_runtime_report(tmp_path: Path) -> None:
    """验证 run-dryrun 在 login node 只写 deterministic gate report, 不加载模型。"""
    config_path = _write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path)
    config = load_gr00t_telemetry_config(config_path)
    _write_webdataset_manifest(config.webdataset_store)
    checkpoint_manifest = _write_checkpoint_manifest(
        tmp_path / "checkpoint-manifest.json",
        config.checkpoint_path,
        config.gr00t_source_root,
    )

    first = _run_module(
        [
            "run-dryrun",
            "--config",
            str(config_path),
            "--checkpoint-manifest",
            str(checkpoint_manifest),
        ],
        cwd=tmp_path,
        env=_offline_env(),
    )

    assert first.returncode == 0, first.stderr
    stdout = cast(dict[str, object], json.loads(first.stdout))
    report_path = Path(cast(str, stdout["telemetry_report_path"]))
    assert report_path == config.output_root / config.run_id / GR00T_TELEMETRY_REPORT_FILENAME
    report = cast(dict[str, object], json.loads(report_path.read_text(encoding="utf-8")))
    assert report["schema_version"] == "autovla.gr00t_webdataset_telemetry_report.v1"
    assert report["classification"] == "BLOCKED_MODEL_RUNTIME_LOGIN_NODE"
    assert report["max_steps"] == 20
    assert report["checkpoint_write"] is False
    assert report["model_load_attempted"] is False
    assert report["tokenizer_load_attempted"] is False
    assert report["checkpoint_weight_read_attempted"] is False
    assert report["missing_metrics"] == [
        "model_runtime_import",
        "gpu_memory",
        "forward_latency_ms",
        "backward_latency_ms",
        "optimizer_step_latency_ms",
    ]
    assert all(
        value is False for value in cast(dict[str, bool], report["external_effects"]).values()
    )

    first_text = report_path.read_text(encoding="utf-8")
    second = _run_module(
        [
            "run-dryrun",
            "--config",
            str(config_path),
            "--checkpoint-manifest",
            str(checkpoint_manifest),
        ],
        cwd=tmp_path,
        env=_offline_env(),
    )
    assert second.returncode == 0, second.stderr
    assert report_path.read_text(encoding="utf-8") == first_text


def test_render_slurm_command_should_require_compute_node_flag_and_no_network(
    tmp_path: Path,
) -> None:
    """验证 render-slurm-command 输出 bounded compute-only 命令。"""
    config_path = _write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path)
    checkpoint_manifest = _write_checkpoint_manifest(
        tmp_path / "checkpoint-manifest.json",
        tmp_path / "GR00T-N1.6-3B",
        tmp_path / "Isaac-GR00T17",
    )

    result = _run_module(
        [
            "render-slurm-command",
            "--config",
            str(config_path),
            "--checkpoint-manifest",
            str(checkpoint_manifest),
        ],
        cwd=tmp_path,
        env=_offline_env(),
    )

    assert result.returncode == 0, result.stderr
    payload = cast(dict[str, object], json.loads(result.stdout))
    argv = cast(list[str], payload["argv"])
    env = cast(dict[str, str], payload["environment"])
    assert argv[:3] == [sys.executable, "-m", "autovla.training.gr00t_webdataset_telemetry"]
    assert "run-dryrun" in argv
    assert "--require-compute-node" in argv
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["WANDB_DISABLED"] == "true"
    assert payload["max_steps"] == 20
    assert payload["checkpoint_write"] is False


def test_build_report_should_keep_missing_metrics_explicit(tmp_path: Path) -> None:
    """验证 telemetry report schema 对未观测指标显式分类。"""
    config = load_gr00t_telemetry_config(_write_yaml(tmp_path / "config.yaml", tmp_path=tmp_path))
    _write_webdataset_manifest(config.webdataset_store)
    checkpoint_manifest = _write_checkpoint_manifest(
        tmp_path / "checkpoint-manifest.json",
        config.checkpoint_path,
        config.gr00t_source_root,
    )

    report = build_telemetry_report(
        config,
        env_gate={"profile": "model-gr00t-n1d6", "sync_profile_allowed": False},
        data_gate=check_data_gate(config),
        checkpoint_gate=check_checkpoint_manifest(config, checkpoint_manifest),
        compute_node=False,
    )

    metrics = cast(dict[str, object], report["metrics"])
    assert metrics["planned_max_steps"] == 20
    assert metrics["observed_completed_steps"] == "not_observed"
    assert metrics["completion_ratio"] == "missing"
    assert metrics["data_wait_proxy_ms"] == "not_observed"
    assert report["fine_tune_readiness"] is False
