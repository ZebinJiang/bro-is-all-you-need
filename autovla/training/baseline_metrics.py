"""GR00T baseline run 的只读指标摘要器。"""

from __future__ import annotations

import ast
import json
import math
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

SCHEMA_VERSION = "autovla.baseline_metrics.v1"
MISSING = "missing"
NOT_OBSERVED = "not_observed"
NOT_PARSEABLE = "not_parseable"

_EXTERNAL_EFFECTS_FALSE = {
    "checkpoint_read": False,
    "dataset_payload_read": False,
    "gpu": False,
    "hf_network": False,
    "model_load": False,
    "network": False,
    "real_training": False,
    "slurm": False,
    "tokenizer_load": False,
    "wandb_network": False,
}
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://\S+")
_GPU_UUID_RE = re.compile(r"GPU-[0-9A-Za-z-]+")
_HOST_RE = re.compile(r"\binstance-[A-Za-z0-9-]+\b")
_TOKEN_RE = re.compile(r"(?i)\b(?:api[_-]?key|token|secret)[=:][^\s,;]+")
_ABS_PATH_RE = re.compile(r"/(?:home|mnt|tmp|var|scratch|data)/[^\s,\"']+")
_WAIT_RE = re.compile(
    r"Rank\s+(?P<rank>\d+),\s+Worker\s+(?P<worker>\d+):\s+"
    r"Wait for shard\s+(?P<shard>\d+)\s+in dataset\s+(?P<dataset>\d+)\s+"
    r"in\s+(?P<seconds>\d+(?:\.\d+)?)\s+seconds"
)
_PROGRESS_RE = re.compile(
    r"(?P<step>\d+)/(?P<total>\d+)\s+\[[^\]]*?,\s+"
    r"(?:(?P<it>\d+(?:\.\d+)?)it/s|(?P<seconds>\d+(?:\.\d+)?)s/it)"
)
_SCALAR_RE = re.compile(r"\{[^{}]*(?:'loss'|'grad_norm'|'learning_rate')[^{}]*\}")
_CANCELLED_RE = re.compile(r"CANCELLED AT (?P<timestamp>[0-9T:\-]+)")
_REQUIRED_REPORT_METRICS = (
    "samples_per_second",
    "episodes_per_second",
    "steps_per_second",
    "tokens_per_second",
    "actions_per_second",
    "step_time_p50",
    "step_time_p95",
    "total_train_time",
    "epoch_time",
    "gpu_util_pct",
    "sm_occupancy_pct",
    "hbm_mem_bw_pct",
    "gpu_memory_used_gb",
    "gpu_memory_reserved_gb",
    "gpu_wait_for_data_ms",
    "data_time_ms",
    "decode_time_ms",
    "transform_time_ms",
    "tokenization_time_ms",
    "collate_time_ms",
    "dataloader_worker_utilization",
    "dataloader_queue_depth",
    "prefetch_stall_count",
    "cache_hit_rate",
    "disk_read_mb_s",
    "network_read_mb_s",
    "allreduce_time_ms",
    "communication_time_ms",
    "communication_overlap_pct",
    "network_bw_pct",
    "val_loss",
    "action_loss",
    "checkpoint_frequency",
    "best_metric",
)


def summarize_baseline_run(run_dir: str | Path) -> dict[str, object]:
    """读取本地文本/JSON evidence 并返回可报告的 deterministic 摘要。"""
    root = Path(run_dir)
    finetune_manifest = _read_json_object(root / "outputs" / "finetune_manifest.json")
    submission_manifest = _read_json_object(root / "outputs" / "submission_manifest.json")
    stdout_text = _read_text(root / "logs" / "stdout.log")
    stderr_text = _read_text(root / "logs" / "stderr.log")
    wandb_metadata_path = _first_path(root.glob("wandb/**/files/wandb-metadata.json"))
    wandb_output_path = _first_path(root.glob("wandb/**/files/output.log"))
    wandb_metadata = _read_json_object(wandb_metadata_path) if wandb_metadata_path else {}
    wandb_output_text = _read_text(wandb_output_path) if wandb_output_path else ""
    combined_text = "\n".join(
        text for text in (stdout_text, stderr_text, wandb_output_text) if text
    )

    max_steps = _int_or_missing(finetune_manifest.get("max_steps"))
    completed_steps, planned_from_progress, last_it_per_second = _parse_progress(combined_text)
    planned_steps = max_steps if isinstance(max_steps, int) else planned_from_progress
    scalar_metrics = _parse_scalar_metrics(combined_text)
    dataloader_waits = _parse_dataloader_waits(combined_text)
    status = _classify_status(combined_text, completed_steps, planned_steps)
    training_config = _training_config(finetune_manifest, submission_manifest, root)
    throughput = _throughput(
        last_it_per_second=last_it_per_second,
        effective_batch_size=_int_or_missing(finetune_manifest.get("effective_global_batch_size")),
    )
    summary: dict[str, object] = {
        "baseline_artifact_files": _baseline_file_presence(root),
        "dataloader_waits": dataloader_waits,
        "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
        "gpu_metadata": _gpu_metadata(wandb_metadata),
        "progress": _progress(
            completed_steps=completed_steps,
            planned_steps=planned_steps,
        ),
        "redaction_markers_observed": _redaction_markers_observed(
            root,
            finetune_manifest,
            submission_manifest,
            wandb_metadata,
            combined_text,
        ),
        "scalar_metrics": scalar_metrics,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "throughput": throughput,
        "training_config": training_config,
        "wandb_local_files": _wandb_local_files(root, wandb_metadata_path, wandb_output_path),
        "warnings": _warning_counts(combined_text),
    }
    return cast(dict[str, object], _redact_value(summary, root))


def render_baseline_metrics_markdown(summary: Mapping[str, object]) -> str:
    """把已脱敏摘要渲染为稳定 Markdown 报告。"""
    status = cast(Mapping[str, object], summary["status"])
    training_config = cast(Mapping[str, object], summary["training_config"])
    progress = cast(Mapping[str, object], summary["progress"])
    scalar_metrics = cast(Mapping[str, object], summary["scalar_metrics"])
    waits = cast(Mapping[str, object], summary["dataloader_waits"])
    warnings = cast(Mapping[str, object], summary["warnings"])
    evidence_files = _evidence_file_lines(summary)
    found_metrics = _found_metric_lines(summary)
    missing_metrics = _missing_metric_lines(summary)
    bottlenecks = _bottleneck_lines(summary)
    recommendations = _recommendation_lines(summary)
    lines = [
        "# Baseline Metrics Readiness Report",
        "",
        "## Summary",
        "",
        f"- Schema: `{summary['schema_version']}`",
        f"- Classification: `{status['classification']}`",
        f"- Evidence: `{status['evidence']}`",
        f"- Model family: `{training_config['model_family']}`",
        f"- Planned max steps: `{progress['planned_max_steps']}`",
        f"- Observed completed steps: `{progress['completed_steps']}`",
        f"- Completion ratio: `{progress['completion_ratio']}`",
        "",
        "## Training Scale",
        "",
        f"- GPUs: `{training_config['num_gpus']}`",
        f"- Global batch size: `{training_config['global_batch_size']}`",
        f"- Effective batch size: `{training_config['effective_global_batch_size']}`",
        f"- Dataloader workers: `{training_config['dataloader_num_workers']}`",
        f"- Action horizon: `{training_config['action_horizon']}`",
        f"- Effective samples: `{training_config['effective_samples']}`",
        "",
        "## Observed Metrics",
        "",
        f"- Loss: `{scalar_metrics.get('loss')}`",
        f"- Grad norm: `{scalar_metrics.get('grad_norm')}`",
        f"- Learning rate: `{scalar_metrics.get('learning_rate')}`",
        f"- Dataloader wait summary: `{waits}`",
        f"- Warning summary: `{warnings}`",
        "",
        "## Metrics Found",
        "",
        *found_metrics,
        "",
        "## Metrics Missing",
        "",
        *missing_metrics,
        "",
        "## Evidence Files Used",
        "",
        *evidence_files,
        "",
        "## Suspected Bottlenecks",
        "",
        *bottlenecks,
        "",
        "## AutoVLA DataLoader Perf Harness Recommendations",
        "",
        *recommendations,
        "",
        "## Safety Boundary",
        "",
        "- Raw logs are not embedded.",
        "- Checkpoint weights, dataset payloads, W&B binary artifacts, network APIs, Slurm, GPU, "
        "real training, model loading, and tokenizer loading were not used by the summarizer.",
        "- Missing telemetry remains explicit as `missing`, `not_observed`, or `not_parseable`.",
        "",
        "## JSON Summary",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_baseline_metrics_report(run_dir: str | Path, output_path: str | Path) -> Path:
    """从本地 run artifact 写出已脱敏 Markdown 摘要报告。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_baseline_run(run_dir)
    path.write_text(render_baseline_metrics_markdown(summary), encoding="utf-8")
    return path


def _evidence_file_lines(summary: Mapping[str, object]) -> list[str]:
    """列出摘要器使用的本地 evidence 文件类型。"""
    files = cast(Mapping[str, object], summary["baseline_artifact_files"])
    wandb_files = cast(Mapping[str, object], summary["wandb_local_files"])
    lines = [f"- `{name}`: `{present}`" for name, present in sorted(files.items())]
    lines.extend(f"- `wandb.{name}`: `{present}`" for name, present in sorted(wandb_files.items()))
    return lines


def _found_metric_lines(summary: Mapping[str, object]) -> list[str]:
    """列出从本地日志中实际解析到的指标。"""
    scalar_metrics = cast(Mapping[str, object], summary["scalar_metrics"])
    throughput = cast(Mapping[str, object], summary["throughput"])
    waits = cast(Mapping[str, object], summary["dataloader_waits"])
    warnings = cast(Mapping[str, object], summary["warnings"])
    progress = cast(Mapping[str, object], summary["progress"])
    return [
        f"- `steps_per_second`: `{throughput['observed_it_per_second_last']}`",
        f"- `samples_per_second`: `{throughput['samples_per_second_last']}`",
        f"- `completed_steps`: `{progress['completed_steps']}`",
        f"- `train_loss`: `{scalar_metrics.get('loss')}`",
        f"- `grad_norm`: `{scalar_metrics.get('grad_norm')}`",
        f"- `learning_rate`: `{scalar_metrics.get('learning_rate')}`",
        f"- `gpu_wait_for_data_proxy`: `{waits}`",
        f"- `warnings`: `{warnings}`",
    ]


def _missing_metric_lines(summary: Mapping[str, object]) -> list[str]:
    """列出本地 evidence 未覆盖的性能/质量指标。"""
    throughput = cast(Mapping[str, object], summary["throughput"])
    gpu_metadata = cast(Mapping[str, object], summary["gpu_metadata"])
    scalar_metrics = cast(Mapping[str, object], summary["scalar_metrics"])
    observed = {
        "grad_norm",
        "learning_rate",
        "train_loss",
    }
    if throughput["samples_per_second_last"] not in {NOT_OBSERVED, NOT_PARSEABLE, MISSING}:
        observed.add("samples_per_second")
    if throughput["observed_it_per_second_last"] not in {NOT_OBSERVED, NOT_PARSEABLE, MISSING}:
        observed.add("steps_per_second")
    if gpu_metadata["gpu_utilization"] not in {NOT_OBSERVED, NOT_PARSEABLE, MISSING}:
        observed.add("gpu_util_pct")
    if scalar_metrics.get("loss") == NOT_OBSERVED:
        observed.discard("train_loss")

    missing = [metric for metric in _REQUIRED_REPORT_METRICS if metric not in observed]
    return [f"- `{metric}`: `missing`" for metric in missing]


def _bottleneck_lines(summary: Mapping[str, object]) -> list[str]:
    """基于本地日志代理指标生成瓶颈判断。"""
    waits = cast(Mapping[str, object], summary["dataloader_waits"])
    warnings = cast(Mapping[str, object], summary["warnings"])
    nonzero_count = waits.get("nonzero_count")
    max_seconds = waits.get("max_seconds")
    p95_seconds = waits.get("p95_seconds")
    gpu_waiting = (
        isinstance(nonzero_count, int) and nonzero_count > 0 and max_seconds != NOT_OBSERVED
    )
    if gpu_waiting:
        gpu_wait_line = (
            "- GPU waiting for CPU/data: `likely`, because local logs contain "
            f"`{nonzero_count}` nonzero dataloader shard waits, "
            f"max `{max_seconds}` seconds, p95 `{p95_seconds}` seconds."
        )
    else:
        gpu_wait_line = "- GPU waiting for CPU/data: `not_observed` in available local logs."
    return [
        gpu_wait_line,
        f"- NCCL warnings observed: `{warnings['nccl_warning_count']}`.",
        f"- Token/FLOPs telemetry gaps observed: `{warnings['token_flops_missing_count']}`.",
        "- GPU utilization, HBM bandwidth, dataloader queue depth, decode/transform/tokenization "
        "latency, and communication overlap are insufficiently instrumented in this baseline.",
    ]


def _recommendation_lines(summary: Mapping[str, object]) -> list[str]:
    """生成后续 DataLoader Perf Harness 建议。"""
    waits = cast(Mapping[str, object], summary["dataloader_waits"])
    return [
        "- Add per-step `data_time_ms`, `decode_time_ms`, `transform_time_ms`, "
        "`tokenization_time_ms`, and `collate_time_ms` timers.",
        "- Add dataloader queue-depth, worker-utilization, prefetch-stall, cache-hit-rate, "
        "and local-NVMe staging-hit-rate counters.",
        "- Add GPU wait/data-to-compute ratio thresholds before authorizing real finetune.",
        f"- Treat observed dataloader waits `{waits}` as an M3.2 harness seed signal, not as "
        "a final throughput diagnosis.",
        "- Keep W&B/HF/network optional; the harness must emit local JSON/Markdown evidence first.",
    ]


def _read_json_object(path: Path) -> dict[str, object]:
    """读取 JSON object; 缺失时返回空对象。"""
    if not path.is_file():
        return {}
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, object], loaded)


def _read_text(path: Path) -> str:
    """读取文本文件; 缺失时返回空字符串。"""
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _first_path(paths: Iterable[Path]) -> Path | None:
    """返回稳定排序后的第一个路径。"""
    sorted_paths = sorted(paths)
    return sorted_paths[0] if sorted_paths else None


def _int_or_missing(value: object) -> int | str:
    """把 JSON 字段转换为 int, 失败时显式标记 missing。"""
    if value is None:
        return MISSING
    try:
        return int(str(value))
    except ValueError:
        return NOT_PARSEABLE


def _float_stat(values: list[float]) -> dict[str, float | int] | str:
    """计算首尾最小最大指标。"""
    if not values:
        return NOT_OBSERVED
    return {
        "count": len(values),
        "first": values[0],
        "last": values[-1],
        "max": max(values),
        "min": min(values),
    }


def _parse_scalar_metrics(text: str) -> dict[str, object]:
    """从日志中的 Python dict 标量行提取 loss/grad/lr。"""
    metrics: dict[str, list[float]] = {
        "grad_norm": [],
        "learning_rate": [],
        "loss": [],
    }
    for match in _SCALAR_RE.finditer(text):
        try:
            parsed = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            continue
        if not isinstance(parsed, dict):
            continue
        parsed_metrics = cast(dict[str, object], parsed)
        for key in metrics:
            value = parsed_metrics.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            number = float(value)
            if math.isfinite(number):
                metrics[key].append(number)
    return {key: _float_stat(values) for key, values in metrics.items()}


def _parse_progress(text: str) -> tuple[int | str, int | str, float | str]:
    """从 tqdm 片段提取最大 step、计划 step 与最后 it/s。"""
    completed: int | str = MISSING
    planned: int | str = MISSING
    last_it_per_second: float | str = NOT_OBSERVED
    for match in _PROGRESS_RE.finditer(text):
        step = int(match.group("step"))
        total = int(match.group("total"))
        if not isinstance(completed, int) or step > completed:
            completed = step
            planned = total
        it_value = match.group("it")
        seconds_value = match.group("seconds")
        if it_value is not None:
            last_it_per_second = float(it_value)
        elif seconds_value is not None:
            seconds = float(seconds_value)
            last_it_per_second = 1.0 / seconds if seconds > 0 else NOT_PARSEABLE
    return completed, planned, last_it_per_second


def _progress(completed_steps: int | str, planned_steps: int | str) -> dict[str, object]:
    """构造 progress 摘要。"""
    if isinstance(completed_steps, int) and isinstance(planned_steps, int) and planned_steps > 0:
        ratio: float | str = round(completed_steps / planned_steps, 6)
    else:
        ratio = MISSING
    return {
        "completed_steps": completed_steps,
        "completion_ratio": ratio,
        "planned_max_steps": planned_steps,
    }


def _throughput(
    *,
    last_it_per_second: float | str,
    effective_batch_size: int | str,
) -> dict[str, object]:
    """构造吞吐摘要。"""
    if isinstance(last_it_per_second, float) and isinstance(effective_batch_size, int):
        samples_per_second: float | str = round(last_it_per_second * effective_batch_size, 6)
    else:
        samples_per_second = NOT_OBSERVED
    return {
        "observed_it_per_second_last": last_it_per_second,
        "progress_samples": 0 if last_it_per_second == NOT_OBSERVED else 1,
        "samples_per_second_last": samples_per_second,
    }


def _parse_dataloader_waits(text: str) -> dict[str, object]:
    """从 dataloader shard wait 行提取 GPU 饥饿代理指标。"""
    waits = [float(match.group("seconds")) for match in _WAIT_RE.finditer(text)]
    if not waits:
        return {
            "count": 0,
            "max_seconds": NOT_OBSERVED,
            "nonzero_count": 0,
            "p95_seconds": NOT_OBSERVED,
            "total_seconds": 0.0,
        }
    sorted_waits = sorted(waits)
    p95_index = max(0, math.ceil(len(sorted_waits) * 0.95) - 1)
    return {
        "count": len(waits),
        "max_seconds": max(waits),
        "nonzero_count": sum(1 for value in waits if value > 0.0),
        "p95_seconds": sorted_waits[p95_index],
        "total_seconds": round(sum(waits), 6),
    }


def _warning_counts(text: str) -> dict[str, int]:
    """统计已知训练风险提示。"""
    lowered = text.lower()
    return {
        "error_count": lowered.count("error"),
        "nccl_warning_count": text.count("NCCL"),
        "token_flops_missing_count": text.count("Could not estimate"),
        "warning_count": lowered.count("warning"),
    }


def _classify_status(
    text: str,
    completed_steps: int | str,
    planned_steps: int | str,
) -> dict[str, object]:
    """根据日志证据分类 run 状态。"""
    cancelled = _CANCELLED_RE.search(text)
    partial = (
        isinstance(completed_steps, int)
        and isinstance(planned_steps, int)
        and completed_steps < planned_steps
    )
    if cancelled and partial:
        return {
            "classification": "cancelled_partial",
            "evidence": "cancelled log marker",
            "partial_run": True,
        }
    if cancelled:
        return {
            "classification": "cancelled",
            "evidence": "cancelled log marker",
            "partial_run": partial,
        }
    if partial:
        return {
            "classification": "partial_observed",
            "evidence": "progress below planned max steps",
            "partial_run": True,
        }
    if isinstance(completed_steps, int) and isinstance(planned_steps, int):
        return {
            "classification": "completed_observed",
            "evidence": "progress reached planned max steps",
            "partial_run": False,
        }
    return {
        "classification": "unknown",
        "evidence": MISSING,
        "partial_run": MISSING,
    }


def _training_config(
    finetune_manifest: Mapping[str, object],
    submission_manifest: Mapping[str, object],
    run_dir: Path,
) -> dict[str, object]:
    """提取训练规模与 provenance 字段。"""
    return {
        "action_horizon": _int_or_missing(finetune_manifest.get("action_horizon")),
        "base_model_path": _redact_value(
            finetune_manifest.get("base_model_path", MISSING),
            run_dir,
        ),
        "dataloader_num_workers": _int_or_missing(finetune_manifest.get("dataloader_num_workers")),
        "dataset_path": _redact_value(finetune_manifest.get("dataset_path", MISSING), run_dir),
        "effective_global_batch_size": _int_or_missing(
            finetune_manifest.get("effective_global_batch_size")
        ),
        "effective_samples": _int_or_missing(finetune_manifest.get("effective_samples")),
        "global_batch_size": _int_or_missing(finetune_manifest.get("global_batch_size")),
        "model_family": finetune_manifest.get("model_family", MISSING),
        "num_gpus": _int_or_missing(finetune_manifest.get("num_gpus")),
        "planned_max_steps": _int_or_missing(finetune_manifest.get("max_steps")),
        "run_kind": submission_manifest.get("run_kind", finetune_manifest.get("run_kind", MISSING)),
        "slurm_job_id": finetune_manifest.get(
            "slurm_job_id",
            submission_manifest.get("slurm_job_id", MISSING),
        ),
        "total_episodes": _int_or_missing(finetune_manifest.get("total_episodes")),
        "total_frames": _int_or_missing(finetune_manifest.get("total_frames")),
        "train_epochs": _int_or_missing(finetune_manifest.get("train_epochs")),
        "wandb_mode": finetune_manifest.get("wandb_mode", MISSING),
    }


def _gpu_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """提取本地 W&B 元数据里的 GPU 配置, 不推断利用率。"""
    return {
        "cuda_version": metadata.get("cudaVersion", MISSING),
        "gpu_count": metadata.get("gpu_count", MISSING),
        "gpu_model": metadata.get("gpu", MISSING),
        "gpu_utilization": MISSING,
    }


def _wandb_local_files(
    root: Path,
    metadata_path: Path | None,
    output_path: Path | None,
) -> dict[str, object]:
    """记录本地 W&B 文件存在性, 不访问 W&B 服务。"""
    binary_count = len(tuple(root.glob("wandb/**/*.wandb")))
    debug_log_count = len(tuple(root.glob("wandb/**/logs/*.log")))
    return {
        "binary_artifacts": "opaque_local_artifact" if binary_count else "missing",
        "debug_log_count": debug_log_count,
        "metadata_json": "present" if metadata_path else "missing",
        "network_access": False,
        "output_log": "present" if output_path else "missing",
    }


def _baseline_file_presence(root: Path) -> dict[str, object]:
    """记录授权读取范围内的 evidence 文件存在性。"""
    return {
        "finetune_manifest": (root / "outputs" / "finetune_manifest.json").is_file(),
        "stderr_log": (root / "logs" / "stderr.log").is_file(),
        "stdout_log": (root / "logs" / "stdout.log").is_file(),
        "submission_manifest": (root / "outputs" / "submission_manifest.json").is_file(),
        "wandb_metadata_json": any(root.glob("wandb/**/files/wandb-metadata.json")),
        "wandb_output_log": any(root.glob("wandb/**/files/output.log")),
    }


def _redaction_markers_observed(
    run_dir: Path,
    finetune_manifest: Mapping[str, object],
    submission_manifest: Mapping[str, object],
    wandb_metadata: Mapping[str, object],
    combined_text: str,
) -> tuple[str, ...]:
    """记录脱敏器实际触发的 marker, 不保存原始敏感文本。"""
    source_text = json.dumps(
        {
            "finetune_manifest": finetune_manifest,
            "logs": combined_text,
            "submission_manifest": submission_manifest,
            "wandb_metadata": wandb_metadata,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    redacted = _redact_text(source_text, run_dir)
    markers = ("<EMAIL>", "<GPU_UUID>", "<HOST>", "<PATH>", "<RUN_DIR>", "<TOKEN>", "<URL>")
    return tuple(marker for marker in markers if marker in redacted)


def _redact_value(value: object, run_dir: Path) -> object:
    """递归脱敏 reportable 值。"""
    if isinstance(value, str):
        return _redact_text(value, run_dir)
    if isinstance(value, list):
        return [_redact_value(item, run_dir) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, run_dir) for item in cast(tuple[object, ...], value))
    if isinstance(value, dict):
        return {
            str(key): _redact_value(item, run_dir)
            for key, item in sorted(
                cast(dict[object, object], value).items(),
                key=lambda pair: str(pair[0]),
            )
        }
    return value


def _redact_text(text: str, run_dir: Path) -> str:
    """脱敏路径、URL、邮箱、主机、GPU UUID 和 token 形态字符串。"""
    redacted = text.replace(str(run_dir), "<RUN_DIR>")
    redacted = _URL_RE.sub("<URL>", redacted)
    redacted = _EMAIL_RE.sub("<EMAIL>", redacted)
    redacted = _GPU_UUID_RE.sub("<GPU_UUID>", redacted)
    redacted = _HOST_RE.sub("<HOST>", redacted)
    redacted = _TOKEN_RE.sub("<TOKEN>", redacted)
    redacted = _ABS_PATH_RE.sub("<PATH>", redacted)
    return redacted
