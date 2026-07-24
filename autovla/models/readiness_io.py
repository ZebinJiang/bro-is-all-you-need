"""模型运行证据的严格版本迁移与原子持久化边界。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar, cast

from autovla.models.activation import (
    RuntimeActivationReceipt,
    require_promotable_activation,
)
from autovla.models.families.specification import ModelFamilyDefinition
from autovla.models.readiness import (
    DeepSpeedStage,
    DistributedStrategyKind,
    EvidenceValidationKind,
    ModelFamilyReadinessSnapshot,
    PrecisionMode,
    ReadinessAxis,
    ReadinessEvidenceReceipt,
    ReadinessValue,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeEvidenceSet,
    RuntimeOperation,
    RuntimeTopology,
    RuntimeValidationKey,
    default_readiness_states,
    readiness_state_type,
)
from autovla.runtime_profiles.contracts import RuntimeExecutionReceipt
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

M11_SCHEMA_VERSION = "autovla.model_readiness.m11.v1"
M12_SCHEMA_VERSION = "autovla.runtime_readiness.m12.v1"
M12_PROMOTABLE_SCHEMA_VERSION = "autovla.promotable_runtime_readiness.m12.v1"
_MAX_READINESS_BYTES = 16 * 1024 * 1024
_EnumT = TypeVar("_EnumT", bound=Enum)


class ReadinessPersistenceError(ValueError):
    """表示 readiness 文件不完整、损坏或身份不匹配。"""


@dataclass(frozen=True, slots=True)
class PromotableReadinessDocument:
    """保存 readiness 投影和经 canonical 执行链重验的 promotion 收据。"""

    snapshots: Mapping[str, ModelFamilyReadinessSnapshot]
    promotions: Mapping[str, RuntimeActivationReceipt]

    def __post_init__(self) -> None:
        """冻结映射并拒绝 promotion 脱离对应 snapshot。"""

        snapshots = dict(self.snapshots)
        promotions = dict(self.promotions)
        for fingerprint, promotion in promotions.items():
            if fingerprint != promotion.readiness_receipt.validation_key.fingerprint:
                raise ValueError("promotion mapping key must match its validation key")
            snapshot = snapshots.get(promotion.readiness_receipt.validation_key.family_key)
            if snapshot is None:
                raise ValueError("promotion family is absent from readiness snapshots")
            exact = snapshot.evidence.exact(promotion.readiness_receipt.validation_key)
            if exact != promotion.readiness_receipt:
                raise ValueError("promotion receipt is absent from readiness snapshot")
        object.__setattr__(
            self,
            "snapshots",
            MappingProxyType(dict(sorted(snapshots.items()))),
        )
        object.__setattr__(
            self,
            "promotions",
            MappingProxyType(dict(sorted(promotions.items()))),
        )

    def require(
        self,
        family_key: str,
        validation_key: RuntimeValidationKey,
    ) -> str:
        """只允许同时具备 readiness 与 canonical promotion chain 的精确键。"""

        snapshot = self.snapshots.get(family_key)
        if snapshot is None:
            raise ReadinessPersistenceError("readiness family is unavailable")
        promotion = self.promotions.get(validation_key.fingerprint)
        if promotion is None:
            raise ReadinessPersistenceError(
                "caller-authored readiness lacks a canonical promotion receipt"
            )
        return require_promotable_activation(snapshot, validation_key, promotion)


def _object(value: object, context: str) -> dict[str, object]:
    """把 JSON 对象收窄为字符串键映射。"""

    if type(value) is not dict:
        raise ReadinessPersistenceError(f"{context} must be an object")
    raw = cast(dict[object, object], value)
    if any(type(key) is not str for key in raw):
        raise ReadinessPersistenceError(f"{context} keys must be strings")
    return cast(dict[str, object], raw)


def _sequence(value: object, context: str) -> list[object]:
    """把 JSON 数组收窄为对象列表。"""

    if type(value) is not list:
        raise ReadinessPersistenceError(f"{context} must be an array")
    return cast(list[object], value)


def _fields(payload: Mapping[str, object], expected: set[str], context: str) -> None:
    """要求动态边界字段集合完全一致。"""

    actual = set(payload)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown or missing:
        raise ReadinessPersistenceError(
            f"{context} fields mismatch: unknown={unknown}, missing={missing}"
        )


def _text(value: object, context: str) -> str:
    """读取规范非空文本。"""

    if type(value) is not str:
        raise ReadinessPersistenceError(f"{context} must be a string")
    result = value
    if not result or result != result.strip():
        raise ReadinessPersistenceError(f"{context} must be canonical non-empty text")
    return result


def _optional_text(value: object, context: str) -> str | None:
    """读取显式空值或规范文本。"""

    if value is None:
        return None
    return _text(value, context)


def _exact_bool(value: object, context: str) -> bool:
    """读取精确布尔值并拒绝 0/1。"""

    if type(value) is not bool:
        raise ReadinessPersistenceError(f"{context} must be an exact bool")
    return value


def _exact_int(value: object, context: str) -> int:
    """读取精确整数并拒绝布尔值。"""

    if type(value) is not int:
        raise ReadinessPersistenceError(f"{context} must be an exact int")
    return value


def _optional_exact_int(value: object, context: str) -> int | None:
    """读取显式空值或精确整数。"""

    if value is None:
        return None
    return _exact_int(value, context)


def _enum(value: object, enum_type: type[_EnumT], context: str) -> _EnumT:
    """严格读取闭集枚举值。"""

    text = _text(value, context)
    try:
        return enum_type(text)
    except ValueError as exc:
        raise ReadinessPersistenceError(f"{context} has an unknown value: {text!r}") from exc


def _parse_topology(value: object, context: str) -> RuntimeTopology | None:
    """读取显式空值或严格拓扑。"""

    if value is None:
        return None
    payload = _object(value, context)
    _fields(payload, {"gpu_type", "gpus_per_node", "node_count", "world_size"}, context)
    try:
        return RuntimeTopology(
            node_count=_exact_int(payload["node_count"], f"{context}.node_count"),
            world_size=_exact_int(payload["world_size"], f"{context}.world_size"),
            gpus_per_node=_exact_int(payload["gpus_per_node"], f"{context}.gpus_per_node"),
            gpu_type=_text(payload["gpu_type"], f"{context}.gpu_type"),
        )
    except (TypeError, ValueError) as exc:
        raise ReadinessPersistenceError(f"{context} is invalid: {exc}") from exc


_KEY_FIELDS = {
    "asset_fingerprint",
    "checkpoint_fingerprint",
    "checkpoint_mode",
    "command_fingerprint",
    "data_backend",
    "data_binding_fingerprint",
    "deepspeed_stage",
    "definition_fingerprint",
    "environment_fingerprint",
    "evidence_artifact_fingerprint",
    "family_key",
    "gradient_accumulation",
    "operation",
    "precision",
    "runtime_lock_fingerprint",
    "runtime_profile_fingerprint",
    "source_sha",
    "strategy",
    "topology",
}


def _parse_validation_key(value: object, context: str) -> RuntimeValidationKey:
    """读取严格 M12 验证键。"""

    payload = _object(value, context)
    _fields(payload, _KEY_FIELDS, context)
    strategy_text = _optional_text(payload["strategy"], f"{context}.strategy")
    precision_text = _optional_text(payload["precision"], f"{context}.precision")
    try:
        return RuntimeValidationKey(
            family_key=_text(payload["family_key"], f"{context}.family_key"),
            definition_fingerprint=_text(
                payload["definition_fingerprint"],
                f"{context}.definition_fingerprint",
            ),
            operation=_enum(payload["operation"], RuntimeOperation, f"{context}.operation"),
            runtime_profile_fingerprint=_optional_text(
                payload["runtime_profile_fingerprint"],
                f"{context}.runtime_profile_fingerprint",
            ),
            runtime_lock_fingerprint=_optional_text(
                payload["runtime_lock_fingerprint"],
                f"{context}.runtime_lock_fingerprint",
            ),
            environment_fingerprint=_optional_text(
                payload["environment_fingerprint"],
                f"{context}.environment_fingerprint",
            ),
            evidence_artifact_fingerprint=_optional_text(
                payload["evidence_artifact_fingerprint"],
                f"{context}.evidence_artifact_fingerprint",
            ),
            asset_fingerprint=_optional_text(
                payload["asset_fingerprint"], f"{context}.asset_fingerprint"
            ),
            checkpoint_fingerprint=_optional_text(
                payload["checkpoint_fingerprint"],
                f"{context}.checkpoint_fingerprint",
            ),
            data_binding_fingerprint=_optional_text(
                payload["data_binding_fingerprint"],
                f"{context}.data_binding_fingerprint",
            ),
            data_backend=_optional_text(
                payload["data_backend"],
                f"{context}.data_backend",
            ),
            gradient_accumulation=_optional_exact_int(
                payload["gradient_accumulation"],
                f"{context}.gradient_accumulation",
            ),
            source_sha=_optional_text(payload["source_sha"], f"{context}.source_sha"),
            command_fingerprint=_optional_text(
                payload["command_fingerprint"],
                f"{context}.command_fingerprint",
            ),
            strategy=(
                None
                if strategy_text is None
                else _enum(strategy_text, DistributedStrategyKind, f"{context}.strategy")
            ),
            deepspeed_stage=_enum(
                payload["deepspeed_stage"],
                DeepSpeedStage,
                f"{context}.deepspeed_stage",
            ),
            topology=_parse_topology(payload["topology"], f"{context}.topology"),
            precision=(
                None
                if precision_text is None
                else _enum(precision_text, PrecisionMode, f"{context}.precision")
            ),
            checkpoint_mode=_optional_text(
                payload["checkpoint_mode"], f"{context}.checkpoint_mode"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ReadinessPersistenceError(f"{context} is invalid: {exc}") from exc


_RECEIPT_FIELDS = {
    "artifact_fingerprint",
    "evidence_kind",
    "historical",
    "passed",
    "receipt_id",
    "validation_key",
}


def _parse_m12_receipt(value: object, context: str) -> RuntimeEvidenceReceipt:
    """读取严格 M12 收据。"""

    payload = _object(value, context)
    _fields(payload, _RECEIPT_FIELDS, context)
    try:
        return RuntimeEvidenceReceipt(
            receipt_id=_text(payload["receipt_id"], f"{context}.receipt_id"),
            validation_key=_parse_validation_key(
                payload["validation_key"], f"{context}.validation_key"
            ),
            evidence_kind=_enum(
                payload["evidence_kind"], RuntimeEvidenceKind, f"{context}.evidence_kind"
            ),
            artifact_fingerprint=_text(
                payload["artifact_fingerprint"],
                f"{context}.artifact_fingerprint",
            ),
            passed=_exact_bool(payload["passed"], f"{context}.passed"),
            historical=_exact_bool(payload["historical"], f"{context}.historical"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ReadinessPersistenceError):
            raise
        raise ReadinessPersistenceError(f"{context} is invalid: {exc}") from exc


def _expected_fingerprints(
    definitions: Mapping[str, ModelFamilyDefinition | str],
) -> dict[str, str]:
    """规范化当前模型族定义指纹。"""

    result: dict[str, str] = {}
    for family_key, definition in definitions.items():
        if type(family_key) is not str:
            raise TypeError("definition family keys must be strings")
        if isinstance(definition, ModelFamilyDefinition):
            if definition.family_key != family_key:
                raise ValueError("definition mapping key does not match family definition")
            fingerprint = definition.fingerprint
        elif type(definition) is str:
            fingerprint = definition
        else:
            raise TypeError("definition values must be ModelFamilyDefinition or SHA256 strings")
        try:
            RuntimeValidationKey(
                family_key=family_key,
                definition_fingerprint=fingerprint,
                operation=RuntimeOperation.CONSTRUCTION,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid definition identity for {family_key!r}: {exc}") from exc
        result[family_key] = fingerprint
    return result


def _parse_m12_snapshot(
    value: object,
    expected: Mapping[str, str],
    context: str,
) -> ModelFamilyReadinessSnapshot:
    """读取一个 M12 模型族快照并核对当前定义。"""

    payload = _object(value, context)
    _fields(payload, {"definition_fingerprint", "evidence", "family_key"}, context)
    family_key = _text(payload["family_key"], f"{context}.family_key")
    definition_fingerprint = _text(
        payload["definition_fingerprint"], f"{context}.definition_fingerprint"
    )
    if family_key not in expected:
        raise ReadinessPersistenceError(f"{context} references an unknown model family")
    if expected[family_key] != definition_fingerprint:
        raise ReadinessPersistenceError(f"{context} definition fingerprint is stale")
    evidence_payload = _object(payload["evidence"], f"{context}.evidence")
    _fields(evidence_payload, {"receipts"}, f"{context}.evidence")
    receipts = tuple(
        _parse_m12_receipt(item, f"{context}.evidence.receipts[{index}]")
        for index, item in enumerate(
            _sequence(evidence_payload["receipts"], f"{context}.evidence.receipts")
        )
    )
    try:
        return ModelFamilyReadinessSnapshot(
            family_key=family_key,
            definition_fingerprint=definition_fingerprint,
            evidence=RuntimeEvidenceSet(receipts),
        )
    except (TypeError, ValueError) as exc:
        raise ReadinessPersistenceError(f"{context} is invalid: {exc}") from exc


_M11_SNAPSHOT_FIELDS = {
    "assets",
    "checkpoint",
    "construction",
    "data_binding",
    "definition",
    "definition_fingerprint",
    "distributed",
    "family_key",
    "forward",
    "prediction",
    "receipts",
    "training",
    "validation",
}
_M11_RECEIPT_FIELDS = {
    "artifact_fingerprint",
    "axis",
    "definition_fingerprint",
    "evidence_id",
    "family_key",
    "state",
    "validation_kind",
}
_M11_OPERATION_BY_AXIS = {
    ReadinessAxis.DEFINITION: RuntimeOperation.CONSTRUCTION,
    ReadinessAxis.ASSETS: RuntimeOperation.CHECKPOINT_LOAD,
    ReadinessAxis.CHECKPOINT: RuntimeOperation.CHECKPOINT_LOAD,
    ReadinessAxis.CONSTRUCTION: RuntimeOperation.CONSTRUCTION,
    ReadinessAxis.FORWARD: RuntimeOperation.FORWARD,
    ReadinessAxis.TRAINING: RuntimeOperation.OPTIMIZER_STEP,
    ReadinessAxis.PREDICTION: RuntimeOperation.PREDICTION,
    ReadinessAxis.DATA_BINDING: RuntimeOperation.DATA_BINDING,
    ReadinessAxis.DISTRIBUTED: RuntimeOperation.PROFILING,
}


def _m11_receipt(
    value: object,
    family_key: str,
    definition_fingerprint: str,
    context: str,
) -> tuple[ReadinessEvidenceReceipt, RuntimeEvidenceReceipt]:
    """校验 M11 收据并转换为不可激活的历史 M12 收据。"""

    payload = _object(value, context)
    _fields(payload, _M11_RECEIPT_FIELDS, context)
    axis = _enum(payload["axis"], ReadinessAxis, f"{context}.axis")
    state_text = _text(payload["state"], f"{context}.state")
    try:
        state = readiness_state_type(axis)(state_text)
    except ValueError as exc:
        raise ReadinessPersistenceError(f"{context}.state has an unknown value") from exc
    try:
        old = ReadinessEvidenceReceipt(
            evidence_id=_text(payload["evidence_id"], f"{context}.evidence_id"),
            family_key=_text(payload["family_key"], f"{context}.family_key"),
            definition_fingerprint=_text(
                payload["definition_fingerprint"],
                f"{context}.definition_fingerprint",
            ),
            axis=axis,
            state=cast(ReadinessValue, state),
            validation_kind=_enum(
                payload["validation_kind"],
                EvidenceValidationKind,
                f"{context}.validation_kind",
            ),
            artifact_fingerprint=_text(
                payload["artifact_fingerprint"],
                f"{context}.artifact_fingerprint",
            ),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ReadinessPersistenceError):
            raise
        raise ReadinessPersistenceError(f"{context} is invalid: {exc}") from exc
    if old.family_key != family_key or old.definition_fingerprint != definition_fingerprint:
        raise ReadinessPersistenceError(f"{context} identity does not match its snapshot")
    migrated = RuntimeEvidenceReceipt(
        receipt_id=f"m11:{old.evidence_id}",
        validation_key=RuntimeValidationKey(
            family_key=family_key,
            definition_fingerprint=definition_fingerprint,
            operation=_M11_OPERATION_BY_AXIS[axis],
            command_fingerprint=old.artifact_fingerprint,
            evidence_artifact_fingerprint=old.artifact_fingerprint,
            checkpoint_mode=f"m11_{axis.value}",
        ),
        evidence_kind=RuntimeEvidenceKind(old.validation_kind.value),
        artifact_fingerprint=old.artifact_fingerprint,
        passed=True,
        historical=True,
    )
    return old, migrated


def _parse_m11_snapshot(
    value: object,
    expected: Mapping[str, str],
    context: str,
) -> ModelFamilyReadinessSnapshot:
    """严格验证 M11 投影,再仅在内存中迁移为历史收据。"""

    payload = _object(value, context)
    _fields(payload, _M11_SNAPSHOT_FIELDS, context)
    family_key = _text(payload["family_key"], f"{context}.family_key")
    definition_fingerprint = _text(
        payload["definition_fingerprint"], f"{context}.definition_fingerprint"
    )
    if family_key not in expected:
        raise ReadinessPersistenceError(f"{context} references an unknown model family")
    if expected[family_key] != definition_fingerprint:
        raise ReadinessPersistenceError(f"{context} definition fingerprint is stale")
    old_and_new = tuple(
        _m11_receipt(
            item,
            family_key,
            definition_fingerprint,
            f"{context}.receipts[{index}]",
        )
        for index, item in enumerate(_sequence(payload["receipts"], f"{context}.receipts"))
    )
    old_receipts = tuple(item[0] for item in old_and_new)
    migrated = tuple(item[1] for item in old_and_new)
    defaults = default_readiness_states()
    projected = dict(defaults)
    seen_axes: set[ReadinessAxis] = set()
    evidence_by_kind: dict[EvidenceValidationKind, list[str]] = {
        kind: [] for kind in EvidenceValidationKind
    }
    for receipt in old_receipts:
        if receipt.axis in seen_axes:
            raise ReadinessPersistenceError(f"{context} repeats a scalar M11 readiness axis")
        seen_axes.add(receipt.axis)
        projected[receipt.axis] = receipt.state
        evidence_by_kind[receipt.validation_kind].append(receipt.evidence_id)
    if projected[ReadinessAxis.DEFINITION].value != "executable_source_complete" and (
        projected[ReadinessAxis.CHECKPOINT] != defaults[ReadinessAxis.CHECKPOINT]
        or projected[ReadinessAxis.CONSTRUCTION] != defaults[ReadinessAxis.CONSTRUCTION]
    ):
        raise ReadinessPersistenceError(
            f"{context} checkpoint or construction evidence lacks executable source"
        )
    if projected[ReadinessAxis.CONSTRUCTION].value == "unavailable" and any(
        projected[axis] != defaults[axis]
        for axis in (
            ReadinessAxis.FORWARD,
            ReadinessAxis.TRAINING,
            ReadinessAxis.PREDICTION,
            ReadinessAxis.DISTRIBUTED,
        )
    ):
        raise ReadinessPersistenceError(f"{context} runtime evidence lacks a constructible model")
    if (
        projected[ReadinessAxis.TRAINING].value == "checkpoint_resume_validated"
        and projected[ReadinessAxis.CHECKPOINT].value != "resume_validated"
    ):
        raise ReadinessPersistenceError(
            f"{context} training resume evidence lacks checkpoint resume evidence"
        )
    if projected[ReadinessAxis.FORWARD].value == "real_data_validated" and projected[
        ReadinessAxis.DATA_BINDING
    ].value in {"none", "contract_fixture_only"}:
        raise ReadinessPersistenceError(
            f"{context} real-data forward lacks an explicit data binding"
        )
    for axis, state in projected.items():
        serialized = _text(payload[axis.value], f"{context}.{axis.value}")
        if serialized != state.value:
            raise ReadinessPersistenceError(
                f"{context}.{axis.value} is not derived from its M11 receipts"
            )
    validation = _object(payload["validation"], f"{context}.validation")
    _fields(validation, {"runtime", "source", "static"}, f"{context}.validation")
    for kind in EvidenceValidationKind:
        serialized_ids = tuple(
            _text(item, f"{context}.validation.{kind.value}[{index}]")
            for index, item in enumerate(
                _sequence(validation[kind.value], f"{context}.validation.{kind.value}")
            )
        )
        expected_ids = tuple(sorted(evidence_by_kind[kind]))
        if serialized_ids != expected_ids:
            raise ReadinessPersistenceError(
                f"{context}.validation.{kind.value} is not derived from receipts"
            )
    return ModelFamilyReadinessSnapshot.derive(
        family_key,
        definition_fingerprint,
        migrated,
    )


def _snapshots_by_family(
    snapshots: Sequence[ModelFamilyReadinessSnapshot],
) -> dict[str, ModelFamilyReadinessSnapshot]:
    """构造规范模型族映射并拒绝重复键。"""

    result: dict[str, ModelFamilyReadinessSnapshot] = {}
    for snapshot in snapshots:
        if type(snapshot) is not ModelFamilyReadinessSnapshot:
            raise TypeError("snapshots must contain ModelFamilyReadinessSnapshot")
        if snapshot.family_key in result:
            raise ReadinessPersistenceError("readiness document repeats a model family")
        result[snapshot.family_key] = snapshot
    return dict(sorted(result.items()))


def decode_readiness_document(
    value: object,
    definitions: Mapping[str, ModelFamilyDefinition | str],
) -> dict[str, ModelFamilyReadinessSnapshot]:
    """读取 M11 或 M12 文档;M11 仅在内存中迁移且永不提升运行能力。"""

    expected = _expected_fingerprints(definitions)
    root = _object(value, "readiness document")
    schema_value = root.get("schema_version")
    if schema_value is None and "family_key" in root:
        return _snapshots_by_family((_parse_m11_snapshot(root, expected, "readiness document"),))
    schema_version = _text(schema_value, "readiness document.schema_version")
    _fields(root, {"families", "schema_version"}, "readiness document")
    families = _sequence(root["families"], "readiness document.families")
    if schema_version == M12_SCHEMA_VERSION:
        snapshots = tuple(
            _parse_m12_snapshot(item, expected, f"readiness document.families[{index}]")
            for index, item in enumerate(families)
        )
    elif schema_version == M11_SCHEMA_VERSION:
        snapshots = tuple(
            _parse_m11_snapshot(item, expected, f"readiness document.families[{index}]")
            for index, item in enumerate(families)
        )
    else:
        raise ReadinessPersistenceError(f"unsupported readiness schema version: {schema_version!r}")
    return _snapshots_by_family(snapshots)


def encode_readiness_document(
    snapshots: Mapping[str, ModelFamilyReadinessSnapshot] | Sequence[ModelFamilyReadinessSnapshot],
) -> dict[str, object]:
    """只编码 M12 schema,投影不作为第二份事实来源写入。"""

    if isinstance(snapshots, Mapping):
        ordered = tuple(snapshots[key] for key in sorted(snapshots))
        for family_key, snapshot in snapshots.items():
            if family_key != snapshot.family_key:
                raise ValueError("snapshot mapping key does not match family_key")
    else:
        ordered = tuple(snapshots)
    canonical = _snapshots_by_family(ordered)
    return {
        "families": [snapshot.to_json_dict() for snapshot in canonical.values()],
        "schema_version": M12_SCHEMA_VERSION,
    }


def decode_promotable_readiness_document(
    value: object,
    definitions: Mapping[str, ModelFamilyDefinition | str],
) -> PromotableReadinessDocument:
    """严格解析 promotion schema 并重建 canonical execution/checkpoint/data/topology 链。"""

    root = _object(value, "promotable readiness document")
    _fields(
        root,
        {"families", "promotion_receipts", "schema_version"},
        "promotable readiness document",
    )
    if (
        _text(root["schema_version"], "promotable readiness document.schema_version")
        != M12_PROMOTABLE_SCHEMA_VERSION
    ):
        raise ReadinessPersistenceError("unsupported promotable readiness schema version")
    snapshots = decode_readiness_document(
        {
            "families": root["families"],
            "schema_version": M12_SCHEMA_VERSION,
        },
        definitions,
    )
    receipts_by_id: dict[str, RuntimeEvidenceReceipt] = {}
    for snapshot in snapshots.values():
        for receipt in snapshot.evidence.receipts:
            if receipt.receipt_id in receipts_by_id:
                raise ReadinessPersistenceError("promotable readiness repeats a receipt identity")
            receipts_by_id[receipt.receipt_id] = receipt
    promotions: dict[str, RuntimeActivationReceipt] = {}
    for index, raw_promotion in enumerate(
        _sequence(
            root["promotion_receipts"],
            "promotable readiness document.promotion_receipts",
        )
    ):
        context = f"promotable readiness document.promotion_receipts[{index}]"
        payload = _object(raw_promotion, context)
        _fields(
            payload,
            {
                "schema_version",
                "readiness_receipt_id",
                "readiness_receipt_fingerprint",
                "execution_receipt",
                "checkpoint_fingerprint",
                "data_binding_fingerprint",
                "topology_fingerprint",
            },
            context,
        )
        if _text(payload["schema_version"], f"{context}.schema_version") != (
            "autovla.runtime_activation_receipt.v1"
        ):
            raise ReadinessPersistenceError("unsupported runtime activation receipt schema")
        receipt_id = _text(
            payload["readiness_receipt_id"],
            f"{context}.readiness_receipt_id",
        )
        readiness_receipt = receipts_by_id.get(receipt_id)
        if readiness_receipt is None:
            raise ReadinessPersistenceError("promotion references an unknown readiness receipt")
        if (
            _text(
                payload["readiness_receipt_fingerprint"],
                f"{context}.readiness_receipt_fingerprint",
            )
            != readiness_receipt.fingerprint
        ):
            raise ReadinessPersistenceError("promotion readiness receipt fingerprint drifted")
        execution_payload = _object(
            payload["execution_receipt"],
            f"{context}.execution_receipt",
        )
        try:
            execution = RuntimeExecutionReceipt.from_dict(execution_payload)
            promotion = RuntimeActivationReceipt(
                readiness_receipt=readiness_receipt,
                execution_receipt=execution,
                checkpoint_fingerprint=_optional_text(
                    payload["checkpoint_fingerprint"],
                    f"{context}.checkpoint_fingerprint",
                ),
                data_binding_fingerprint=_optional_text(
                    payload["data_binding_fingerprint"],
                    f"{context}.data_binding_fingerprint",
                ),
                topology_fingerprint=_text(
                    payload["topology_fingerprint"],
                    f"{context}.topology_fingerprint",
                ),
            )
        except (RuntimeEnvironmentError, TypeError, ValueError) as exc:
            raise ReadinessPersistenceError(f"{context} is not promotable: {exc}") from exc
        key_fingerprint = readiness_receipt.validation_key.fingerprint
        if key_fingerprint in promotions:
            raise ReadinessPersistenceError("promotable readiness repeats a validation key")
        promotions[key_fingerprint] = promotion
    return PromotableReadinessDocument(snapshots, promotions)


def encode_promotable_readiness_document(
    snapshots: Mapping[str, ModelFamilyReadinessSnapshot] | Sequence[ModelFamilyReadinessSnapshot],
    promotions: Sequence[RuntimeActivationReceipt],
) -> dict[str, object]:
    """只从已构造且可重验的 promotion 对象编码 caller-safe readiness JSON。"""

    readiness = encode_readiness_document(snapshots)
    document = PromotableReadinessDocument(
        _snapshots_by_family(
            tuple(snapshots[key] for key in sorted(snapshots))
            if isinstance(snapshots, Mapping)
            else tuple(snapshots)
        ),
        {
            promotion.readiness_receipt.validation_key.fingerprint: promotion
            for promotion in promotions
        },
    )
    if len(document.promotions) != len(tuple(promotions)):
        raise ValueError("promotions must use unique validation keys")
    return {
        "families": readiness["families"],
        "promotion_receipts": [
            promotion.to_json_dict()
            for promotion in sorted(
                document.promotions.values(),
                key=lambda item: item.fingerprint,
            )
        ],
        "schema_version": M12_PROMOTABLE_SCHEMA_VERSION,
    }


def read_promotable_readiness_file(
    path: str | Path,
    definitions: Mapping[str, ModelFamilyDefinition | str],
) -> PromotableReadinessDocument:
    """读取 caller-authored JSON,但只返回可由 canonical chain 重验的 promotion。"""

    source = Path(path)
    if source.is_symlink():
        raise ReadinessPersistenceError("readiness path must not be a symlink")
    try:
        stat = source.stat()
    except OSError as exc:
        raise ReadinessPersistenceError(f"readiness file is unavailable: {exc}") from exc
    if not source.is_file():
        raise ReadinessPersistenceError("readiness path must be a regular file")
    if stat.st_size > _MAX_READINESS_BYTES:
        raise ReadinessPersistenceError("readiness file exceeds the bounded size limit")
    try:
        decoded = cast(object, json.loads(source.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReadinessPersistenceError(f"readiness file is corrupt: {exc}") from exc
    return decode_promotable_readiness_document(decoded, definitions)


def read_readiness_file(
    path: str | Path,
    definitions: Mapping[str, ModelFamilyDefinition | str],
) -> dict[str, ModelFamilyReadinessSnapshot]:
    """从普通文件严格读取 readiness 文档并关闭损坏或部分状态。"""

    source = Path(path)
    if source.is_symlink():
        raise ReadinessPersistenceError("readiness path must not be a symlink")
    try:
        stat = source.stat()
    except OSError as exc:
        raise ReadinessPersistenceError(f"readiness file is unavailable: {exc}") from exc
    if not source.is_file():
        raise ReadinessPersistenceError("readiness path must be a regular file")
    if stat.st_size > _MAX_READINESS_BYTES:
        raise ReadinessPersistenceError("readiness file exceeds the bounded size limit")
    try:
        decoded = cast(object, json.loads(source.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReadinessPersistenceError(f"readiness file is corrupt: {exc}") from exc
    return decode_readiness_document(decoded, definitions)


def write_readiness_file(
    path: str | Path,
    snapshots: Mapping[str, ModelFamilyReadinessSnapshot] | Sequence[ModelFamilyReadinessSnapshot],
) -> None:
    """在同目录写入并原子替换唯一 M12 readiness 文档。"""

    target = Path(path)
    parent = target.parent
    if target.is_symlink():
        raise ReadinessPersistenceError("readiness target must not be a symlink")
    if not parent.is_dir() or parent.is_symlink():
        raise ReadinessPersistenceError("readiness parent must be a real existing directory")
    payload = encode_readiness_document(snapshots)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        directory_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError as exc:
        raise ReadinessPersistenceError(f"atomic readiness write failed: {exc}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()


load_readiness_file = read_readiness_file
save_readiness_file = write_readiness_file


__all__ = [
    "M11_SCHEMA_VERSION",
    "M12_PROMOTABLE_SCHEMA_VERSION",
    "M12_SCHEMA_VERSION",
    "PromotableReadinessDocument",
    "ReadinessPersistenceError",
    "decode_promotable_readiness_document",
    "decode_readiness_document",
    "encode_promotable_readiness_document",
    "encode_readiness_document",
    "load_readiness_file",
    "read_promotable_readiness_file",
    "read_readiness_file",
    "save_readiness_file",
    "write_readiness_file",
]
