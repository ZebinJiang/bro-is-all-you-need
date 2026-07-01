"""AutoVLA format-native loader bakeoff 合同测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.perf.bakeoff import (
    FORMAT_NATIVE_LOADER_CANDIDATE_IDS,
    build_format_native_conversion_manifest,
    build_format_native_payload_contract,
    default_format_native_loader_rows,
    render_format_native_loader_markdown,
    write_format_native_loader_outputs,
)

TASK_ID = "AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001"
SOURCE_DATASET = (
    "/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/"
    "black-rubber-bellows-0622-0623-768-cmd-256-30hz"
)
WORKING_ROOT = "datasets/working/autovla_format_native_loader_bakeoff"


def test_benchmark_payload_contract_should_cover_required_modalities() -> None:
    """验证 BenchmarkPayload 合同覆盖 action、语言、三路 RGB、state 和 mask。"""
    contract = build_format_native_payload_contract(
        dataset_uri=SOURCE_DATASET,
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=98,
        state_dim=72,
        max_samples=512,
        max_episodes=4,
    )

    assert contract["schema_version"] == "autovla.format_native_benchmark_payload.v1"
    assert contract["worker_count"] == 8
    assert contract["same_subset_required"] is True
    assert contract["required_fields"] == [
        "action",
        "language",
        "rgb_camera_streams",
        "state",
        "action_mask",
    ]
    assert contract["rgb_camera_streams"] == [
        "observation.images.left_wrist_rgb",
        "observation.images.head_rgb",
        "observation.images.right_wrist_rgb",
    ]
    assert contract["state_policy"] == "present_if_required"
    assert contract["action_mask_policy"] == "present_or_derivable"
    training_window_ids = cast(list[dict[str, object]], contract["training_window_ids"])
    assert len(training_window_ids) == 512


def test_native_loader_rows_should_cover_required_candidates_and_payloads() -> None:
    """验证五个 format-native 候选均有 loader、W8 或 not-run 原因和 payload 覆盖。"""
    contract = _payload_contract()
    rows = default_format_native_loader_rows(
        payload_contract=contract,
        task_id=TASK_ID,
        generated_artifact_root=WORKING_ROOT,
    )

    assert tuple(str(row["candidate_id"]) for row in rows) == FORMAT_NATIVE_LOADER_CANDIDATE_IDS
    by_id = {str(row["candidate_id"]): row for row in rows}
    assert by_id["zjh_lerobot_v21_raw"]["run_status"] == "NOT_RUN_UNSAFE_OR_UNAVAILABLE"
    assert by_id["webdataset_converted"]["run_status"] == "RUNNABLE_NOW"
    assert by_id["webdataset_converted"]["benchmark_scope"] == "benchmarked"
    assert by_id["webdataset_converted"]["worker_count_satisfied"] is True
    assert by_id["webdataset_converted"]["worker_count_evidence_status"] == "PASS"
    assert by_id["webdataset_converted"]["sample_count"] == 512
    assert by_id["robodm_style_converted"]["run_status"] == "RUNNABLE_NOW"
    assert by_id["robodm_style_converted"]["benchmark_scope"] == "benchmarked_prototype"
    assert by_id["robodm_style_converted"]["worker_count_satisfied"] is True
    assert by_id["robodm_style_converted"]["worker_count_evidence_status"] == "PASS"
    assert by_id["robodm_style_converted"]["sample_count"] == 512
    assert by_id["lerobot_v3_converted"]["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    assert by_id["zarr_converted"]["run_status"] == "NOT_RUN_DEPENDENCY_BLOCKED"
    for row in rows:
        coverage = cast(dict[str, object], row["payload_coverage"])
        effects = cast(dict[str, bool], row["external_effects"])
        run_status = str(row["run_status"])
        assert row["worker_count_required"] == 8
        assert row["native_loader_name"]
        assert row["native_loader_path"]
        assert row["generated_artifact_root"] == WORKING_ROOT or run_status.startswith("NOT_RUN")
        assert row["run_status"] != "PASS"
        assert row["not_run_reason"] or row["benchmark_scope"] == "benchmarked"
        assert coverage["action"] is True
        assert coverage["language"] is True
        assert coverage["rgb_camera_stream_count"] == 3
        assert coverage["rgb_camera_streams"] == contract["rgb_camera_streams"]
        assert coverage["state"] == "present_if_required"
        assert coverage["action_mask"] == "present_or_derivable"
        assert all(value is False for value in effects.values())


def test_conversion_manifest_should_reject_symlink_or_source_dataset_outputs() -> None:
    """验证转换 manifest 拒绝 symlink-only 和 readonly/source 输出根。"""
    contract = _payload_contract()
    rows = default_format_native_loader_rows(
        payload_contract=contract,
        task_id=TASK_ID,
        generated_artifact_root=WORKING_ROOT,
    )

    with pytest.raises(ValueError, match="symlink-only"):
        build_format_native_conversion_manifest(
            payload_contract=contract,
            rows=rows,
            task_id=TASK_ID,
            source_dataset_uri=SOURCE_DATASET,
            generated_artifact_root=WORKING_ROOT,
            symlink_only_output=True,
        )
    with pytest.raises(ValueError, match="source dataset"):
        build_format_native_conversion_manifest(
            payload_contract=contract,
            rows=rows,
            task_id=TASK_ID,
            source_dataset_uri=SOURCE_DATASET,
            generated_artifact_root=SOURCE_DATASET,
        )
    with pytest.raises(ValueError, match="autovla_format_native_loader_bakeoff"):
        build_format_native_conversion_manifest(
            payload_contract=contract,
            rows=rows,
            task_id=TASK_ID,
            source_dataset_uri=SOURCE_DATASET,
            generated_artifact_root="runs/tmp/autovla_format_native_loader_bakeoff",
        )
    descendant_manifest = build_format_native_conversion_manifest(
        payload_contract=contract,
        rows=rows,
        task_id=TASK_ID,
        source_dataset_uri=SOURCE_DATASET,
        generated_artifact_root=f"{WORKING_ROOT}/w8-smoke",
    )
    assert descendant_manifest["generated_artifact_root"] == f"{WORKING_ROOT}/w8-smoke"


def test_format_native_outputs_should_write_report_and_safe_ledger(tmp_path: Path) -> None:
    """验证 format-native writer 产出报告、转换 manifest 和安全 ledger。"""
    contract = _payload_contract()
    rows = default_format_native_loader_rows(
        payload_contract=contract,
        task_id=TASK_ID,
        generated_artifact_root=WORKING_ROOT,
    )
    manifest = build_format_native_conversion_manifest(
        payload_contract=contract,
        rows=rows,
        task_id=TASK_ID,
        source_dataset_uri=SOURCE_DATASET,
        generated_artifact_root=WORKING_ROOT,
    )

    outputs = write_format_native_loader_outputs(
        docs_dir=tmp_path / "docs" / "benchmarks",
        output_dir=tmp_path / "runs" / "tmp" / "format-native",
        payload_contract=contract,
        rows=rows,
        conversion_manifest=manifest,
        task_id=TASK_ID,
    )

    report_text = outputs["report"].read_text(encoding="utf-8")
    docs_readme_text = outputs["docs_readme"].read_text(encoding="utf-8")
    docs_text = outputs["docs_report"].read_text(encoding="utf-8")
    ledger = json.loads(outputs["generated_artifact_ledger"].read_text(encoding="utf-8"))
    manifest_payload = json.loads(outputs["conversion_manifest"].read_text(encoding="utf-8"))

    assert outputs["report"].name == "format-native-loader-bakeoff-report.md"
    assert "Final decision class: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`" in report_text
    assert "AUTOVLA-M3-GR00T-N1D6-RAWPATH-FINETUNE-TELEMETRY-DRYRUN-001" in report_text
    assert "No converted backend winner is selected" in report_text
    assert "Compute/HPC W8 evidence exists" in report_text
    assert "`webdataset_converted`" in report_text
    assert "`robodm_style_converted` is an owned native bounded prototype" in report_text
    assert "Historical proxy/backend-reader rows are context-only" in report_text
    assert "FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md" not in docs_readme_text
    assert "Compute/HPC W8 evidence" in docs_readme_text
    assert "local generated/ignored evidence target" in docs_readme_text
    assert "zjh_lerobot_v21_raw" in docs_text
    assert "RUNNABLE_NOW" in docs_text
    assert "worker_count_evidence_status=PASS" in docs_text
    assert manifest_payload["generated_artifact_root"] == WORKING_ROOT
    assert manifest_payload["symlink_only_output_valid"] is False
    assert ledger["generated_artifacts_tracked"] is False
    assert ledger["source_dataset_mutated"] is False
    for entry in ledger["entries"]:
        assert entry["tracked_status"] == "not_staged_report_or_doc_artifact"
        assert "datasets/working" not in str(entry["path"])
        assert "datasets/readonly" not in str(entry["path"])


def test_format_native_decision_should_not_select_historical_proxy_winner() -> None:
    """验证历史 backend-reader/proxy 行不能成为 native-loader winner。"""
    contract = _payload_contract()
    rows = default_format_native_loader_rows(
        payload_contract=contract,
        task_id=TASK_ID,
        generated_artifact_root=WORKING_ROOT,
    )
    markdown = render_format_native_loader_markdown(
        payload_contract=contract,
        rows=rows,
        conversion_manifest=build_format_native_conversion_manifest(
            payload_contract=contract,
            rows=rows,
            task_id=TASK_ID,
            source_dataset_uri=SOURCE_DATASET,
            generated_artifact_root=WORKING_ROOT,
        ),
    )

    assert "Final decision class: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`" in markdown
    assert "No format-native loader winner is selected." in markdown
    assert "No converted backend winner is selected" in markdown
    assert "Compute/HPC W8 evidence exists" in markdown
    assert "RUNNABLE_NOW" in markdown
    assert "not actual Robo-DM" in markdown
    assert "Historical proxy/backend-reader rows are context-only" in markdown
    assert "historical_proxy_winner_eligible=false" in markdown


def _payload_contract() -> dict[str, object]:
    """构造测试共享 payload 合同。"""
    return build_format_native_payload_contract(
        dataset_uri=SOURCE_DATASET,
        dataset_fingerprint="dataset-fingerprint",
        sample_count=512,
        episode_count=4,
        action_dim=98,
        state_dim=72,
        max_samples=512,
        max_episodes=4,
    )
