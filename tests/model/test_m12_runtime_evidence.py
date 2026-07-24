"""M12 多收据运行证据、迁移和激活门测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.cli.models import ModelStatusCategory, project_status_categories
from autovla.models.activation import ActivationBlocker, evaluate_activation
from autovla.models.readiness import (
    DeepSpeedStage,
    DistributedStrategyKind,
    ModelFamilyReadiness,
    ModelFamilyReadinessSnapshot,
    PrecisionMode,
    ReadinessAxis,
    ReadinessEvidenceReceipt,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeEvidenceSet,
    RuntimeOperation,
    RuntimeTopology,
    RuntimeValidationKey,
)
from autovla.models.readiness_io import (
    M12_SCHEMA_VERSION,
    ReadinessPersistenceError,
    decode_readiness_document,
    read_readiness_file,
    write_readiness_file,
)

ROOT = Path(__file__).resolve().parents[2]
FAMILY = "gr00t_n1d6"
DEFINITION = "1" * 64
PROFILE = "2" * 64
LOCK = "3" * 64
ENVIRONMENT = "4" * 64
ASSET = "5" * 64
CHECKPOINT = "6" * 64
DATA = "7" * 64
COMMAND = "8" * 64
SOURCE_SHA = "9" * 40
EVIDENCE = "e" * 64


def _key(
    operation: RuntimeOperation,
    *,
    strategy: DistributedStrategyKind = DistributedStrategyKind.SINGLE_GPU,
    topology: RuntimeTopology | None = None,
    command_fingerprint: str = COMMAND,
    definition_fingerprint: str = DEFINITION,
) -> RuntimeValidationKey:
    """构造一条完整、可激活的测试验证键。"""

    selected_topology = topology or RuntimeTopology(1, 1, 1, "NVIDIA-A100-SXM4-80GB")
    checkpoint = (
        None
        if operation
        in {
            RuntimeOperation.CONSTRUCTION,
            RuntimeOperation.PROCESSOR,
            RuntimeOperation.DATA_BINDING,
        }
        else CHECKPOINT
    )
    data_binding = (
        DATA
        if operation
        in {
            RuntimeOperation.PROCESSOR,
            RuntimeOperation.FORWARD,
            RuntimeOperation.BACKWARD,
            RuntimeOperation.OPTIMIZER_STEP,
            RuntimeOperation.PREDICTION,
            RuntimeOperation.DECODE,
            RuntimeOperation.DATA_BINDING,
            RuntimeOperation.PROFILING,
        }
        else None
    )
    return RuntimeValidationKey(
        family_key=FAMILY,
        definition_fingerprint=definition_fingerprint,
        operation=operation,
        runtime_profile_fingerprint=PROFILE,
        runtime_lock_fingerprint=LOCK,
        environment_fingerprint=ENVIRONMENT,
        asset_fingerprint=ASSET,
        checkpoint_fingerprint=checkpoint,
        data_binding_fingerprint=data_binding,
        source_sha=SOURCE_SHA,
        command_fingerprint=command_fingerprint,
        evidence_artifact_fingerprint=EVIDENCE,
        strategy=strategy,
        deepspeed_stage=(
            DeepSpeedStage.ZERO2
            if strategy is DistributedStrategyKind.DEEPSPEED
            else DeepSpeedStage.NONE
        ),
        topology=selected_topology,
        precision=PrecisionMode.BF16,
        checkpoint_mode="weights_only",
    )


def _receipt(
    receipt_id: str,
    key: RuntimeValidationKey,
    *,
    passed: bool = True,
) -> RuntimeEvidenceReceipt:
    """构造一条新 M12 运行收据。"""

    artifact_fingerprint = key.evidence_artifact_fingerprint
    assert artifact_fingerprint is not None
    return RuntimeEvidenceReceipt(
        receipt_id=receipt_id,
        validation_key=key,
        evidence_kind=RuntimeEvidenceKind.RUNTIME,
        artifact_fingerprint=artifact_fingerprint,
        passed=passed,
    )


def _source_receipt() -> RuntimeEvidenceReceipt:
    """构造不会激活运行路径的源码收据。"""

    return RuntimeEvidenceReceipt(
        receipt_id="source-complete",
        validation_key=RuntimeValidationKey(
            family_key=FAMILY,
            definition_fingerprint=DEFINITION,
            operation=RuntimeOperation.CONSTRUCTION,
            source_sha=SOURCE_SHA,
            command_fingerprint="a" * 64,
            evidence_artifact_fingerprint="b" * 64,
        ),
        evidence_kind=RuntimeEvidenceKind.SOURCE,
        artifact_fingerprint="b" * 64,
        passed=True,
    )


def test_multi_receipt_set_preserves_topologies_and_is_deterministic() -> None:
    """同一家族的 DDP 与 ZeRO 拓扑必须共存且输入顺序不影响输出。"""

    ddp = _receipt(
        "c-ddp",
        _key(
            RuntimeOperation.FORWARD,
            strategy=DistributedStrategyKind.DDP,
            topology=RuntimeTopology(1, 2, 2, "NVIDIA-A100-SXM4-80GB"),
            command_fingerprint="c" * 64,
        ),
    )
    zero = _receipt(
        "d-zero",
        _key(
            RuntimeOperation.FORWARD,
            strategy=DistributedStrategyKind.DEEPSPEED,
            topology=RuntimeTopology(1, 4, 4, "NVIDIA-A100-SXM4-80GB"),
            command_fingerprint="d" * 64,
        ),
    )

    first = RuntimeEvidenceSet.derive((ddp, zero))
    second = RuntimeEvidenceSet.derive((zero, ddp))

    assert first == second
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
    assert {receipt.validation_key.topology for receipt in first.receipts} == {
        RuntimeTopology(1, 2, 2, "NVIDIA-A100-SXM4-80GB"),
        RuntimeTopology(1, 4, 4, "NVIDIA-A100-SXM4-80GB"),
    }


def test_one_receipt_does_not_promote_an_unrelated_operation() -> None:
    """前向收据不得提升优化器操作或对应 CLI 类别。"""

    forward = _receipt("e-forward", _key(RuntimeOperation.FORWARD))
    snapshot = ModelFamilyReadinessSnapshot.derive(
        FAMILY,
        DEFINITION,
        (_source_receipt(), forward),
    )

    assert snapshot.projection.forward_validated
    assert not snapshot.projection.training_validated
    assert project_status_categories(snapshot) == (
        ModelStatusCategory.ACTIVE_DEVELOPMENT,
        ModelStatusCategory.SOURCE_EXECUTABLE,
    )
    decision = evaluate_activation(snapshot, _key(RuntimeOperation.OPTIMIZER_STEP))
    assert not decision.authorized
    assert decision.blocker is ActivationBlocker.MISSING_EXACT_OPERATION_EVIDENCE


def test_runtime_identity_rejects_partial_sha_bool_int_and_impossible_strategy() -> None:
    """动态身份边界拒绝短 SHA、布尔整数和不可能策略组合。"""

    with pytest.raises(ValueError, match="complete lowercase Git SHA"):
        RuntimeValidationKey(
            family_key=FAMILY,
            definition_fingerprint=DEFINITION,
            operation=RuntimeOperation.CONSTRUCTION,
            source_sha="9" * 12,
        )
    with pytest.raises(TypeError, match="exact int"):
        RuntimeTopology(True, 1, 1, "A100")
    with pytest.raises(ValueError, match="world_size"):
        RuntimeTopology(2, 3, 2, "A100")
    with pytest.raises(ValueError, match="ZeRO stage"):
        RuntimeValidationKey(
            family_key=FAMILY,
            definition_fingerprint=DEFINITION,
            operation=RuntimeOperation.CONSTRUCTION,
            strategy=DistributedStrategyKind.DEEPSPEED,
            topology=RuntimeTopology(1, 1, 1, "A100"),
        )
    with pytest.raises(ValueError, match="stale"):
        ModelFamilyReadinessSnapshot.derive(
            FAMILY,
            DEFINITION,
            (
                _receipt(
                    "f-stale", _key(RuntimeOperation.CONSTRUCTION, definition_fingerprint="f" * 64)
                ),
            ),
        )


def test_activation_requires_the_exact_operation_and_topology_key() -> None:
    """仅完全相等且成功的新运行收据可以通过激活门。"""

    key = _key(
        RuntimeOperation.FORWARD,
        strategy=DistributedStrategyKind.DDP,
        topology=RuntimeTopology(1, 2, 2, "NVIDIA-A100-SXM4-80GB"),
    )
    snapshot = ModelFamilyReadinessSnapshot.derive(
        FAMILY,
        DEFINITION,
        (_source_receipt(), _receipt("a-forward", key)),
    )

    accepted = evaluate_activation(snapshot, key)
    mismatched = evaluate_activation(
        snapshot,
        _key(
            RuntimeOperation.FORWARD,
            strategy=DistributedStrategyKind.DDP,
            topology=RuntimeTopology(2, 4, 2, "NVIDIA-A100-SXM4-80GB"),
        ),
    )

    assert accepted.authorized
    assert accepted.receipt_id == "a-forward"
    assert not mismatched.authorized
    assert mismatched.blocker is ActivationBlocker.EXACT_RUNTIME_IDENTITY_MISMATCH


def test_m12_round_trip_is_atomic_strict_and_does_not_store_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M12 文件原子往返,未知字段与替换失败均关闭。"""

    snapshot = ModelFamilyReadinessSnapshot.derive(
        FAMILY,
        DEFINITION,
        (_source_receipt(), _receipt("b-forward", _key(RuntimeOperation.FORWARD))),
    )
    target = tmp_path / "readiness.json"
    write_readiness_file(target, {FAMILY: snapshot})
    serialized = cast(dict[str, object], json.loads(target.read_text(encoding="utf-8")))

    assert serialized["schema_version"] == M12_SCHEMA_VERSION
    assert "projection" not in target.read_text(encoding="utf-8")
    assert read_readiness_file(target, {FAMILY: DEFINITION}) == {FAMILY: snapshot}

    corrupted = dict(serialized)
    corrupted["projection"] = {}
    with pytest.raises(ReadinessPersistenceError, match="unknown"):
        decode_readiness_document(corrupted, {FAMILY: DEFINITION})

    original_text = target.read_text(encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        """模拟原子替换失败。"""

        del source, destination
        raise OSError("replace failed")

    monkeypatch.setattr("autovla.models.readiness_io.os.replace", fail_replace)
    with pytest.raises(ReadinessPersistenceError, match="atomic"):
        write_readiness_file(target, {FAMILY: snapshot})
    assert target.read_text(encoding="utf-8") == original_text
    assert not tuple(tmp_path.glob(".readiness.json.*.tmp"))


def test_m11_snapshot_migrates_in_memory_as_historical_and_writes_only_m12(
    tmp_path: Path,
) -> None:
    """旧快照保持可读,但迁移收据不得激活且后续只写 M12。"""

    from autovla.models.readiness import (
        ConstructionReadiness,
        DefinitionReadiness,
        EvidenceValidationKind,
    )
    from autovla.models.registry import get_model_family_spec

    definition = get_model_family_spec("gr00t_n1d7")
    old = ModelFamilyReadiness.derive(
        definition,
        (
            ReadinessEvidenceReceipt(
                evidence_id="m11-source",
                family_key=definition.family_key,
                definition_fingerprint=definition.fingerprint,
                axis=ReadinessAxis.DEFINITION,
                state=DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE,
                validation_kind=EvidenceValidationKind.SOURCE,
                artifact_fingerprint="c" * 64,
            ),
            ReadinessEvidenceReceipt(
                evidence_id="m11-construction",
                family_key=definition.family_key,
                definition_fingerprint=definition.fingerprint,
                axis=ReadinessAxis.CONSTRUCTION,
                state=ConstructionReadiness.SOURCE_CONSTRUCTIBLE,
                validation_kind=EvidenceValidationKind.SOURCE,
                artifact_fingerprint="d" * 64,
            ),
        ),
    )
    old_path = tmp_path / "m11.json"
    old_path.write_text(old.to_json() + "\n", encoding="utf-8")

    migrated = read_readiness_file(old_path, {definition.family_key: definition})
    snapshot = migrated[definition.family_key]

    assert snapshot.projection.source_available
    assert snapshot.projection.historical_receipt_count == 2
    assert all(receipt.historical for receipt in snapshot.evidence.receipts)
    new_path = tmp_path / "m12.json"
    write_readiness_file(new_path, migrated)
    assert json.loads(new_path.read_text(encoding="utf-8"))["schema_version"] == M12_SCHEMA_VERSION
    assert old_path.read_text(encoding="utf-8") == old.to_json() + "\n"


def test_corrupt_or_partial_persistence_fails_closed(tmp_path: Path) -> None:
    """截断 JSON 和字段缺失不得返回部分 readiness。"""

    target = tmp_path / "readiness.json"
    target.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(ReadinessPersistenceError, match="corrupt"):
        read_readiness_file(target, {FAMILY: DEFINITION})

    with pytest.raises(ReadinessPersistenceError, match="missing"):
        decode_readiness_document(
            {
                "schema_version": M12_SCHEMA_VERSION,
                "families": [{"family_key": FAMILY}],
            },
            {FAMILY: DEFINITION},
        )


def test_fresh_import_remains_free_of_torch_and_family_implementation() -> None:
    """新 readiness、IO、激活与 CLI 导入保持轻量。"""

    script = """
import sys
import autovla.models.readiness
import autovla.models.readiness_io
import autovla.models.activation
import autovla.cli.models
forbidden = {'torch', 'transformers', 'deepspeed', 'jax', 'flax', 'orbax'}
assert not forbidden & set(sys.modules)
private_prefixes = (
    'autovla.models.families.gr00t_n1d6',
    'autovla.models.families.gr00t_n1d7',
    'autovla.models.families.pi0_5',
)
assert not any(name.startswith(private_prefixes) for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
