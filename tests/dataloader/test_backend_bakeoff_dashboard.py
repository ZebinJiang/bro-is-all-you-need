"""AutoVLA 数据后端 bakeoff/dashboard 测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from autovla.dataloader.perf.bakeoff import (
    BAKEOFF_CANDIDATE_IDS,
    build_initial_bakeoff_rows,
    build_zjh_subset_window_manifest,
    default_candidate_registry,
    render_bakeoff_markdown,
    update_bakeoff_rows_with_compute_reports,
    update_bakeoff_rows_with_historical_webdataset_evidence,
    update_bakeoff_rows_with_webdataset_w8_evidence,
    webdataset_backend_recommendation_status,
    write_backend_bakeoff_outputs,
    write_final_backend_decision_outputs,
    write_generated_artifact_ledger,
)


def test_candidate_registry_should_preserve_required_ids_and_blocked_statuses() -> None:
    """验证候选 registry 保留任务卡 ID 并诚实标注阻塞状态。"""
    registry = default_candidate_registry()

    assert tuple(candidate.candidate_id for candidate in registry) == BAKEOFF_CANDIDATE_IDS
    by_id = {candidate.candidate_id: candidate for candidate in registry}
    assert by_id["zjh_lerobot_v21_raw"].run_status == "NOT_RUN_COMPUTE_PENDING"
    assert by_id["zjh_lerobot_v21_raw"].dependency_status == "no_new_dependency"
    assert by_id["webdataset_streaming"].run_status == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["lerobot_v3_view"].run_status == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["lerobot_v3_view"].benchmark_scope == "dependency_blocked"
    assert by_id["lerobot_v3_view"].prototype_only is False
    assert by_id["robodm_style_container"].prototype_only is True
    assert by_id["zarr_chunked_store"].run_status == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["zarr_chunked_store"].benchmark_scope == "dependency_blocked"
    assert by_id["zarr_chunked_store"].prototype_only is False
    assert by_id["gr00t_original_dataloader"].run_status == "NOT_RUN_UNSAFE_OR_UNAVAILABLE"
    assert by_id["gr00t_original_dataloader"].action_state_mask_supported is False

    for candidate in registry:
        payload = candidate.to_json_dict()
        assert payload["candidate_id"] == candidate.candidate_id
        assert payload["worker_count_required"] == 8
        assert not candidate.generated_artifact_root.startswith("datasets/readonly")
        assert "genesisvla" not in json.dumps(payload, sort_keys=True).lower()
        assert payload["external_effects"] == {
            "checkpoint_read": False,
            "endpoint": False,
            "hf_network": False,
            "model_load": False,
            "real_training": False,
            "robot": False,
            "tokenizer_load": False,
            "wandb_network": False,
        }


def test_subset_window_manifest_should_be_deterministic_and_field_complete() -> None:
    """验证共享子集/window manifest 可重复且包含 ZJH 原始字段。"""
    left = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=6,
        episode_count=3,
        action_dim=7,
        state_dim=14,
        max_samples=5,
        max_episodes=2,
    )
    right = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=6,
        episode_count=3,
        action_dim=7,
        state_dim=14,
        max_samples=5,
        max_episodes=2,
    )

    assert left == right
    assert left["fingerprint"] == right["fingerprint"]
    assert left["worker_count"] == 8
    assert left["same_subset_required"] is True
    assert left["selected_sample_count"] == 5
    assert left["selected_episode_count"] == 2
    raw_zjh_fields = cast(dict[str, object], left["raw_zjh_fields"])
    assert raw_zjh_fields["action"] == "action"
    assert raw_zjh_fields["state"] == "observation.state"
    assert raw_zjh_fields["cameras"] == [
        "observation.images.left_wrist_rgb",
        "observation.images.head_rgb",
        "observation.images.right_wrist_rgb",
    ]
    windows = cast(list[dict[str, object]], left["training_window_ids"])
    assert len(windows) == 5
    assert windows[0] == {
        "action_dim": 7,
        "action_horizon": 1,
        "episode_id": "episode-000000",
        "episode_index": 0,
        "frame_index": 0,
        "sample_id": "sample-000000",
        "state_dim": 14,
        "task_index": 0,
        "training_window_id": "episode-000000:sample-000000:0",
        "window_start": 0,
    }


def test_report_and_ledger_should_render_pending_compute_dashboard(tmp_path: Path) -> None:
    """验证本地 smoke 输出、报告、ledger 与 dashboard 稳定写出。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=8,
        episode_count=4,
        action_dim=2,
        state_dim=3,
        max_samples=4,
        max_episodes=2,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001",
    )
    report_text = render_bakeoff_markdown(
        rows=rows,
        subset_manifest=subset,
        title="AutoVLA ZJH Data Backend Bakeoff",
    )

    assert "| `zjh_lerobot_v21_raw` |" in report_text
    assert "worker_count=8" in report_text
    assert "NOT_RUN_DEPENDENCY_BLOCKED" in report_text
    assert "No real training" in report_text
    assert sum(row["benchmark_scope"] == "compute_pending" for row in rows) == 1
    assert sum(row["benchmark_scope"] == "prototype_only" for row in rows) >= 1
    assert sum(row["benchmark_scope"] == "dependency_blocked" for row in rows) >= 3
    assert all(row["worker_count_required"] == 8 for row in rows)
    assert all(row["subset_fingerprint"] == subset["fingerprint"] for row in rows)
    metrics_rows = [cast(dict[str, object], row["benchmark_metrics"]) for row in rows]
    assert all(metrics["p50_ms"] == "not_run" for metrics in metrics_rows)
    assert all(metrics["p95_ms"] == "not_run" for metrics in metrics_rows)

    output_paths = write_backend_bakeoff_outputs(
        docs_dir=tmp_path / "docs" / "benchmarks",
        output_dir=tmp_path / "runs" / "tmp" / "task",
        rows=rows,
        subset_manifest=subset,
    )
    ledger_path = write_generated_artifact_ledger(
        output_paths=tuple(output_paths.values()),
        path=tmp_path / "runs" / "tmp" / "task" / "generated-artifact-ledger.json",
        task_id="AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001",
    )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["generated_artifacts_tracked"] is False
    assert ledger["source_dataset_mutated"] is False
    assert {entry["artifact_type"] for entry in ledger["entries"]} >= {
        "dashboard_doc",
        "report",
    }
    for entry in ledger["entries"]:
        assert set(entry) >= {
            "candidate",
            "checksum_manifest",
            "created_by",
            "file_count",
            "path",
            "safe_to_delete_later",
            "size_bytes",
            "tracked_status",
        }
        assert entry["file_count"] == 1
        assert entry["safe_to_delete_later"] is True
        assert entry["tracked_status"] == "not_staged_report_or_doc_artifact"
    assert output_paths["report"].is_file()
    assert output_paths["docs_readme"].is_file()
    assert output_paths["docs_bakeoff"].is_file()
    assert "prototype_only" in output_paths["docs_bakeoff"].read_text(encoding="utf-8")
    assert "StarVLA" not in output_paths["docs_bakeoff"].read_text(encoding="utf-8")


def test_compute_report_ingestion_should_update_raw_and_prototype_rows() -> None:
    """验证 compute perf_report 可更新 raw 与原生 prototype 行。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=2,
        state_dim=3,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001",
    )

    updated = update_bakeoff_rows_with_compute_reports(
        rows=rows,
        raw_report=_raw_fail_report(),
        robodm_build_report=_store_build_report(),
        robodm_read_report=_store_read_report(),
        evidence_paths={
            "raw_report": "runs/tmp/task/compute/raw-bounded-decode/perf_report.json",
            "robodm_build_report": (
                "runs/tmp/task/compute/robodm-style-store-build/perf_report.json"
            ),
            "robodm_read_report": "runs/tmp/task/compute/robodm-style-store-read/perf_report.json",
        },
    )
    by_id = {str(row["candidate_id"]): row for row in updated}
    raw = by_id["zjh_lerobot_v21_raw"]
    robodm = by_id["robodm_style_container"]
    webdataset = by_id["webdataset_streaming"]
    zarr = by_id["zarr_chunked_store"]
    gr00t = by_id["gr00t_original_dataloader"]

    raw_metrics = cast(dict[str, object], raw["benchmark_metrics"])
    robodm_metrics = cast(dict[str, object], robodm["benchmark_metrics"])
    raw_effects = cast(dict[str, object], raw["external_effects"])
    robodm_effects = cast(dict[str, object], robodm["external_effects"])

    assert raw["run_status"] == "FAIL"
    assert raw["benchmark_scope"] == "benchmarked"
    assert raw_metrics["worker_count"] == 8
    assert raw_metrics["sample_count"] == 512
    assert raw_metrics["batch_size"] == "missing"
    assert raw_metrics["build_time_ms"] == "not_applicable"
    assert raw_metrics["artifact_size_bytes"] == "missing"
    assert raw_metrics["p50_ms"] == 6.055724
    assert raw_metrics["p95_ms"] == 6.055724
    assert raw_metrics["media_decode_time_ms"] == 23.20258
    assert raw_metrics["samples_per_second"] == 84548.106882
    assert raw_metrics["file_opens"] == 12
    assert raw_metrics["pfs_read_mb_s"] == "not_applicable"
    assert raw_metrics["estimated_gpu_wait_time_ms"] == 0.0
    assert raw_metrics["classification"] == "FAIL"
    assert "media_decode_time_ms dominates" in str(raw_metrics["status_detail"])
    assert all(value is False for value in raw_effects.values())

    assert robodm["run_status"] == "INSUFFICIENT_TELEMETRY"
    assert robodm["benchmark_scope"] == "benchmarked_prototype"
    assert robodm["prototype_only"] is True
    assert robodm_metrics["build_status"] == "INSUFFICIENT_TELEMETRY"
    assert robodm_metrics["read_status"] == "INSUFFICIENT_TELEMETRY"
    assert robodm_metrics["sample_count"] == 512
    assert robodm_metrics["batch_size"] == "missing"
    assert robodm_metrics["build_time_ms"] == 49.798713
    assert robodm_metrics["artifact_size_bytes"] == "missing"
    assert robodm_metrics["p50_ms"] == 9.264098
    assert robodm_metrics["p95_ms"] == 9.264098
    assert robodm_metrics["media_decode_time_ms"] == 0.0
    assert robodm_metrics["samples_per_second"] == 55267.118288
    assert robodm_metrics["file_opens"] == 6
    assert robodm_metrics["pfs_read_mb_s"] == 47.125842
    assert robodm_metrics["estimated_gpu_wait_time_ms"] == 0.0
    assert "actual Robo-DM" not in str(robodm["implementation_status"])
    assert all(value is False for value in robodm_effects.values())

    assert webdataset["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert zarr["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert zarr["benchmark_scope"] == "dependency_blocked"
    assert gr00t["run_status"] == "NOT_RUN_UNSAFE_OR_UNAVAILABLE"

    markdown = render_bakeoff_markdown(rows=updated, subset_manifest=subset)
    assert (
        "| Candidate | Dependency status | Worker count | Batch size | Sample count | "
        "Build time | Artifact size | P50 latency | P95 latency | Samples/sec | "
        "File opens | PFS read MB/s | Estimated GPU wait | Status | Recommendation |"
    ) in markdown
    assert "FAIL" in markdown
    assert "INSUFFICIENT_TELEMETRY" in markdown
    assert "84548.106882" in markdown
    assert "49.798713" in markdown
    assert "47.125842" in markdown
    assert "`12` | `not_applicable` | `0.0` | `FAIL`" in markdown
    assert "`6` | `47.125842` | `0.0` | `INSUFFICIENT_TELEMETRY`" in markdown
    assert "NOT_RUN_UNSAFE_OR_UNAVAILABLE" in markdown


def test_historical_webdataset_evidence_should_not_count_as_primary_worker_row() -> None:
    """验证历史 WebDataset evidence 不会伪装成 worker_count=8 主比较行。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=2,
        state_dim=3,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-ZJH-DATA-BACKEND-BAKEOFF-AND-DASHBOARD-001",
    )

    updated = update_bakeoff_rows_with_historical_webdataset_evidence(
        rows=rows,
        raw_report=_historical_webdataset_raw_report(),
        webdataset_build_report=_historical_webdataset_build_report(),
        webdataset_read_report=_historical_webdataset_read_report(),
        worker_count=4,
        evidence_paths={
            "webdataset_build_report": "runs/tmp/history/webdataset-build/perf_report.json",
            "webdataset_read_report": "runs/tmp/history/webdataset-read/perf_report.json",
        },
    )
    by_id = {str(row["candidate_id"]): row for row in updated}
    webdataset = by_id["webdataset_streaming"]
    metrics = cast(dict[str, object], webdataset["benchmark_metrics"])

    assert webdataset["run_status"] == "FAIL_NON_PRIMARY_WORKER_COUNT"
    assert webdataset["benchmark_scope"] == "benchmarked_historical_non_primary_worker_count"
    assert webdataset["dependency_status"] == "historical_webdataset_dependency_approved_pr16_only"
    assert metrics["worker_count"] == 4
    assert metrics["primary_worker_count_required"] == 8
    assert metrics["historical_worker_count"] == 4
    assert metrics["sample_count"] == 512
    assert metrics["build_time_ms"] == 954.466104
    assert metrics["p50_ms"] == 476.634326
    assert metrics["p95_ms"] == 476.634326
    assert metrics["samples_per_second"] == 1074.198756
    assert metrics["file_opens"] == 6
    assert metrics["pfs_read_mb_s"] == 6.480499
    assert metrics["comparator_mode"] == "action_state_mask_only"
    assert metrics["comparator_valid"] is True
    assert metrics["raw_comparator_p50_ms"] == 6.568576
    assert "worker_count=8" in str(metrics["recommendation"])

    markdown = render_bakeoff_markdown(rows=updated, subset_manifest=subset)
    assert "FAIL_NON_PRIMARY_WORKER_COUNT" in markdown
    assert "`webdataset_streaming`" in markdown
    assert "`4` | `missing` | `512` | `954.466104`" in markdown
    assert "rerun primary worker_count=8 before final ranking" in markdown
    assert (
        "Three benchmark evidence rows exist when historical WebDataset evidence is counted"
        in markdown
    )
    assert "primary-comparable only when `primary_worker_count_satisfied=true`" in markdown


def test_webdataset_w8_evidence_should_render_as_primary_comparable_row() -> None:
    """验证 worker_count=8 WebDataset evidence 才能成为 primary comparable 行。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=2,
        state_dim=3,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-PR18-WEBDATASET-W8-COMPARABLE-BENCHMARK-001",
    )
    updated = update_bakeoff_rows_with_webdataset_w8_evidence(
        rows=rows,
        raw_report=_historical_webdataset_raw_report(),
        webdataset_build_report=_historical_webdataset_build_report(),
        webdataset_read_report=_historical_webdataset_read_report(),
        evidence_paths={
            "webdataset_build_report": "runs/tmp/pr18/webdataset-build/perf_report.json",
            "webdataset_read_report": "runs/tmp/pr18/webdataset-read/perf_report.json",
        },
    )
    by_id = {str(row["candidate_id"]): row for row in updated}
    webdataset = by_id["webdataset_streaming"]
    metrics = cast(dict[str, object], webdataset["benchmark_metrics"])
    decision = webdataset_backend_recommendation_status(updated)

    assert webdataset["run_status"] == "FAIL"
    assert webdataset["benchmark_scope"] == "benchmarked"
    assert webdataset["dependency_status"] == "webdataset_dependency_approved_pr18"
    assert metrics["worker_count"] == 8
    assert metrics["primary_worker_count_satisfied"] is True
    assert metrics["raw_comparator_p50_ms"] == 6.568576
    assert decision["status"] == "READY_FOR_USER_DECISION_BACKEND"
    assert "performance classification is FAIL" in str(decision["reasons"])
    assert "final backend winner is not selected" in str(decision["reasons"])

    markdown = render_bakeoff_markdown(rows=updated, subset_manifest=subset)
    assert "`webdataset_streaming` | `webdataset_dependency_approved_pr18` | `8`" in markdown
    assert "READY_FOR_USER_DECISION_BACKEND" in markdown


def test_webdataset_w8_insufficient_telemetry_should_keep_decision_gate() -> None:
    """验证 job 1901 W8 evidence 已存在但不能声明最终 winner。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=98,
        state_dim=72,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-PR18-WEBDATASET-W8-COMPARABLE-BENCHMARK-001",
    )
    updated = update_bakeoff_rows_with_webdataset_w8_evidence(
        rows=rows,
        raw_report=_webdataset_w8_raw_report(),
        webdataset_build_report=_webdataset_w8_build_report(),
        webdataset_read_report=_webdataset_w8_read_report(),
        evidence_paths={
            "raw_report": "runs/tmp/pr18/compute/w8/raw-bounded-decode/perf_report.json",
            "webdataset_build_report": "runs/tmp/pr18/compute/w8/webdataset-build/perf_report.json",
            "webdataset_read_report": "runs/tmp/pr18/compute/w8/webdataset-read/perf_report.json",
        },
    )
    by_id = {str(row["candidate_id"]): row for row in updated}
    webdataset = by_id["webdataset_streaming"]
    metrics = cast(dict[str, object], webdataset["benchmark_metrics"])
    decision = webdataset_backend_recommendation_status(updated)

    assert webdataset["run_status"] == "INSUFFICIENT_TELEMETRY"
    assert metrics["worker_count"] == 8
    assert metrics["primary_worker_count_satisfied"] is True
    assert metrics["slurm_cpus_per_task"] == 8
    assert metrics["comparator_valid"] is True
    assert metrics["comparator_mode"] == "action_state_mask_only"
    assert metrics["checksum_validation_scope"] == "open_boundary_once"
    assert metrics["checksums_verified"] is True
    assert metrics["checksum_files_checked"] == 6
    assert metrics["raw_comparator_p50_ms"] == 1.992976
    assert metrics["p50_ms"] == 348.007695
    assert metrics["pfs_read_mb_s"] == 8.768431
    assert decision["status"] == "READY_FOR_USER_DECISION_BACKEND"
    assert "performance classification is INSUFFICIENT_TELEMETRY" in str(decision["reasons"])

    markdown = render_bakeoff_markdown(rows=updated, subset_manifest=subset)
    assert "Primary worker_count=8 WebDataset evidence is present" in markdown
    assert "WebDataset read remains `INSUFFICIENT_TELEMETRY`" in markdown
    assert "WebDataset is not primary worker_count=8 comparable" not in markdown
    assert "third benchmarked candidate" not in markdown
    assert "`webdataset_streaming` | `webdataset_dependency_approved_pr18` | `8`" in markdown


def test_final_backend_decision_closure_should_render_explicit_gate() -> None:
    """验证最终闭环文档显式保留用户决策门, 不选择 winner。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=98,
        state_dim=72,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-FINAL-DATA-BACKEND-DECISION-CLOSURE-001",
    )
    rows = update_bakeoff_rows_with_compute_reports(
        rows=rows,
        raw_report=_webdataset_w8_raw_report(),
        robodm_build_report=_store_build_report(),
        robodm_read_report=_store_read_report(),
    )
    rows = update_bakeoff_rows_with_webdataset_w8_evidence(
        rows=rows,
        raw_report=_webdataset_w8_raw_report(),
        webdataset_build_report=_webdataset_w8_build_report(),
        webdataset_read_report=_webdataset_w8_read_report(),
    )

    by_id = {str(row["candidate_id"]): row for row in rows}
    markdown = render_bakeoff_markdown(rows=rows, subset_manifest=subset)

    assert set(by_id) == set(BAKEOFF_CANDIDATE_IDS)
    assert "Final decision class: `READY_FOR_USER_DECISION_BACKEND`" in markdown
    assert "Next action:" in markdown
    assert "No final backend winner is selected." in markdown
    assert by_id["lerobot_v3_view"]["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["zarr_chunked_store"]["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["robodm_style_container"]["benchmark_scope"] == "benchmarked_prototype"
    assert by_id["robodm_style_container"]["prototype_only"] is True
    assert by_id["webdataset_streaming"]["run_status"] == "INSUFFICIENT_TELEMETRY"
    assert by_id["gr00t_original_dataloader"]["run_status"] == "NOT_RUN_UNSAFE_OR_UNAVAILABLE"
    for row in rows:
        metrics = cast(dict[str, object], row["benchmark_metrics"])
        if row["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED":
            assert row["not_run_reason"]
        else:
            assert metrics["worker_count"] == 8


def test_final_backend_decision_writer_should_create_report_and_safe_ledger(
    tmp_path: Path,
) -> None:
    """验证最终闭环 writer 产出指定 report 与不可发布生成物 ledger。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=98,
        state_dim=72,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-FINAL-DATA-BACKEND-DECISION-CLOSURE-001",
    )
    outputs = write_final_backend_decision_outputs(
        docs_dir=tmp_path / "docs" / "benchmarks",
        output_dir=tmp_path / "runs" / "tmp" / "final",
        rows=rows,
        subset_manifest=subset,
        task_id="AUTOVLA-M3-FINAL-DATA-BACKEND-DECISION-CLOSURE-001",
    )

    report_text = outputs["final_report"].read_text(encoding="utf-8")
    ledger = json.loads(outputs["generated_artifact_ledger"].read_text(encoding="utf-8"))
    readme_text = outputs["docs_bakeoff"].read_text(encoding="utf-8")
    docs_readme_text = outputs["docs_readme"].read_text(encoding="utf-8")

    assert outputs["final_report"].name == "final-backend-decision-report.md"
    assert "Final decision class: `READY_FOR_USER_DECISION_BACKEND`" in report_text
    assert "Next action:" in report_text
    assert "Final decision class: `READY_FOR_USER_DECISION_BACKEND`" in readme_text
    assert "Final decision class: `READY_FOR_USER_DECISION_BACKEND`" in docs_readme_text
    assert ledger["generated_artifacts_tracked"] is False
    assert ledger["source_dataset_mutated"] is False
    for entry in ledger["entries"]:
        assert entry["tracked_status"] == "not_staged_report_or_doc_artifact"
        assert "datasets/working" not in str(entry["path"])
        assert "datasets/derived" not in str(entry["path"])
        assert not (
            "runs/tmp" in str(entry["path"])
            and entry["tracked_status"] == "tracked_publishable_artifact"
        )


def test_root_readme_should_match_final_backend_decision_status() -> None:
    """验证 root README 的紧凑 dashboard 不落后于最终决策文档。"""
    readme_text = Path("README.md").read_text(encoding="utf-8")

    assert "Final decision class: `READY_FOR_USER_DECISION_BACKEND`" in readme_text
    assert "Next action: Manager/user must choose the backend path" in readme_text
    assert "No final backend winner or training format has been selected." in readme_text
    assert "webdataset_streaming" in readme_text


def test_missing_webdataset_w8_evidence_should_request_backend_decision() -> None:
    """验证只有历史 W4 evidence 时不能满足 PR18 primary W8 决策。"""
    subset = build_zjh_subset_window_manifest(
        dataset_uri="/datasets/readonly/zjh",
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=2,
        state_dim=3,
        max_samples=512,
        max_episodes=4,
    )
    rows = build_initial_bakeoff_rows(
        registry=default_candidate_registry(),
        subset_manifest=subset,
        task_id="AUTOVLA-M3-PR18-WEBDATASET-W8-COMPARABLE-BENCHMARK-001",
    )
    updated = update_bakeoff_rows_with_historical_webdataset_evidence(
        rows=rows,
        raw_report=_historical_webdataset_raw_report(),
        webdataset_build_report=_historical_webdataset_build_report(),
        webdataset_read_report=_historical_webdataset_read_report(),
        worker_count=4,
    )
    decision = webdataset_backend_recommendation_status(updated)

    assert decision["status"] == "READY_FOR_USER_DECISION_BACKEND"
    assert "primary worker_count=8 WebDataset evidence is missing" in str(decision["reasons"])
    assert "historical worker_count=4 evidence cannot satisfy PR18" in str(decision["reasons"])


def _raw_fail_report() -> dict[str, object]:
    """构造 raw bounded-decode FAIL compute 报告。"""
    return {
        "classification": {
            "classification": "FAIL",
            "reasons": ["media_decode_time_ms dominates per-batch time"],
            "recommendations": ["build a PFS-backed Training Store before training"],
        },
        "config": {
            "mode": "bounded-decode",
            "output_dir": "runs/tmp/task/compute/raw-bounded-decode",
        },
        "dataset_probe_summary": {
            "episode_count": 4,
            "media_files_read": 12,
            "sample_count": 512,
        },
        "metrics": {
            "batch_latency_ms_p50": 6.055724,
            "batch_latency_ms_p95": 6.055724,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 23.20258,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 84548.106882,
        },
    }


def _historical_webdataset_raw_report() -> dict[str, object]:
    """构造历史 WebDataset 同批 raw comparator 报告。"""
    payload = _raw_fail_report()
    metrics = cast(dict[str, object], payload["metrics"])
    metrics["batch_latency_ms_p50"] = 6.568576
    metrics["batch_latency_ms_p95"] = 6.568576
    metrics["media_decode_time_ms"] = 21.34071
    return payload


def _historical_webdataset_build_report() -> dict[str, object]:
    """构造历史 WebDataset build 报告。"""
    return {
        "classification": {
            "classification": "INSUFFICIENT_TELEMETRY",
            "reasons": ["missing GPU telemetry"],
            "recommendations": ["collect nvidia-smi telemetry on compute node if available"],
        },
        "config": {"mode": "pfs-training-store-build-webdataset"},
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 3.014078,
            "batch_latency_ms_p95": 3.014078,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 169869.525606,
        },
    }


def _historical_webdataset_read_report() -> dict[str, object]:
    """构造历史 WebDataset read FAIL 报告。"""
    return {
        "classification": {
            "classification": "FAIL",
            "reasons": ["training-store read is not materially faster"],
            "recommendations": ["keep PR draft and revisit store format or recording format"],
        },
        "config": {"mode": "pfs-training-store-read-webdataset"},
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 476.634326,
            "batch_latency_ms_p95": 476.634326,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 1074.198756,
        },
        "training_store_comparison": {
            "comparator_mode": "action_state_mask_only",
            "comparator_valid": True,
            "pfs_file_open_count": 6,
            "pfs_read_mb_s": 6.480499,
            "training_store_build_time_ms": 954.466104,
            "training_store_read_time_ms": 476.634326,
        },
    }


def _webdataset_w8_raw_report() -> dict[str, object]:
    """构造 job 1901 raw bounded-decode W8 报告。"""
    return {
        "classification": {
            "classification": "FAIL",
            "reasons": ["media_decode_time_ms dominates per-batch time"],
            "recommendations": ["build a PFS-backed Training Store before training"],
        },
        "config": {"mode": "bounded-decode"},
        "dataset_probe_summary": {
            "episode_count": 4,
            "media_files_read": 12,
            "sample_count": 512,
        },
        "metrics": {
            "batch_latency_ms_p50": 1.992976,
            "batch_latency_ms_p95": 1.992976,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 18.557223,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 256902.240669,
        },
    }


def _webdataset_w8_build_report() -> dict[str, object]:
    """构造 job 1901 WebDataset build W8 报告。"""
    return {
        "classification": {
            "classification": "INSUFFICIENT_TELEMETRY",
            "reasons": ["missing GPU telemetry"],
            "recommendations": ["collect nvidia-smi telemetry on compute node if available"],
        },
        "config": {"mode": "pfs-training-store-build-webdataset"},
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 1.935577,
            "batch_latency_ms_p95": 1.935577,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 264520.605484,
        },
    }


def _webdataset_w8_read_report() -> dict[str, object]:
    """构造 job 1901 WebDataset read W8 报告。"""
    return {
        "classification": {
            "classification": "INSUFFICIENT_TELEMETRY",
            "reasons": ["missing effective raw bounded-decode comparison latency"],
            "recommendations": [
                "run bounded raw decode and store-read benchmark in one compute evidence pass"
            ],
        },
        "config": {"mode": "pfs-training-store-read-webdataset"},
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 348.007695,
            "batch_latency_ms_p95": 348.007695,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["raw_batch_latency_ms_p50", "raw_media_decode_time_ms"],
            "samples_per_second": 1471.231836,
        },
        "training_store_comparison": {
            "checksum_files_checked": 6,
            "checksum_validation_scope": "open_boundary_once",
            "comparator_mode": "action_state_mask_only",
            "comparator_valid": True,
            "pfs_file_open_count": 6,
            "pfs_read_mb_s": 8.768431,
            "training_store_build_time_ms": 592.675342,
            "training_store_read_time_ms": 348.007695,
        },
    }


def _store_build_report() -> dict[str, object]:
    """构造 Robo-DM-style build INSUFFICIENT_TELEMETRY 报告。"""
    return {
        "classification": {
            "classification": "INSUFFICIENT_TELEMETRY",
            "reasons": ["missing GPU telemetry"],
            "recommendations": ["collect nvidia-smi telemetry on compute node if available"],
        },
        "config": {"mode": "store-build-bounded"},
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 2.347183,
            "batch_latency_ms_p95": 2.347183,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["gpu_util_pct"],
            "samples_per_second": 218133.822544,
        },
    }


def _store_read_report() -> dict[str, object]:
    """构造 Robo-DM-style read INSUFFICIENT_TELEMETRY 报告。"""
    return {
        "classification": {
            "classification": "INSUFFICIENT_TELEMETRY",
            "reasons": ["missing effective raw bounded-decode comparison latency"],
            "recommendations": [
                "run bounded raw decode and store-read benchmark in one compute evidence pass"
            ],
        },
        "config": {
            "mode": "store-read-benchmark",
            "training_store_dir": (
                "/home/cz-jzb/workspace/vla-flywheel/datasets/working/"
                "autovla_backend_bakeoff/robodm_style_container/20260701T000000Z"
            ),
        },
        "dataset_probe_summary": {"episode_count": 4, "sample_count": 512},
        "metrics": {
            "batch_latency_ms_p50": 9.264098,
            "batch_latency_ms_p95": 9.264098,
            "estimated_gpu_wait_time_ms": 0.0,
            "media_decode_time_ms": 0.0,
            "missing_metrics": ["raw_batch_latency_ms_p50", "raw_media_decode_time_ms"],
            "samples_per_second": 55267.118288,
        },
        "training_store_comparison": {
            "pfs_file_open_count": 6,
            "pfs_read_mb_s": 47.125842,
            "training_store_build_time_ms": 49.798713,
            "training_store_read_time_ms": 9.264098,
        },
    }
