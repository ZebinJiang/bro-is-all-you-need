"""PR30 actual dataloader worker benchmark tests。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autovla.dataloader.perf.actual_dataloader_worker_bakeoff import (
    CANDIDATE_MATRIX,
    ActualWorkerBenchmarkConfig,
    ActualWorkerRunner,
    BenchmarkPayload,
    collate_benchmark_batch,
    run_actual_worker_bakeoff,
    validate_benchmark_payload,
)


def test_actual_worker_bakeoff_should_emit_d1_to_d6_rows_and_tiny_artifacts(
    tmp_path: Path,
) -> None:
    """验证 W1 tiny fixture 产出 D1-D6 行和真实 worker 证据。"""
    output_dir = tmp_path / "runs" / "tmp" / "actual-worker"
    working_root = tmp_path / "datasets" / "working" / "autovla_actual_worker_bakeoff_v1"
    result = run_actual_worker_bakeoff(
        ActualWorkerBenchmarkConfig(
            batch_size=2,
            max_samples=8,
            output_dir=output_dir,
            source_dataset=tmp_path / "readonly" / "tiny",
            use_tiny_fixture=True,
            worker_count=2,
            working_root=working_root,
        )
    )
    assert result.conclusion == "REQUEST_CHANGES_REMAIN"

    by_candidate = {row["candidate"]: row for row in result.rows}
    assert set(by_candidate) == {candidate.candidate_id for candidate in CANDIDATE_MATRIX}
    assert by_candidate["zjh_zarr_cache"]["status"] == "NOT_IMPLEMENTED_IN_CURRENT_PR"
    for candidate in (
        "zjh_lerobot_v21_autovla_adapter",
        "zjh_lerobot_v3_local",
        "zjh_webdataset_tar",
        "zjh_robodm_container_v1",
    ):
        row = by_candidate[candidate]
        assert row["status"] == "RUN"
        assert row["actual_worker_count"] == 2
        assert row["worker_count_evidence_status"] == "PASS"
        assert row["payload_complete"] is True
        assert row["payload_missing_fields"] == []
        assert row["manifest_checksum"] == result.manifest_checksum

    assert by_candidate["zjh_lerobot_v21_gr00t_or_lerobot_native"]["status"] == (
        "NOT_RUN_UNSAFE_OR_UNAVAILABLE"
    )
    assert result.raw_json_path.is_file()
    assert result.summary_markdown_path.is_file()
    assert result.worker_evidence_json_path.is_file()
    assert result.generated_artifact_ledger_path.is_file()
    assert (
        result.source_dataset_mutation_check_path.read_text(encoding="utf-8")
        .strip()
        .endswith("PASS")
    )

    missing = json.loads((output_dir / "missing_telemetry_table.json").read_text())["rows"]
    assert any(
        row["candidate"] == "zjh_lerobot_v21_gr00t_or_lerobot_native"
        and row["metric"] == "worker_read_timing"
        and row["blocking"] is True
        for row in missing
    )
    assert any(
        row["candidate"] == "zjh_webdataset_tar"
        and row["metric"] == "persistent_workers_matrix"
        and row["blocking"] is True
        for row in missing
    )

    decision = json.loads((output_dir / "backend_decision_table.json").read_text())["rows"][0]
    assert decision["decision"] == "NO_BACKEND_WINNER"
    assert decision["mandatory_comparability_gates_pass"] is False
    assert decision["blocking_missing_telemetry"] is True

    audit_rows = json.loads((output_dir / "agent_result_consistency_audit.json").read_text())[
        "rows"
    ]
    runnable_audit = [
        row for row in audit_rows if row["classification"] == "TRACEABLE_BUT_METHODOLOGY_LIMITED"
    ]
    assert runnable_audit
    for row in runnable_audit:
        assert row["aggregate_matches_raw_timings"] is True
        assert row["final_backend_winner"] is False


def test_worker_runner_should_record_serial_and_process_worker_modes(tmp_path: Path) -> None:
    """验证 worker_count=0 与 worker_count>0 都给出数字化执行证据。"""
    payload_path = tmp_path / "payloads.jsonl"
    _write_payloads(payload_path, sample_count=4)

    serial = ActualWorkerRunner(worker_count=0, batch_size=2).run_payload_file(payload_path)
    assert serial.actual_worker_count == 0
    assert serial.execution_mode == "serial"
    assert serial.multiprocessing_enabled is False
    assert serial.worker_count_evidence_status == "PASS"

    process = ActualWorkerRunner(worker_count=2, batch_size=2).run_payload_file(payload_path)
    assert process.actual_worker_count == 2
    assert process.execution_mode == "process_pool"
    assert process.multiprocessing_enabled is True
    assert process.worker_count_evidence_status == "PASS"
    assert sorted(process.per_worker_sample_counts.values()) == [2, 2]


def test_payload_contract_should_reject_camera_refs_only_and_collate_hashes() -> None:
    """验证 RUN payload 不能只提供 camera_refs, batch hash 需稳定。"""
    valid = _payload("sample-000000")
    validate_benchmark_payload(valid)
    batch = collate_benchmark_batch([valid, _payload("sample-000001")])
    assert batch.sample_ids == ("sample-000000", "sample-000001")
    assert batch.payload_hash

    invalid = dict(valid.to_json_dict())
    invalid.pop("camera_rgb_0")
    invalid["camera_refs"] = ["a.mp4", "b.mp4", "c.mp4"]
    with pytest.raises(ValueError, match="camera_rgb_0"):
        validate_benchmark_payload(BenchmarkPayload.from_json_dict(invalid))


def test_rows_with_unmeasured_worker_count_must_not_be_run(tmp_path: Path) -> None:
    """验证缺少 actual worker 证据时不能标为 RUN。"""
    payload_path = tmp_path / "payloads.jsonl"
    _write_payloads(payload_path, sample_count=2)
    evidence = ActualWorkerRunner(worker_count=2, batch_size=1).run_payload_file(
        payload_path,
        force_unmeasured_for_test=True,
    )
    assert evidence.worker_count_evidence_status == "BLOCKED_ACTUAL_WORKER_COUNT_NOT_MEASURED"
    assert evidence.actual_worker_count == "not_measured"


def test_actual_worker_cli_help_and_tiny_execution(tmp_path: Path) -> None:
    """验证 CLI help 与 tiny fixture execution 可被 Compute 后续复用。"""
    help_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf.actual_dataloader_worker_bakeoff",
            "--help",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert help_result.returncode == 0
    assert "--worker-count" in help_result.stdout
    assert "--worker-counts" in help_result.stdout
    assert "--gr00t-root" in help_result.stdout

    output_dir = tmp_path / "runs" / "tmp" / "cli"
    working_root = tmp_path / "datasets" / "working" / "autovla_actual_worker_bakeoff_v1"
    run_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf.actual_dataloader_worker_bakeoff",
            "--source-dataset",
            str(tmp_path / "readonly" / "tiny"),
            "--working-root",
            str(working_root),
            "--output-dir",
            str(output_dir),
            "--worker-count",
            "2",
            "--batch-size",
            "2",
            "--max-samples",
            "4",
            "--worker-counts",
            "0,2",
            "--batch-sizes",
            "2",
            "--warmup-batches",
            "0",
            "--measured-batches",
            "1",
            "--repeats",
            "1",
            "--max-episodes",
            "4",
            "--candidates",
            "zjh_lerobot_v21_autovla_adapter,zjh_lerobot_v3_local",
            "--gr00t-root",
            str(tmp_path / "Isaac-GR00T17"),
            "--tiny-fixture",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert run_result.returncode == 0, run_result.stderr
    assert (output_dir / "worker_count_0_batch_size_2" / "actual_worker_bakeoff_raw.json").is_file()
    assert (output_dir / "worker_count_2_batch_size_2" / "actual_worker_bakeoff_raw.json").is_file()


def _write_payloads(path: Path, *, sample_count: int) -> None:
    """写入测试用 JSONL payload artifact。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_payload(f"sample-{index:06d}").to_json_dict() for index in range(sample_count)]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")


def _payload(sample_id: str) -> BenchmarkPayload:
    """构造一个完整 BenchmarkPayload。"""
    return BenchmarkPayload(
        action=(1.0, 2.0, 3.0),
        action_mask=(True, True, False),
        camera_rgb_0=b"rgb0" + sample_id.encode("utf-8"),
        camera_rgb_1=b"rgb1" + sample_id.encode("utf-8"),
        camera_rgb_2=b"rgb2" + sample_id.encode("utf-8"),
        episode_id="episode-000000",
        language="tiny task",
        sample_id=sample_id,
        state=(0.0, 1.0, 2.0),
        window_id=f"window-{sample_id}",
    )
