"""GR00T baseline metrics 只读摘要测试。"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from autovla.training.baseline_metrics import (
    render_baseline_metrics_markdown,
    summarize_baseline_run,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """写入稳定 JSON fixture。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    """写入 UTF-8 fixture。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _section(summary: Mapping[str, object], key: str) -> Mapping[str, object]:
    """从摘要中取出类型明确的 mapping section。"""
    value = summary[key]
    assert isinstance(value, Mapping)
    return cast(Mapping[str, object], value)


def _fixture_run(tmp_path: Path) -> Path:
    """构造不含真实数据 payload 的小型 baseline run fixture。"""
    run_dir = tmp_path / "baseline-run"
    sensitive_root = tmp_path / "secret-project"
    _write_json(
        run_dir / "outputs" / "finetune_manifest.json",
        {
            "action_horizon": "16",
            "base_model_path": str(sensitive_root / "base_model" / "GR00T-N1.6-3B"),
            "dataloader_num_workers": "24",
            "dataset_path": str(sensitive_root / "datasets" / "working" / "zjh"),
            "effective_global_batch_size": "72",
            "effective_samples": "176884",
            "global_batch_size": "72",
            "max_steps": "10",
            "model_family": "Gr00tN1d6",
            "num_gpus": "2",
            "slurm_job_id": "1346",
            "total_episodes": "768",
            "total_frames": "188404",
            "train_epochs": "30",
            "wandb_mode": "online",
        },
    )
    _write_json(
        run_dir / "outputs" / "submission_manifest.json",
        {
            "run_kind": "formal",
            "run_dir": str(run_dir),
            "slurm_job_id": "1346",
            "submit_output": "Submitted batch job 1346",
        },
    )
    _write_text(
        run_dir / "logs" / "stdout.log",
        "\n".join(
            [
                "Total steps: 176884, average shard length: 1022.45, shard length std: 5.91",
                "Rank 0, Worker 1: Wait for shard 7 in dataset 0 in 3.50 seconds",
                "Rank 1, Worker 2: Wait for shard 8 in dataset 0 in 0.00 seconds",
                "{'loss': 1.25, 'grad_norm': 2.5, 'learning_rate': 1e-06}",
                "{'loss': 0.75, 'grad_norm': 1.5, 'learning_rate': 2e-06}",
                " 30%|###       | 3/10 [00:03<00:07, 1.50it/s]",
                "https://wandb.ai/private/team/run and alex@example.com",
            ]
        )
        + "\n",
    )
    _write_text(
        run_dir / "logs" / "stderr.log",
        "\n".join(
            [
                "NCCL warning: using GPU 0 as device unknown",
                "Could not estimate the number of tokens of the input",
                "slurmstepd: error: *** JOB 1346 ON instance-znapw6il-2 "
                "CANCELLED AT 2026-06-25T02:31:11 ***",
            ]
        )
        + "\n",
    )
    _write_json(
        run_dir / "wandb" / "wandb" / "run-1" / "files" / "wandb-metadata.json",
        {
            "cudaVersion": "12.8",
            "email": "alex@example.com",
            "gpu": "NVIDIA H800",
            "gpu_count": 2,
            "gpu_nvidia": [
                {
                    "name": "NVIDIA H800",
                    "memoryTotal": "85520809984",
                    "uuid": "GPU-secret-uuid",
                }
            ],
            "host": "instance-znapw6il-2",
            "root": str(run_dir / "wandb"),
            "slurm": {
                "job_account": "cz-root",
                "job_nodelist": "instance-znapw6il-2",
                "job_partition": "h800",
            },
            "writerId": "secret-writer",
        },
    )
    _write_text(
        run_dir / "wandb" / "wandb" / "run-1" / "files" / "output.log",
        "{'loss': 0.50, 'grad_norm': 1.0, 'learning_rate': 3e-06}\n",
    )
    return run_dir


def test_summarize_baseline_run_should_be_deterministic_and_classify_partial_cancel(
    tmp_path: Path,
) -> None:
    """验证 baseline 摘要稳定且能识别取消的局部 run。"""
    run_dir = _fixture_run(tmp_path)

    first = summarize_baseline_run(run_dir)
    second = summarize_baseline_run(run_dir)

    assert first == second
    assert first["schema_version"] == "autovla.baseline_metrics.v1"
    assert _section(first, "status") == {
        "classification": "cancelled_partial",
        "evidence": "cancelled log marker",
        "partial_run": True,
    }
    assert _section(first, "training_config")["model_family"] == "Gr00tN1d6"
    assert _section(first, "training_config")["planned_max_steps"] == 10
    assert _section(first, "progress") == {
        "completed_steps": 3,
        "completion_ratio": 0.3,
        "planned_max_steps": 10,
    }


def test_summarize_baseline_run_should_extract_metrics_and_proxy_starvation(
    tmp_path: Path,
) -> None:
    """验证指标、吞吐和 dataloader 等待代理指标。"""
    summary = summarize_baseline_run(_fixture_run(tmp_path))
    scalar_metrics = _section(summary, "scalar_metrics")
    grad_norm = _section(scalar_metrics, "grad_norm")
    learning_rate = _section(scalar_metrics, "learning_rate")

    assert scalar_metrics["loss"] == {
        "count": 3,
        "first": 1.25,
        "last": 0.5,
        "max": 1.25,
        "min": 0.5,
    }
    assert grad_norm["max"] == 2.5
    assert learning_rate["last"] == 0.000003
    assert _section(summary, "throughput") == {
        "observed_it_per_second_last": 1.5,
        "progress_samples": 1,
        "samples_per_second_last": 108.0,
    }
    assert _section(summary, "dataloader_waits") == {
        "count": 2,
        "max_seconds": 3.5,
        "nonzero_count": 1,
        "p95_seconds": 3.5,
        "total_seconds": 3.5,
    }
    assert _section(summary, "warnings")["nccl_warning_count"] == 1
    assert _section(summary, "warnings")["token_flops_missing_count"] == 1


def test_summarize_baseline_run_should_redact_sensitive_values(tmp_path: Path) -> None:
    """验证 reportable 输出不泄露路径、URL、邮箱、主机或 GPU UUID。"""
    run_dir = _fixture_run(tmp_path)

    text = json.dumps(summarize_baseline_run(run_dir), sort_keys=True)

    assert str(tmp_path) not in text
    assert "alex@example.com" not in text
    assert "https://wandb.ai" not in text
    assert "instance-znapw6il-2" not in text
    assert "GPU-secret-uuid" not in text
    assert "secret-writer" not in text
    assert "<RUN_DIR>" in text
    assert "<EMAIL>" in text
    assert "<URL>" in text
    assert "<HOST>" in text
    assert "<GPU_UUID>" in text


def test_summarize_baseline_run_should_mark_missing_telemetry_explicitly(
    tmp_path: Path,
) -> None:
    """验证缺失 telemetry 不被猜测。"""
    run_dir = tmp_path / "minimal-run"
    _write_json(run_dir / "outputs" / "finetune_manifest.json", {"model_family": "Gr00tN1d6"})

    summary = summarize_baseline_run(run_dir)

    assert _section(summary, "progress")["completed_steps"] == "missing"
    assert _section(summary, "progress")["completion_ratio"] == "missing"
    assert _section(summary, "throughput")["observed_it_per_second_last"] == "not_observed"
    assert _section(summary, "scalar_metrics")["loss"] == "not_observed"
    assert _section(summary, "wandb_local_files")["metadata_json"] == "missing"
    assert _section(summary, "gpu_metadata")["gpu_utilization"] == "missing"


def test_summarize_baseline_run_should_not_call_external_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证摘要器不调用 Slurm、网络、训练或外部进程。"""
    run_dir = _fixture_run(tmp_path)

    def _forbid_subprocess(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("baseline metrics summarizer must not run subprocesses")

    monkeypatch.setattr(subprocess, "run", _forbid_subprocess)
    summary = summarize_baseline_run(run_dir)

    assert all(value is False for value in _section(summary, "external_effects").values())


def test_render_baseline_metrics_markdown_should_use_redacted_summary(tmp_path: Path) -> None:
    """验证 Markdown 报告只含摘要字段, 不粘贴原始日志。"""
    run_dir = _fixture_run(tmp_path)

    markdown = render_baseline_metrics_markdown(summarize_baseline_run(run_dir))

    assert "Classification: `cancelled_partial`" in markdown
    assert "## Metrics Found" in markdown
    assert "## Metrics Missing" in markdown
    assert "## Evidence Files Used" in markdown
    assert "## Suspected Bottlenecks" in markdown
    assert "## AutoVLA DataLoader Perf Harness Recommendations" in markdown
    assert "GPU waiting for CPU/data: `likely`" in markdown
    assert "`gpu_util_pct`: `missing`" in markdown
    assert "`data_time_ms`: `missing`" in markdown
    assert "Raw logs are not embedded" in markdown
    assert str(tmp_path) not in markdown
    assert "alex@example.com" not in markdown
