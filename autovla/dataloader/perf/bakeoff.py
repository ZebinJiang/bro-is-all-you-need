"""AutoVLA ZJH 数据后端 bakeoff 纯报告层。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

WORKER_COUNT_REQUIRED = 8
BAKEOFF_SCHEMA_VERSION = "autovla.zjh_backend_bakeoff.v1"
SUBSET_MANIFEST_SCHEMA_VERSION = "autovla.zjh_backend_subset_manifest.v1"
LEDGER_SCHEMA_VERSION = "autovla.generated_artifact_ledger.v1"
FINAL_BACKEND_DECISION_CLASS = "READY_FOR_USER_DECISION_BACKEND"
FINAL_BACKEND_NEXT_ACTION = (
    "Manager/user must choose the backend path before any final winner, fine-tune, or "
    "training-format claim."
)

CandidateId = Literal[
    "zjh_lerobot_v21_raw",
    "lerobot_v3_view",
    "robodm_style_container",
    "webdataset_streaming",
    "zarr_chunked_store",
    "gr00t_original_dataloader",
]
RunStatus = Literal[
    "NOT_RUN_COMPUTE_PENDING",
    "NOT_RUN_DEPENDENCY_BLOCKED",
    "NOT_RUN_PROTOTYPE_ONLY",
    "NOT_RUN_UNSAFE_OR_UNAVAILABLE",
    "FAIL",
    "FAIL_NON_PRIMARY_WORKER_COUNT",
    "INSUFFICIENT_TELEMETRY",
    "PASS",
    "WARN",
]
BenchmarkScope = Literal[
    "benchmarked",
    "benchmarked_historical_non_primary_worker_count",
    "benchmarked_prototype",
    "compute_pending",
    "dependency_blocked",
    "prototype_only",
    "unsafe_or_unavailable",
]

BAKEOFF_CANDIDATE_IDS: tuple[CandidateId, ...] = (
    "zjh_lerobot_v21_raw",
    "lerobot_v3_view",
    "robodm_style_container",
    "webdataset_streaming",
    "zarr_chunked_store",
    "gr00t_original_dataloader",
)
RAW_ZJH_FIELDS: dict[str, object] = {
    "action": "action",
    "cameras": [
        "observation.images.left_wrist_rgb",
        "observation.images.head_rgb",
        "observation.images.right_wrist_rgb",
    ],
    "episode_flags": ["is_first", "is_last", "is_terminal"],
    "index": ["timestamp", "frame_index", "episode_index", "index", "task_index"],
    "language": {"source": "meta/tasks.jsonl", "task_index_field": "task_index"},
    "state": "observation.state",
}
FORMAT_NATIVE_LOADER_CANDIDATE_IDS: tuple[str, ...] = (
    "zjh_lerobot_v21_raw",
    "lerobot_v3_converted",
    "webdataset_converted",
    "robodm_style_converted",
    "zarr_converted",
)
FORMAT_NATIVE_PAYLOAD_SCHEMA_VERSION = "autovla.format_native_benchmark_payload.v1"
FORMAT_NATIVE_CONVERSION_MANIFEST_SCHEMA_VERSION = "autovla.format_native_conversion_manifest.v1"
FORMAT_NATIVE_GENERATED_ROOT = "datasets/working/autovla_format_native_loader_bakeoff"


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """描述一个 bakeoff 候选后端的可审计状态。"""

    candidate_id: CandidateId
    display_name: str
    source_format: str
    implementation_status: str
    run_status: RunStatus
    dependency_status: str
    benchmark_scope: BenchmarkScope
    prototype_only: bool
    supported_payload_fields: tuple[str, ...]
    full_training_window_supported: bool
    action_state_mask_supported: bool
    generated_artifact_root: str
    not_run_reason: str
    worker_count_required: int = WORKER_COUNT_REQUIRED

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 候选记录。"""
        return {
            "action_state_mask_supported": self.action_state_mask_supported,
            "benchmark_scope": self.benchmark_scope,
            "candidate_id": self.candidate_id,
            "dependency_status": self.dependency_status,
            "display_name": self.display_name,
            "external_effects": external_effects_false(),
            "full_training_window_supported": self.full_training_window_supported,
            "generated_artifact_root": self.generated_artifact_root,
            "implementation_status": self.implementation_status,
            "not_run_reason": self.not_run_reason,
            "prototype_only": self.prototype_only,
            "run_status": self.run_status,
            "source_format": self.source_format,
            "supported_payload_fields": list(self.supported_payload_fields),
            "worker_count_required": self.worker_count_required,
        }


def external_effects_false() -> dict[str, bool]:
    """返回 bakeoff 报告允许的外部副作用边界。"""
    return {
        "checkpoint_read": False,
        "endpoint": False,
        "hf_network": False,
        "model_load": False,
        "real_training": False,
        "robot": False,
        "tokenizer_load": False,
        "wandb_network": False,
    }


def default_candidate_registry() -> tuple[CandidateRecord, ...]:
    """构造任务卡要求的固定候选 registry。"""
    return (
        CandidateRecord(
            candidate_id="zjh_lerobot_v21_raw",
            display_name="ZJH LeRobot v2.1 raw baseline",
            source_format="lerobot-v2-compatible",
            implementation_status="ready_no_new_dependency_smoke_only",
            run_status="NOT_RUN_COMPUTE_PENDING",
            dependency_status="no_new_dependency",
            benchmark_scope="compute_pending",
            prototype_only=False,
            supported_payload_fields=(
                "action",
                "state",
                "action_mask",
                "language",
                "metadata",
                "camera_refs",
            ),
            full_training_window_supported=False,
            action_state_mask_supported=True,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/raw"
            ),
            not_run_reason="full benchmark requires Compute/HPC worker_count=8 execution",
        ),
        CandidateRecord(
            candidate_id="lerobot_v3_view",
            display_name="LeRobot v3-compatible view",
            source_format="official-lerobot-v3-dependency-route",
            implementation_status="not_run_official_lerobot_v3_dependency_blocked",
            run_status="NOT_RUN_DEPENDENCY_BLOCKED",
            dependency_status="official_lerobot_v3_dependency_not_approved",
            benchmark_scope="dependency_blocked",
            prototype_only=False,
            supported_payload_fields=(),
            full_training_window_supported=False,
            action_state_mask_supported=False,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/" "lerobot_v3_view"
            ),
            not_run_reason=(
                "official LeRobot v3 route is dependency-blocked; no native prototype is "
                "selected as a final backend"
            ),
        ),
        CandidateRecord(
            candidate_id="robodm_style_container",
            display_name="Robo-DM-style native container prototype",
            source_format="native-prototype-robodm-style",
            implementation_status="prototype_only_metadata_container",
            run_status="NOT_RUN_PROTOTYPE_ONLY",
            dependency_status="actual_robodm_dependency_license_blocked",
            benchmark_scope="prototype_only",
            prototype_only=True,
            supported_payload_fields=("action", "state", "action_mask", "metadata"),
            full_training_window_supported=False,
            action_state_mask_supported=True,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/"
                "robodm_style_container"
            ),
            not_run_reason=(
                "actual Robo-DM route is license/dependency-blocked; local row is prototype_only"
            ),
        ),
        CandidateRecord(
            candidate_id="webdataset_streaming",
            display_name="WebDataset streaming candidate",
            source_format="webdataset-package-required",
            implementation_status="not_implemented_dependency_route",
            run_status="NOT_RUN_DEPENDENCY_BLOCKED",
            dependency_status="webdataset_dependency_not_declared_on_this_branch",
            benchmark_scope="dependency_blocked",
            prototype_only=False,
            supported_payload_fields=(),
            full_training_window_supported=False,
            action_state_mask_supported=False,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/"
                "webdataset_streaming"
            ),
            not_run_reason=(
                "actual WebDataset route requires governed dependency work; PR #16 not touched"
            ),
        ),
        CandidateRecord(
            candidate_id="zarr_chunked_store",
            display_name="Zarr chunked store",
            source_format="official-zarr-dependency-route",
            implementation_status="not_run_actual_zarr_dependency_version_blocked",
            run_status="NOT_RUN_DEPENDENCY_BLOCKED",
            dependency_status="actual_zarr_python310_version_decision_missing",
            benchmark_scope="dependency_blocked",
            prototype_only=False,
            supported_payload_fields=(),
            full_training_window_supported=False,
            action_state_mask_supported=False,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/"
                "zarr_chunked_store"
            ),
            not_run_reason=(
                "actual Zarr route is dependency/version-blocked; no native prototype is "
                "selected as a final backend"
            ),
        ),
        CandidateRecord(
            candidate_id="gr00t_original_dataloader",
            display_name="Original GR00T dataloader reference",
            source_format="external-static-reference-only",
            implementation_status="not_executed_safety_review_required",
            run_status="NOT_RUN_UNSAFE_OR_UNAVAILABLE",
            dependency_status="model_training_side_effect_safety_not_proven",
            benchmark_scope="unsafe_or_unavailable",
            prototype_only=False,
            supported_payload_fields=(),
            full_training_window_supported=False,
            action_state_mask_supported=False,
            generated_artifact_root=(
                "runs/tmp/AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001/"
                "gr00t_original_dataloader"
            ),
            not_run_reason="do not execute until Model and Training prove dataloader-only safety",
        ),
    )


def build_zjh_subset_window_manifest(
    *,
    dataset_uri: str,
    dataset_fingerprint: str,
    sample_count: int,
    episode_count: int,
    action_dim: int,
    state_dim: int,
    max_samples: int,
    max_episodes: int,
    action_horizon: int = 1,
    worker_count: int = WORKER_COUNT_REQUIRED,
) -> dict[str, object]:
    """构造不读样本行的共享 ZJH 子集/window manifest。"""
    _positive_int(sample_count, "sample_count")
    _positive_int(episode_count, "episode_count")
    _positive_int(action_dim, "action_dim")
    _positive_int(state_dim, "state_dim")
    _positive_int(max_samples, "max_samples")
    _positive_int(max_episodes, "max_episodes")
    _positive_int(action_horizon, "action_horizon")
    _positive_int(worker_count, "worker_count")
    selected_samples = min(sample_count, max_samples)
    selected_episodes = min(episode_count, max_episodes)
    windows = [
        _training_window_row(
            index=index,
            episode_count=selected_episodes,
            action_dim=action_dim,
            state_dim=state_dim,
            action_horizon=action_horizon,
        )
        for index in range(selected_samples)
    ]
    payload: dict[str, object] = {
        "action_horizon": action_horizon,
        "dataset_fingerprint": _non_empty(dataset_fingerprint, "dataset_fingerprint"),
        "dataset_uri": _non_empty(dataset_uri, "dataset_uri"),
        "payload_field_specs": _payload_field_specs(
            action_dim=action_dim,
            state_dim=state_dim,
            action_horizon=action_horizon,
        ),
        "raw_zjh_fields": RAW_ZJH_FIELDS,
        "same_subset_required": True,
        "schema_version": SUBSET_MANIFEST_SCHEMA_VERSION,
        "selected_episode_count": selected_episodes,
        "selected_sample_count": selected_samples,
        "source_episode_count": episode_count,
        "source_sample_count": sample_count,
        "training_window_ids": windows,
        "worker_count": worker_count,
    }
    payload["fingerprint"] = _stable_fingerprint(payload)
    return payload


def build_initial_bakeoff_rows(
    *,
    registry: Sequence[CandidateRecord],
    subset_manifest: Mapping[str, object],
    task_id: str,
) -> list[dict[str, object]]:
    """把候选 registry 转成 dashboard 行, 不运行 benchmark。"""
    subset_id = _string(subset_manifest.get("fingerprint"), "subset fingerprint")
    rows: list[dict[str, object]] = []
    for candidate in registry:
        row = {
            **candidate.to_json_dict(),
            "benchmark_metrics": _not_run_metrics(candidate),
            "recommended_next_gate": _next_gate(candidate),
            "schema_version": f"{BAKEOFF_SCHEMA_VERSION}.row",
            "subset_fingerprint": subset_id,
            "task_id": _non_empty(task_id, "task_id"),
        }
        _validate_no_runtime_effects(row)
        rows.append(row)
    return rows


def build_format_native_payload_contract(
    *,
    dataset_uri: str,
    dataset_fingerprint: str,
    sample_count: int,
    episode_count: int,
    action_dim: int,
    state_dim: int,
    max_samples: int,
    max_episodes: int,
    action_horizon: int = 1,
    worker_count: int = WORKER_COUNT_REQUIRED,
) -> dict[str, object]:
    """构造 format-native loader 共享 BenchmarkPayload 合同。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri=dataset_uri,
        dataset_fingerprint=dataset_fingerprint,
        sample_count=sample_count,
        episode_count=episode_count,
        action_dim=action_dim,
        state_dim=state_dim,
        max_samples=max_samples,
        max_episodes=max_episodes,
        action_horizon=action_horizon,
        worker_count=worker_count,
    )
    camera_streams = _string_list(RAW_ZJH_FIELDS["cameras"])
    payload: dict[str, object] = {
        "action_dim": action_dim,
        "action_horizon": action_horizon,
        "action_mask_policy": "present_or_derivable",
        "dataset_fingerprint": subset["dataset_fingerprint"],
        "dataset_uri": subset["dataset_uri"],
        "episode_count": subset["selected_episode_count"],
        "payload_field_specs": subset["payload_field_specs"],
        "required_fields": [
            "action",
            "language",
            "rgb_camera_streams",
            "state",
            "action_mask",
        ],
        "rgb_camera_streams": camera_streams,
        "same_subset_required": True,
        "sample_count": subset["selected_sample_count"],
        "schema_version": FORMAT_NATIVE_PAYLOAD_SCHEMA_VERSION,
        "state_dim": state_dim,
        "state_policy": "present_if_required",
        "training_window_ids": subset["training_window_ids"],
        "worker_count": worker_count,
    }
    payload["fingerprint"] = _stable_fingerprint(payload)
    return payload


def default_format_native_loader_rows(
    *,
    payload_contract: Mapping[str, object],
    task_id: str,
    generated_artifact_root: str = FORMAT_NATIVE_GENERATED_ROOT,
) -> list[dict[str, object]]:
    """构造 format-native loader 五候选矩阵, 不执行转换或读取。"""
    _validate_format_native_output_policy(
        generated_artifact_root=generated_artifact_root,
        source_dataset_uri=_string(payload_contract.get("dataset_uri"), "dataset_uri"),
        symlink_only_output=False,
    )
    coverage = _format_native_payload_coverage(payload_contract)
    records: tuple[tuple[str, str, str, RunStatus, BenchmarkScope, str, str], ...] = (
        (
            "zjh_lerobot_v21_raw",
            "zjh_lerobot_v21_raw_native_loader",
            "autovla.dataloader.adapters.zjh:ZjhDatasetAdapter",
            "NOT_RUN_COMPUTE_PENDING",
            "compute_pending",
            "lerobot-v2.1 raw native loader W8 run is pending",
            "no_new_dependency_raw_loader",
        ),
        (
            "lerobot_v3_converted",
            "lerobot_v3_format_native_loader",
            "autovla.dataloader.perf.format_native_loader:lerobot_v3",
            "NOT_RUN_DEPENDENCY_BLOCKED",
            "dependency_blocked",
            "official LeRobot v3 dependency and conversion decision are not approved",
            "official_lerobot_v3_dependency_not_approved",
        ),
        (
            "webdataset_converted",
            "webdataset_format_native_loader",
            "autovla.dataloader.perf.webdataset_streaming_store:WebDatasetStreamingReader",
            "NOT_RUN_COMPUTE_PENDING",
            "compute_pending",
            "WebDataset format-native W8 converted-loader run is pending",
            "webdataset_dependency_approved_pr18",
        ),
        (
            "robodm_style_converted",
            "robodm_style_native_container_loader",
            "autovla.dataloader.perf.training_store:RoboDMStyleNativePrototype",
            "NOT_RUN_COMPUTE_PENDING",
            "compute_pending",
            "native Robo-DM-style converted-loader prototype run is pending; actual Robo-DM "
            "dependency remains blocked",
            "actual_robodm_dependency_license_blocked",
        ),
        (
            "zarr_converted",
            "zarr_format_native_loader",
            "autovla.dataloader.perf.format_native_loader:zarr_chunked",
            "NOT_RUN_DEPENDENCY_BLOCKED",
            "dependency_blocked",
            "actual Zarr dependency/version decision is missing",
            "actual_zarr_python310_version_decision_missing",
        ),
    )
    rows: list[dict[str, object]] = []
    for (
        candidate_id,
        native_loader_name,
        native_loader_path,
        run_status,
        benchmark_scope,
        not_run_reason,
        dependency_status,
    ) in records:
        row: dict[str, object] = {
            "benchmark_scope": benchmark_scope,
            "candidate_id": candidate_id,
            "conversion_artifact_policy": "write_under_datasets_working_or_not_run",
            "dependency_status": dependency_status,
            "external_effects": external_effects_false(),
            "final_decision_class": FINAL_BACKEND_DECISION_CLASS,
            "generated_artifact_root": generated_artifact_root,
            "historical_proxy_winner_eligible": False,
            "native_loader_name": native_loader_name,
            "native_loader_path": native_loader_path,
            "not_run_reason": not_run_reason,
            "payload_contract_fingerprint": payload_contract["fingerprint"],
            "payload_coverage": dict(coverage),
            "run_status": run_status,
            "schema_version": "autovla.format_native_loader_bakeoff.row.v1",
            "source_dataset_mutated": False,
            "task_id": _non_empty(task_id, "task_id"),
            "worker_count_required": WORKER_COUNT_REQUIRED,
            "worker_count_satisfied": False,
            "winner_eligible": False,
        }
        _validate_no_runtime_effects(row)
        rows.append(row)
    return rows


def build_format_native_conversion_manifest(
    *,
    payload_contract: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    task_id: str,
    source_dataset_uri: str,
    generated_artifact_root: str = FORMAT_NATIVE_GENERATED_ROOT,
    symlink_only_output: bool = False,
) -> dict[str, object]:
    """构造 format-native 转换 manifest, 并拒绝不安全输出策略。"""
    _validate_format_native_output_policy(
        generated_artifact_root=generated_artifact_root,
        source_dataset_uri=source_dataset_uri,
        symlink_only_output=symlink_only_output,
    )
    payload = {
        "candidate_ids": [row["candidate_id"] for row in rows],
        "external_effects": external_effects_false(),
        "final_decision_class": FINAL_BACKEND_DECISION_CLASS,
        "generated_artifact_root": generated_artifact_root,
        "generated_artifacts_tracked": False,
        "historical_proxy_winner_eligible": False,
        "payload_contract_fingerprint": payload_contract["fingerprint"],
        "required_candidate_ids": list(FORMAT_NATIVE_LOADER_CANDIDATE_IDS),
        "same_subset_required": payload_contract["same_subset_required"],
        "schema_version": FORMAT_NATIVE_CONVERSION_MANIFEST_SCHEMA_VERSION,
        "source_dataset_mutated": False,
        "source_dataset_uri": _non_empty(source_dataset_uri, "source_dataset_uri"),
        "symlink_only_output_valid": False,
        "task_id": _non_empty(task_id, "task_id"),
        "worker_count": WORKER_COUNT_REQUIRED,
    }
    payload["fingerprint"] = _stable_fingerprint(payload)
    return payload


def render_format_native_loader_markdown(
    *,
    payload_contract: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    conversion_manifest: Mapping[str, object],
    title: str = "AutoVLA Format-Native Loader Backend Bakeoff",
) -> str:
    """渲染 format-native loader bakeoff 报告。"""
    coverage_summary = "action/language/3_rgb_cameras/state/action_mask"
    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Payload schema: `{payload_contract['schema_version']}`",
        f"- Payload fingerprint: `{payload_contract['fingerprint']}`",
        "- Normalized BenchmarkPayload fields: action, language, all 3 RGB camera streams, "
        "state, and action_mask.",
        f"- Worker count required: `{WORKER_COUNT_REQUIRED}`.",
        f"- Generated artifact root: `{conversion_manifest['generated_artifact_root']}`.",
        "- Symlink-only output is invalid.",
        f"- Final decision class: `{FINAL_BACKEND_DECISION_CLASS}`.",
        f"- Next action: {FINAL_BACKEND_NEXT_ACTION}",
        "- No format-native loader winner is selected.",
        "- Historical proxy/backend-reader rows are context-only; "
        "historical_proxy_winner_eligible=false.",
        "- No real training, model load, checkpoint read, tokenizer load, W&B/HF network, "
        "endpoint, or robot action.",
        "",
        "## Format-Native Loader Matrix",
        "",
        "| Candidate | Native loader | Worker count | Status | Payload coverage | "
        "Generated artifact root | Winner eligible | Not-run reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            f"`{row['candidate_id']}` | "
            f"`{row['native_loader_name']}` ({row['native_loader_path']}) | "
            f"`{row['worker_count_required']}` | "
            f"`{row['run_status']}` | "
            f"`{coverage_summary}` | "
            f"`{row['generated_artifact_root']}` | "
            f"`{row['winner_eligible']}` | "
            f"{row['not_run_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Conversion Manifest Policy",
            "",
            "- Converted/generated artifacts must live under "
            "`datasets/working/autovla_format_native_loader_bakeoff/` or remain not-run.",
            "- Source dataset roots under `datasets/readonly/` are never valid output roots.",
            "- Generated benchmark/store artifacts must not be tracked or staged.",
            "- Historical backend-reader rows stay in prior dashboards only and cannot select a "
            "format-native loader winner.",
            "",
        ]
    )
    return "\n".join(lines)


def write_format_native_loader_outputs(
    *,
    docs_dir: str | Path,
    output_dir: str | Path,
    payload_contract: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
    conversion_manifest: Mapping[str, object],
    task_id: str,
) -> dict[str, Path]:
    """写出 format-native loader 报告、manifest、rows 和 ledger。"""
    output_root = Path(output_dir)
    docs_root = Path(docs_dir)
    report_text = render_format_native_loader_markdown(
        payload_contract=payload_contract,
        rows=rows,
        conversion_manifest=conversion_manifest,
    )
    report_path = output_root / "format-native-loader-bakeoff-report.md"
    rows_path = output_root / "format-native-loader-rows.json"
    payload_path = output_root / "benchmark-payload-contract.json"
    manifest_path = output_root / "format-native-conversion-manifest.json"
    docs_readme = docs_root / "README.md"
    docs_report = docs_root / "FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md"
    _write_text(report_path, report_text)
    _write_json(rows_path, {"rows": [dict(row) for row in rows]})
    _write_json(payload_path, payload_contract)
    _write_json(manifest_path, conversion_manifest)
    _write_text(docs_readme, _render_docs_readme())
    _write_text(docs_report, report_text + _render_docs_appendix())
    ledger_path = write_generated_artifact_ledger(
        output_paths=(
            report_path,
            rows_path,
            payload_path,
            manifest_path,
            docs_readme,
            docs_report,
        ),
        path=output_root / "generated-artifact-ledger.json",
        task_id=task_id,
    )
    return {
        "conversion_manifest": manifest_path,
        "docs_readme": docs_readme,
        "docs_report": docs_report,
        "generated_artifact_ledger": ledger_path,
        "payload_contract": payload_path,
        "report": report_path,
        "rows": rows_path,
    }


def load_perf_report(path: str | Path) -> dict[str, object]:
    """读取并校验 perf_report JSON object。"""
    loaded = cast(object, json.loads(Path(path).read_text(encoding="utf-8")))
    if not isinstance(loaded, Mapping):
        raise TypeError("perf_report must contain a JSON object")
    return dict(cast(Mapping[str, object], loaded))


def update_bakeoff_rows_with_compute_reports(
    *,
    rows: Sequence[Mapping[str, object]],
    raw_report: Mapping[str, object] | None = None,
    robodm_build_report: Mapping[str, object] | None = None,
    robodm_read_report: Mapping[str, object] | None = None,
    evidence_paths: Mapping[str, str | Path] | None = None,
) -> list[dict[str, object]]:
    """把 compute perf_report evidence 合并进 dashboard rows。"""
    updated: list[dict[str, object]] = [dict(row) for row in rows]
    if raw_report is not None:
        _merge_perf_report_into_candidate(
            rows=updated,
            candidate_id="zjh_lerobot_v21_raw",
            report=raw_report,
            evidence_role="raw_bounded_decode",
            evidence_path=_evidence_path(evidence_paths, "raw_report"),
        )
    if robodm_build_report is not None:
        _merge_perf_report_into_candidate(
            rows=updated,
            candidate_id="robodm_style_container",
            report=robodm_build_report,
            evidence_role="prototype_build",
            evidence_path=_evidence_path(evidence_paths, "robodm_build_report"),
        )
    if robodm_read_report is not None:
        _merge_perf_report_into_candidate(
            rows=updated,
            candidate_id="robodm_style_container",
            report=robodm_read_report,
            evidence_role="prototype_read",
            evidence_path=_evidence_path(evidence_paths, "robodm_read_report"),
        )
        robodm = _find_row(updated, "robodm_style_container")
        robodm["benchmark_scope"] = "benchmarked_prototype"
        robodm["implementation_status"] = "prototype_only_native_bounded_container_cache"
        robodm["not_run_reason"] = (
            "native bounded container-cache prototype evidence integrated; not actual Robo-DM"
        )
        robodm["prototype_only"] = True
    return updated


def update_bakeoff_rows_with_historical_webdataset_evidence(
    *,
    rows: Sequence[Mapping[str, object]],
    raw_report: Mapping[str, object],
    webdataset_build_report: Mapping[str, object],
    webdataset_read_report: Mapping[str, object],
    worker_count: int,
    evidence_paths: Mapping[str, str | Path] | None = None,
) -> list[dict[str, object]]:
    """合并历史 WebDataset evidence, 显式标记非 primary worker_count。"""
    updated: list[dict[str, object]] = [dict(row) for row in rows]
    _merge_perf_report_into_candidate(
        rows=updated,
        candidate_id="webdataset_streaming",
        report=webdataset_build_report,
        evidence_role="historical_webdataset_build",
        evidence_path=_evidence_path(evidence_paths, "webdataset_build_report"),
    )
    _merge_perf_report_into_candidate(
        rows=updated,
        candidate_id="webdataset_streaming",
        report=webdataset_read_report,
        evidence_role="historical_webdataset_read",
        evidence_path=_evidence_path(evidence_paths, "webdataset_read_report"),
    )
    webdataset = _find_row(updated, "webdataset_streaming")
    metrics = dict(_mapping(webdataset.get("benchmark_metrics"), "benchmark_metrics"))
    raw_metrics = _metrics_payload(raw_report)
    read_comparison = _mapping(
        webdataset_read_report.get("training_store_comparison"),
        "training_store_comparison",
    )
    metrics.update(
        {
            "classification": "FAIL_NON_PRIMARY_WORKER_COUNT",
            "comparator_mode": read_comparison.get("comparator_mode", "missing"),
            "comparator_valid": read_comparison.get("comparator_valid", "missing"),
            "historical_worker_count": worker_count,
            "primary_worker_count_required": WORKER_COUNT_REQUIRED,
            "raw_comparator_p50_ms": raw_metrics.get("batch_latency_ms_p50", "missing"),
            "raw_comparator_p95_ms": raw_metrics.get("batch_latency_ms_p95", "missing"),
            "recommendation": (
                "historical WebDataset evidence is performance FAIL and used for context "
                "only; rerun primary worker_count=8 before final ranking"
            ),
            "status_detail": "historical evidence used cpus_per_task=4, not primary worker_count=8",
            "worker_count": worker_count,
        }
    )
    webdataset.update(
        {
            "benchmark_scope": "benchmarked_historical_non_primary_worker_count",
            "dependency_status": "historical_webdataset_dependency_approved_pr16_only",
            "implementation_status": (
                "historical_webdataset_package_streaming_evidence_non_primary_worker_count"
            ),
            "not_run_reason": (
                "historical WebDataset package-backed compute evidence integrated; "
                "not final-comparable because worker_count=4"
            ),
            "prototype_only": False,
            "run_status": "FAIL_NON_PRIMARY_WORKER_COUNT",
        }
    )
    webdataset["benchmark_metrics"] = metrics
    _validate_no_runtime_effects(webdataset)
    return updated


def update_bakeoff_rows_with_webdataset_w8_evidence(
    *,
    rows: Sequence[Mapping[str, object]],
    raw_report: Mapping[str, object],
    webdataset_build_report: Mapping[str, object],
    webdataset_read_report: Mapping[str, object],
    evidence_paths: Mapping[str, str | Path] | None = None,
) -> list[dict[str, object]]:
    """合并 primary worker_count=8 WebDataset evidence。"""
    updated: list[dict[str, object]] = [dict(row) for row in rows]
    _merge_perf_report_into_candidate(
        rows=updated,
        candidate_id="webdataset_streaming",
        report=webdataset_build_report,
        evidence_role="webdataset_w8_build",
        evidence_path=_evidence_path(evidence_paths, "webdataset_build_report"),
    )
    _merge_perf_report_into_candidate(
        rows=updated,
        candidate_id="webdataset_streaming",
        report=webdataset_read_report,
        evidence_role="webdataset_w8_read",
        evidence_path=_evidence_path(evidence_paths, "webdataset_read_report"),
    )
    webdataset = _find_row(updated, "webdataset_streaming")
    metrics = dict(_mapping(webdataset.get("benchmark_metrics"), "benchmark_metrics"))
    raw_metrics = _metrics_payload(raw_report)
    read_comparison = _mapping(
        webdataset_read_report.get("training_store_comparison"),
        "training_store_comparison",
    )
    raw_evidence_path = _evidence_path(evidence_paths, "raw_report")
    checksum_files_checked = read_comparison.get("checksum_files_checked", "missing")
    checksum_validation_scope = read_comparison.get("checksum_validation_scope", "missing")
    metrics.update(
        {
            "checksum_files_checked": checksum_files_checked,
            "checksum_validation_scope": checksum_validation_scope,
            "checksums_verified": _checksums_verified(
                files_checked=checksum_files_checked,
                explicit_value=read_comparison.get("checksums_verified", "missing"),
                validation_scope=checksum_validation_scope,
            ),
            "comparator_mode": read_comparison.get("comparator_mode", "missing"),
            "comparator_valid": read_comparison.get("comparator_valid", "missing"),
            "full_training_window_supported": read_comparison.get(
                "full_training_window_supported",
                False,
            ),
            "media_payload_equivalent": read_comparison.get("media_payload_equivalent", False),
            "primary_worker_count_required": WORKER_COUNT_REQUIRED,
            "primary_worker_count_satisfied": True,
            "raw_comparator_p50_ms": raw_metrics.get("batch_latency_ms_p50", "missing"),
            "raw_comparator_p95_ms": raw_metrics.get("batch_latency_ms_p95", "missing"),
            "recommendation": (
                "primary worker_count=8 WebDataset evidence is integrated; final backend "
                "winner still requires Manager/user decision"
            ),
            "slurm_cpus_per_task": WORKER_COUNT_REQUIRED,
            "status_detail": "primary worker_count=8 WebDataset evidence integrated",
            "worker_count": WORKER_COUNT_REQUIRED,
        }
    )
    if raw_evidence_path is not None:
        metrics["raw_evidence_path"] = raw_evidence_path
    webdataset.update(
        {
            "benchmark_scope": "benchmarked",
            "dependency_status": "webdataset_dependency_approved_pr18",
            "implementation_status": "webdataset_package_streaming_primary_w8_evidence",
            "not_run_reason": (
                "primary worker_count=8 WebDataset package-backed compute evidence integrated"
            ),
            "prototype_only": False,
        }
    )
    webdataset["benchmark_metrics"] = metrics
    _validate_no_runtime_effects(webdataset)
    return updated


def _checksums_verified(
    *,
    files_checked: object,
    explicit_value: object,
    validation_scope: object,
) -> bool | str:
    """从 read report 的 checksum 字段推断校验状态。"""
    if isinstance(explicit_value, bool):
        return explicit_value
    if (
        isinstance(files_checked, int)
        and not isinstance(files_checked, bool)
        and files_checked > 0
        and isinstance(validation_scope, str)
        and validation_scope not in {"missing", "not_run", "none"}
    ):
        return True
    return "missing"


def _format_native_payload_coverage(
    payload_contract: Mapping[str, object],
) -> dict[str, object]:
    """根据 BenchmarkPayload 合同构造每行 payload 覆盖声明。"""
    return {
        "action": True,
        "action_mask": payload_contract["action_mask_policy"],
        "language": True,
        "rgb_camera_stream_count": len(_string_list(payload_contract["rgb_camera_streams"])),
        "rgb_camera_streams": _string_list(payload_contract["rgb_camera_streams"]),
        "state": payload_contract["state_policy"],
    }


def _validate_format_native_output_policy(
    *,
    generated_artifact_root: str,
    source_dataset_uri: str,
    symlink_only_output: bool,
) -> None:
    """拒绝 source/readonly 输出根和 symlink-only 转换结果。"""
    root = _non_empty(generated_artifact_root, "generated_artifact_root")
    source = _non_empty(source_dataset_uri, "source_dataset_uri")
    if symlink_only_output:
        raise ValueError("symlink-only output is not valid for format-native bakeoff")
    normalized_root = Path(root).as_posix().rstrip("/")
    normalized_source = Path(source).as_posix().rstrip("/")
    if "datasets/readonly" in normalized_root or normalized_root == normalized_source:
        raise ValueError("format-native output root must not be the source dataset")
    if normalized_root.startswith(normalized_source + "/"):
        raise ValueError("format-native output root must not be inside the source dataset")
    allowed = FORMAT_NATIVE_GENERATED_ROOT
    allowed_suffix = f"/{allowed}"
    is_allowed_root = (
        normalized_root == allowed
        or normalized_root.startswith(f"{allowed}/")
        or normalized_root.endswith(allowed_suffix)
        or f"{allowed_suffix}/" in normalized_root
    )
    if not is_allowed_root:
        raise ValueError(
            "format-native output root must be under "
            "datasets/working/autovla_format_native_loader_bakeoff"
        )


def webdataset_backend_recommendation_status(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """返回 WebDataset backend 决策状态, 防止缺 W8 evidence 时选 winner。"""
    row = _find_row([dict(item) for item in rows], "webdataset_streaming")
    metrics = _mapping(row.get("benchmark_metrics"), "benchmark_metrics")
    reasons: list[str] = []
    primary_satisfied = metrics.get("primary_worker_count_satisfied") is True
    if not primary_satisfied:
        reasons.append("primary worker_count=8 WebDataset evidence is missing")
        if row.get("benchmark_scope") == "benchmarked_historical_non_primary_worker_count":
            reasons.append("historical worker_count=4 evidence cannot satisfy PR18")
        return {
            "reasons": reasons,
            "status": "READY_FOR_USER_DECISION_BACKEND",
        }
    classification = str(metrics.get("classification", row.get("run_status", "missing")))
    if classification != "PASS":
        reasons.append(f"performance classification is {classification}")
    reasons.append("final backend winner is not selected")
    return {
        "reasons": reasons,
        "status": "READY_FOR_USER_DECISION_BACKEND",
    }


def render_bakeoff_markdown(
    *,
    rows: Sequence[Mapping[str, object]],
    subset_manifest: Mapping[str, object],
    title: str = "AutoVLA ZJH Data Backend Bakeoff",
) -> str:
    """渲染稳定 Markdown bakeoff 报告。"""
    subset_id = _string(subset_manifest.get("fingerprint"), "subset fingerprint")
    worker_count = _int(subset_manifest.get("worker_count"), "worker_count")
    webdataset_decision = webdataset_backend_recommendation_status(rows)
    webdataset_row = _find_row([dict(row) for row in rows], "webdataset_streaming")
    webdataset_metrics = _mapping(
        webdataset_row.get("benchmark_metrics"),
        "benchmark_metrics",
    )
    primary_w8_satisfied = webdataset_metrics.get("primary_worker_count_satisfied") is True
    historical_w4 = (
        webdataset_row.get("benchmark_scope") == "benchmarked_historical_non_primary_worker_count"
    )
    summary_lines = [
        "- Partial compute evidence is integrated; final winner remains pending.",
    ]
    if primary_w8_satisfied:
        summary_lines.extend(
            [
                "- Primary worker_count=8 WebDataset evidence is present and "
                "`primary_worker_count_satisfied=true`.",
                "- WebDataset read remains `INSUFFICIENT_TELEMETRY` because raw comparator "
                "fields were not stitched into the read report; comparator_valid=true and "
                "checksum validation passed.",
                "- Missing final requirements: final winner, Owner reviews, draft PR.",
            ]
        )
    elif historical_w4:
        summary_lines.extend(
            [
                "- Three benchmark evidence rows exist when historical WebDataset evidence is "
                "counted, but WebDataset is not primary worker_count=8 comparable.",
                "- Missing final requirements: third benchmarked candidate, final winner, Owner "
                "reviews, draft PR.",
            ]
        )
    else:
        summary_lines.extend(
            [
                "- Primary worker_count=8 WebDataset evidence is missing.",
                "- Missing final requirements: third benchmarked candidate, final winner, Owner "
                "reviews, draft PR.",
            ]
        )
    summary_lines.extend(
        [
            f"- Final decision class: `{FINAL_BACKEND_DECISION_CLASS}`.",
            f"- Next action: {FINAL_BACKEND_NEXT_ACTION}",
            "- No final backend winner is selected.",
            f"- WebDataset backend decision status: `{webdataset_decision['status']}`.",
            "- No real training, model load, checkpoint read, tokenizer load, W&B/HF network, "
            "endpoint, or robot action.",
        ]
    )
    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Schema: `{BAKEOFF_SCHEMA_VERSION}`",
        f"- Subset fingerprint: `{subset_id}`",
        f"- Fair comparison worker_count=8 required: `{worker_count == WORKER_COUNT_REQUIRED}`",
        *summary_lines,
        "",
        "## Candidate Dashboard",
        "",
        "| Candidate | Dependency status | Worker count | Batch size | Sample count | "
        "Build time | Artifact size | P50 latency | P95 latency | Samples/sec | "
        "File opens | PFS read MB/s | Estimated GPU wait | Status | Recommendation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | "
        "--- | --- |",
    ]
    for row in rows:
        metrics = _mapping(row.get("benchmark_metrics"), "benchmark_metrics")
        lines.append(
            "| "
            f"`{row['candidate_id']}` | "
            f"`{row['dependency_status']}` | "
            f"`{metrics.get('worker_count', row['worker_count_required'])}` | "
            f"`{metrics.get('batch_size', 'missing')}` | "
            f"`{metrics.get('sample_count', 'not_run')}` | "
            f"`{metrics.get('build_time_ms', 'not_run')}` | "
            f"`{metrics.get('artifact_size_bytes', 'missing')}` | "
            f"`{metrics.get('p50_ms', 'not_run')}` | "
            f"`{metrics.get('p95_ms', 'not_run')}` | "
            f"`{metrics.get('samples_per_second', 'not_run')}` | "
            f"`{metrics.get('file_opens', 'missing')}` | "
            f"`{metrics.get('pfs_read_mb_s', 'missing')}` | "
            f"`{metrics.get('estimated_gpu_wait_time_ms', 'missing')}` | "
            f"`{metrics.get('classification', row['run_status'])}` | "
            f"{metrics.get('recommendation', row['not_run_reason'])} |"
        )
    lines.extend(
        [
            "",
            "## Final Decision",
            "",
            f"- Final decision class: `{FINAL_BACKEND_DECISION_CLASS}`.",
            f"- Next action: {FINAL_BACKEND_NEXT_ACTION}",
            "- WebDataset W8 evidence is decision-support evidence, not a winner selection.",
            "- Raw W8 evidence remains a baseline, not fine-tune readiness.",
            "- Robo-DM-style evidence is a native bounded prototype; actual Robo-DM remains "
            "dependency/license-blocked.",
            "- LeRobot v3 and Zarr remain `NOT_RUN_DEPENDENCY_BLOCKED`.",
            "- GR00T original dataloader remains `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.",
            "",
            "## Shared Subset/Window Policy",
            "",
            "- All benchmarkable rows must use the same ordered `training_window_ids` manifest.",
            "- Raw ZJH fields are action=`action`, state=`observation.state`, and three "
            "declared camera refs.",
            "- Candidates without action/state/action_mask equivalence stay out of speed ranking.",
            "- Prototype rows are decision-support only and must not be named as official "
            "dependency backends.",
            "",
            "## Residual Compute Requirement",
            "",
            "- Current evidence includes raw bounded-decode, native bounded container-cache "
            "prototype, and WebDataset package-backed streaming rows where available.",
            "- Final acceptance still requires Manager/user backend decision; this dashboard "
            "does not select a final training-store winner.",
            "- W8 WebDataset evidence is primary-comparable only when "
            "`primary_worker_count_satisfied=true`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_backend_bakeoff_outputs(
    *,
    docs_dir: str | Path,
    output_dir: str | Path,
    rows: Sequence[Mapping[str, object]],
    subset_manifest: Mapping[str, object],
) -> dict[str, Path]:
    """写出 bakeoff report、subset manifest 和 docs dashboard。"""
    output_root = Path(output_dir)
    docs_root = Path(docs_dir)
    report_text = render_bakeoff_markdown(rows=rows, subset_manifest=subset_manifest)
    report_path = output_root / "backend-bakeoff-report.md"
    subset_path = output_root / "shared-subset-window-manifest.json"
    rows_path = output_root / "local-smoke-backend-rows.json"
    docs_readme = docs_root / "README.md"
    docs_bakeoff = docs_root / "DATA_PIPELINE_BACKEND_BAKEOFF.md"
    _write_text(report_path, report_text)
    _write_json(subset_path, subset_manifest)
    _write_json(
        rows_path,
        {"rows": [dict(row) for row in rows], "schema_version": BAKEOFF_SCHEMA_VERSION},
    )
    _write_text(docs_readme, _render_docs_readme())
    _write_text(docs_bakeoff, report_text + _render_docs_appendix())
    return {
        "docs_bakeoff": docs_bakeoff,
        "docs_readme": docs_readme,
        "report": report_path,
        "rows": rows_path,
        "subset_manifest": subset_path,
    }


def write_final_backend_decision_outputs(
    *,
    docs_dir: str | Path,
    output_dir: str | Path,
    rows: Sequence[Mapping[str, object]],
    subset_manifest: Mapping[str, object],
    task_id: str,
) -> dict[str, Path]:
    """写出最终后端决策闭环报告和生成物 ledger。"""
    output_root = Path(output_dir)
    docs_root = Path(docs_dir)
    report_text = render_bakeoff_markdown(
        rows=rows,
        subset_manifest=subset_manifest,
        title="AutoVLA ZJH Final Data Backend Decision",
    )
    final_report = output_root / "final-backend-decision-report.md"
    subset_path = output_root / "shared-subset-window-manifest.json"
    rows_path = output_root / "final-backend-decision-rows.json"
    docs_readme = docs_root / "README.md"
    docs_bakeoff = docs_root / "DATA_PIPELINE_BACKEND_BAKEOFF.md"
    _write_text(final_report, report_text)
    _write_json(subset_path, subset_manifest)
    _write_json(
        rows_path,
        {"rows": [dict(row) for row in rows], "schema_version": BAKEOFF_SCHEMA_VERSION},
    )
    _write_text(docs_readme, _render_docs_readme())
    _write_text(docs_bakeoff, report_text + _render_docs_appendix())
    generated_artifact_ledger = write_generated_artifact_ledger(
        output_paths=(final_report, subset_path, rows_path, docs_readme, docs_bakeoff),
        path=output_root / "generated-artifact-ledger.json",
        task_id=task_id,
    )
    return {
        "docs_bakeoff": docs_bakeoff,
        "docs_readme": docs_readme,
        "final_report": final_report,
        "generated_artifact_ledger": generated_artifact_ledger,
        "rows": rows_path,
        "subset_manifest": subset_path,
    }


def write_generated_artifact_ledger(
    *,
    output_paths: Sequence[str | Path],
    path: str | Path,
    task_id: str,
) -> Path:
    """写出稳定生成物 ledger, 不触碰 git index。"""
    ledger_path = Path(path)
    entries = [
        _artifact_entry(
            artifact_path=Path(output_path),
            task_id=task_id,
        )
        for output_path in sorted(
            (Path(item) for item in output_paths),
            key=lambda item: item.as_posix(),
        )
    ]
    payload = {
        "entries": entries,
        "generated_artifacts_tracked": False,
        "schema_version": LEDGER_SCHEMA_VERSION,
        "source_dataset_mutated": False,
        "task_id": _non_empty(task_id, "task_id"),
    }
    _write_json(ledger_path, payload)
    return ledger_path


def _not_run_metrics(candidate: CandidateRecord) -> dict[str, object]:
    """构造未运行候选的 metrics 占位。"""
    return {
        "artifact_size_bytes": "not_run",
        "batch_size": "not_run",
        "build_time_ms": "not_run",
        "build_status": "not_run",
        "classification": candidate.run_status,
        "estimated_gpu_wait_time_ms": "not_run",
        "file_opens": "not_run",
        "full_compute_metrics": "pending_or_not_run",
        "local_smoke_fixture": True,
        "media_decode_time_ms": "not_run",
        "missing_metrics": [],
        "p50_ms": "not_run",
        "pfs_read_mb_s": "not_run",
        "p95_ms": "not_run",
        "read_status": "not_run",
        "recommendation": candidate.not_run_reason,
        "repeats": "not_run",
        "sample_count": "not_run",
        "samples_per_second": "not_run",
        "status_detail": candidate.not_run_reason,
        "worker_count": candidate.worker_count_required,
    }


def _merge_perf_report_into_candidate(
    *,
    rows: list[dict[str, object]],
    candidate_id: CandidateId,
    report: Mapping[str, object],
    evidence_role: str,
    evidence_path: str | None,
) -> None:
    """把单个 perf_report 合并到候选行。"""
    row = _find_row(rows, candidate_id)
    classification = _classification_payload(report)
    metrics = _metrics_payload(report)
    summary = _summary_payload(report)
    config = _config_payload(report)
    existing = dict(_mapping(row.get("benchmark_metrics"), "benchmark_metrics"))
    classification_name = _string(
        classification.get("classification"),
        "classification.classification",
    )
    existing.update(
        {
            "artifact_size_bytes": "missing",
            "batch_size": config.get("batch_size", "missing"),
            "classification": classification_name,
            "evidence_role": evidence_role,
            "estimated_gpu_wait_time_ms": metrics.get("estimated_gpu_wait_time_ms", "missing"),
            "file_opens": summary.get("media_files_read", "missing"),
            "media_decode_time_ms": metrics.get("media_decode_time_ms", "missing"),
            "missing_metrics": _string_list(metrics.get("missing_metrics")),
            "p50_ms": metrics.get("batch_latency_ms_p50", "missing"),
            "pfs_read_mb_s": "not_applicable",
            "p95_ms": metrics.get("batch_latency_ms_p95", "missing"),
            "recommendation": _first_string(
                classification.get("recommendations"),
                default="review compute evidence",
            ),
            "sample_count": summary.get("sample_count", "missing"),
            "samples_per_second": metrics.get("samples_per_second", "missing"),
            "status_detail": "; ".join(_string_list(classification.get("reasons"))),
            "worker_count": row.get("worker_count_required", WORKER_COUNT_REQUIRED),
        }
    )
    if evidence_path is not None:
        existing["evidence_path"] = evidence_path
    if evidence_role == "raw_bounded_decode":
        existing["build_time_ms"] = "not_applicable"
        existing["build_status"] = "not_applicable"
        existing["read_status"] = "raw_bounded_decode"
        row["benchmark_scope"] = "benchmarked"
        row["not_run_reason"] = "raw bounded-decode compute evidence integrated"
        row["run_status"] = classification_name
    elif evidence_role in {
        "historical_webdataset_build",
        "prototype_build",
        "webdataset_w8_build",
    }:
        existing["build_time_ms"] = "missing"
        existing["build_status"] = classification_name
        row["run_status"] = classification_name
    elif evidence_role in {
        "historical_webdataset_read",
        "prototype_read",
        "webdataset_w8_read",
    }:
        existing["read_status"] = classification_name
        row["run_status"] = classification_name
        comparison = report.get("training_store_comparison")
        if isinstance(comparison, Mapping):
            typed_comparison = cast(Mapping[str, object], comparison)
            existing["training_store_build_time_ms"] = typed_comparison.get(
                "training_store_build_time_ms",
                "missing",
            )
            existing["training_store_read_time_ms"] = typed_comparison.get(
                "training_store_read_time_ms",
                "missing",
            )
            existing["build_time_ms"] = typed_comparison.get(
                "training_store_build_time_ms",
                "missing",
            )
            existing["file_opens"] = typed_comparison.get("pfs_file_open_count", "missing")
            existing["pfs_read_mb_s"] = typed_comparison.get("pfs_read_mb_s", "missing")
    row["benchmark_metrics"] = existing
    _validate_no_runtime_effects(row)


def _find_row(rows: list[dict[str, object]], candidate_id: CandidateId) -> dict[str, object]:
    """按 candidate id 查找 dashboard 行。"""
    for row in rows:
        if row.get("candidate_id") == candidate_id:
            return row
    raise ValueError(f"candidate row not found: {candidate_id}")


def _classification_payload(report: Mapping[str, object]) -> Mapping[str, object]:
    """读取 perf report classification。"""
    return _mapping(report.get("classification"), "classification")


def _metrics_payload(report: Mapping[str, object]) -> Mapping[str, object]:
    """读取 perf report metrics。"""
    return _mapping(report.get("metrics"), "metrics")


def _summary_payload(report: Mapping[str, object]) -> Mapping[str, object]:
    """读取 perf report dataset summary。"""
    return _mapping(report.get("dataset_probe_summary"), "dataset_probe_summary")


def _config_payload(report: Mapping[str, object]) -> Mapping[str, object]:
    """读取 perf report config。"""
    return _mapping(report.get("config"), "config")


def _evidence_path(
    evidence_paths: Mapping[str, str | Path] | None,
    key: str,
) -> str | None:
    """读取 evidence path 并转为 POSIX 字符串。"""
    if evidence_paths is None:
        return None
    value = evidence_paths.get(key)
    if value is None:
        return None
    return Path(value).as_posix()


def _training_window_row(
    *,
    index: int,
    episode_count: int,
    action_dim: int,
    state_dim: int,
    action_horizon: int,
) -> dict[str, object]:
    """构造单个稳定训练 window 标识。"""
    episode_index = index % max(episode_count, 1)
    episode_id = f"episode-{episode_index:06d}"
    sample_id = f"sample-{index:06d}"
    window_start = index
    return {
        "action_dim": action_dim,
        "action_horizon": action_horizon,
        "episode_id": episode_id,
        "episode_index": episode_index,
        "frame_index": index,
        "sample_id": sample_id,
        "state_dim": state_dim,
        "task_index": 0,
        "training_window_id": f"{episode_id}:{sample_id}:{window_start}",
        "window_start": window_start,
    }


def _payload_field_specs(
    *,
    action_dim: int,
    state_dim: int,
    action_horizon: int,
) -> dict[str, object]:
    """构造共享 payload 字段约束。"""
    return {
        "action": {
            "dtype": "float32",
            "feature_key": "action",
            "shape": [action_horizon, action_dim],
        },
        "action_mask": {"dtype": "bool", "shape": [action_horizon, action_dim]},
        "cameras": {"equivalence": "reference_only_until_media_payload_benchmark"},
        "language": {"source": "meta/tasks.jsonl", "text_field": "task"},
        "metadata": {"format": "stable_json"},
        "state": {"dtype": "float32", "feature_key": "observation.state", "shape": [state_dim]},
    }


def _artifact_entry(*, artifact_path: Path, task_id: str) -> dict[str, object]:
    """构造单个生成物 ledger 条目。"""
    artifact_type = _artifact_type(artifact_path)
    sha256 = _sha256_file(artifact_path) if artifact_path.is_file() else "missing"
    size_bytes = artifact_path.stat().st_size if artifact_path.is_file() else 0
    return {
        "artifact_path": artifact_path.as_posix(),
        "artifact_type": artifact_type,
        "candidate": "shared_bakeoff_dashboard",
        "candidate_id": "shared_bakeoff_dashboard",
        "checksum_manifest": {
            "algorithm": "sha256",
            "sha256": sha256,
        },
        "created_by": "autovla.dataloader.perf.bakeoff",
        "file_count": 1 if artifact_path.is_file() else 0,
        "git_tracked": False,
        "path": artifact_path.as_posix(),
        "reason_generated": f"{task_id} local smoke/report fixture",
        "reproduction_note": "regenerate with autovla.dataloader.perf.bakeoff writers",
        "safe_to_delete_later": True,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "source_dataset_mutated": False,
        "tracked_status": "not_staged_report_or_doc_artifact",
    }


def _artifact_type(path: Path) -> str:
    """按路径推断生成物类型。"""
    name = path.name
    if name == "DATA_PIPELINE_BACKEND_BAKEOFF.md" or "docs/benchmarks" in path.as_posix():
        return "dashboard_doc"
    if name.endswith(".md"):
        return "report"
    if name.endswith(".json"):
        return "manifest"
    return "evidence"


def _next_gate(candidate: CandidateRecord) -> str:
    """返回候选的下一步 Owner gate。"""
    if candidate.candidate_id == "zjh_lerobot_v21_raw":
        return "Compute/HPC worker_count=8 benchmark"
    if candidate.benchmark_scope == "prototype_only":
        return "Architecture/Quality decide whether prototype should become runnable"
    if candidate.benchmark_scope == "dependency_blocked":
        return "Tooling/Quality dependency approval"
    return "Model+Training dataloader-only safety proof"


def _render_docs_readme() -> str:
    """渲染 docs/benchmarks 入口。"""
    return "\n".join(
        [
            "# AutoVLA Benchmark Dashboards",
            "",
            "- [Data Pipeline Backend Bakeoff](DATA_PIPELINE_BACKEND_BAKEOFF.md)",
            "",
            "This directory records decision-support dashboards only. The ZJH backend bakeoff",
            "does not authorize real training, model loading, external network use, or dataset",
            "writes.",
            "The format-native loader report remains task-local generated evidence under",
            "`runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/` and is not",
            "linked from tracked docs while its generated Markdown target remains ignored.",
            f"Final decision class: `{FINAL_BACKEND_DECISION_CLASS}`.",
            f"Next action: {FINAL_BACKEND_NEXT_ACTION}",
            "",
        ]
    )


def _render_docs_appendix() -> str:
    """渲染文档附录。"""
    return "\n".join(
        [
            "",
            "## Publication Notes",
            "",
            "- `zjh_lerobot_v21_raw` is the no-new-dependency raw baseline.",
            "- `prototype_only` rows are native metadata/report scaffolds, not official backend "
            "claims.",
            "- Dependency-backed official routes remain blocked until their exact dependency "
            "gates pass.",
            "- Generated store/media/checkpoint/model artifacts must stay out of git.",
            "",
        ]
    )


def _stable_fingerprint(payload: Mapping[str, object]) -> str:
    """对 JSON-safe payload 生成稳定 SHA256。"""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    """写出 UTF-8 文本。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _validate_no_runtime_effects(row: Mapping[str, object]) -> None:
    """防止候选行携带真实运行副作用。"""
    effects = row.get("external_effects")
    if not isinstance(effects, Mapping):
        raise ValueError("external_effects must be present")
    typed_effects = cast(Mapping[str, object], effects)
    for key, value in typed_effects.items():
        if value is not False:
            raise ValueError(f"runtime effect must be false: {key}")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """校验并返回 mapping。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return cast(Mapping[str, object], value)


def _string_list(value: object) -> list[str]:
    """读取字符串列表, 非字符串项被忽略。"""
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [item for item in values if isinstance(item, str)]


def _first_string(value: object, *, default: str) -> str:
    """读取字符串列表首项。"""
    strings = _string_list(value)
    if strings:
        return strings[0]
    return default


def _non_empty(value: str, name: str) -> str:
    """校验非空字符串。"""
    if not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _string(value: object, name: str) -> str:
    """校验 mapping 中的字符串值。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _int(value: object, name: str) -> int:
    """校验 mapping 中的 int 值。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int")
    return value


def _positive_int(value: int, name: str) -> int:
    """校验正整数。"""
    if isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive int")
    return value
