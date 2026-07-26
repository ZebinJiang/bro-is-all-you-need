"""基于精确运行验证键的模型族激活门。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from autovla.models.readiness import (
    ModelFamilyReadinessSnapshot,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeValidationKey,
)
from autovla.runtime_profiles.contracts import RuntimeExecutionReceipt


class ActivationBlocker(str, Enum):
    """列出稳定、可机器处理的首个激活阻断原因。"""

    FAMILY_MISMATCH = "FAMILY_MISMATCH"
    DEFINITION_FINGERPRINT_MISMATCH = "DEFINITION_FINGERPRINT_MISMATCH"
    INCOMPLETE_RUNTIME_VALIDATION_KEY = "INCOMPLETE_RUNTIME_VALIDATION_KEY"
    MISSING_EXACT_OPERATION_EVIDENCE = "MISSING_EXACT_OPERATION_EVIDENCE"
    HISTORICAL_EVIDENCE_NON_PROMOTING = "HISTORICAL_EVIDENCE_NON_PROMOTING"
    NON_RUNTIME_EVIDENCE_NON_PROMOTING = "NON_RUNTIME_EVIDENCE_NON_PROMOTING"
    EXACT_RUNTIME_IDENTITY_MISMATCH = "EXACT_RUNTIME_IDENTITY_MISMATCH"
    RUNTIME_EVIDENCE_FAILED = "RUNTIME_EVIDENCE_FAILED"


@dataclass(frozen=True, slots=True)
class ActivationDecision:
    """返回激活结果、首个稳定阻断项和匹配收据身份。"""

    authorized: bool
    blocker: ActivationBlocker | None
    requested_key_fingerprint: str
    receipt_id: str | None = None

    def __post_init__(self) -> None:
        """保持允许与阻断结果互斥。"""

        if type(self.authorized) is not bool:
            raise TypeError("authorized must be an exact bool")
        if self.authorized:
            if self.blocker is not None or self.receipt_id is None:
                raise ValueError("authorized activation requires only a receipt identity")
        elif self.blocker is None or self.receipt_id is not None:
            raise ValueError("blocked activation requires only a blocker")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定激活决策载荷。"""

        return {
            "authorized": self.authorized,
            "blocker": None if self.blocker is None else self.blocker.value,
            "receipt_id": self.receipt_id,
            "requested_key_fingerprint": self.requested_key_fingerprint,
        }


class ModelActivationError(RuntimeError):
    """表示调用方尝试越过证据门。"""

    def __init__(self, decision: ActivationDecision) -> None:
        """保存结构化阻断决策。"""

        if decision.authorized or decision.blocker is None:
            raise ValueError("ModelActivationError requires a blocked decision")
        self.decision = decision
        super().__init__(decision.blocker.value)


def runtime_topology_fingerprint(key: RuntimeValidationKey) -> str:
    """从验证键中的 canonical topology 生成执行收据使用的稳定摘要。"""

    if key.topology is None:
        raise ValueError("runtime activation requires a topology")
    payload = {
        "schema_version": "autovla.runtime_topology_identity.v1",
        "strategy": None if key.strategy is None else key.strategy.value,
        "deepspeed_stage": key.deepspeed_stage.value,
        "topology": key.topology.to_json_dict(),
        "precision": None if key.precision is None else key.precision.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeActivationReceipt:
    """绑定 readiness 收据、canonical 执行收据和 checkpoint/data/topology 链。"""

    readiness_receipt: RuntimeEvidenceReceipt
    execution_receipt: RuntimeExecutionReceipt
    checkpoint_fingerprint: str | None
    data_binding_fingerprint: str | None
    topology_fingerprint: str

    def __post_init__(self) -> None:
        """拒绝 caller 自报通过、陈旧收据或任一跨层身份漂移。"""

        if type(self.readiness_receipt) is not RuntimeEvidenceReceipt:
            raise TypeError("activation chain requires RuntimeEvidenceReceipt")
        if type(self.execution_receipt) is not RuntimeExecutionReceipt:
            raise TypeError("activation chain requires RuntimeExecutionReceipt")
        receipt = self.readiness_receipt
        key = receipt.validation_key
        execution = self.execution_receipt
        if (
            receipt.evidence_kind is not RuntimeEvidenceKind.RUNTIME
            or receipt.historical
            or not receipt.passed
            or not key.is_complete_runtime_identity
        ):
            raise ValueError(
                "activation chain requires passed non-historical complete runtime evidence"
            )
        if execution.status != "pass":
            raise ValueError("activation chain requires a passing execution receipt")
        exact_pairs = (
            ("profile", key.runtime_profile_fingerprint, execution.profile_fingerprint),
            ("lock", key.runtime_lock_fingerprint, execution.lock_fingerprint),
            ("environment", key.environment_fingerprint, execution.environment_fingerprint),
            ("asset", key.asset_fingerprint, execution.asset_fingerprint),
            ("source", key.source_sha, execution.source_sha),
            ("command", key.command_fingerprint, execution.command_fingerprint),
            (
                "evidence artifact",
                key.evidence_artifact_fingerprint,
                execution.evidence_sha256,
            ),
            ("checkpoint", key.checkpoint_fingerprint, self.checkpoint_fingerprint),
            ("data binding", key.data_binding_fingerprint, self.data_binding_fingerprint),
        )
        for name, expected, observed in exact_pairs:
            if expected != observed:
                raise ValueError(f"activation {name} identity drifted")
        if execution.operation != key.operation.value:
            raise ValueError("activation operation identity drifted")
        expected_topology = runtime_topology_fingerprint(key)
        if (
            self.topology_fingerprint != expected_topology
            or execution.topology_fingerprint != expected_topology
        ):
            raise ValueError("activation topology identity drifted")

    @property
    def fingerprint(self) -> str:
        """返回 promotion chain 的稳定身份。"""

        payload = self.to_json_dict()
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        """返回可由 readiness IO 严格重验的 canonical promotion 载荷。"""

        return {
            "schema_version": "autovla.runtime_activation_receipt.v1",
            "readiness_receipt_id": self.readiness_receipt.receipt_id,
            "readiness_receipt_fingerprint": self.readiness_receipt.fingerprint,
            "execution_receipt": self.execution_receipt.to_dict(),
            "checkpoint_fingerprint": self.checkpoint_fingerprint,
            "data_binding_fingerprint": self.data_binding_fingerprint,
            "topology_fingerprint": self.topology_fingerprint,
        }


def evaluate_activation(
    snapshot: ModelFamilyReadinessSnapshot,
    requested_key: RuntimeValidationKey,
) -> ActivationDecision:
    """仅允许与成功 M12 运行收据完全相等的请求。"""

    if type(snapshot) is not ModelFamilyReadinessSnapshot:
        raise TypeError("snapshot must use ModelFamilyReadinessSnapshot")
    if type(requested_key) is not RuntimeValidationKey:
        raise TypeError("requested_key must use RuntimeValidationKey")
    fingerprint = requested_key.fingerprint

    def blocked(reason: ActivationBlocker) -> ActivationDecision:
        """构造统一的关闭决策。"""

        return ActivationDecision(False, reason, fingerprint)

    if requested_key.family_key != snapshot.family_key:
        return blocked(ActivationBlocker.FAMILY_MISMATCH)
    if requested_key.definition_fingerprint != snapshot.definition_fingerprint:
        return blocked(ActivationBlocker.DEFINITION_FINGERPRINT_MISMATCH)
    if not requested_key.is_complete_runtime_identity:
        return blocked(ActivationBlocker.INCOMPLETE_RUNTIME_VALIDATION_KEY)
    exact = snapshot.evidence.exact(requested_key)
    if exact is not None:
        if exact.historical:
            return blocked(ActivationBlocker.HISTORICAL_EVIDENCE_NON_PROMOTING)
        if exact.evidence_kind is not RuntimeEvidenceKind.RUNTIME:
            return blocked(ActivationBlocker.NON_RUNTIME_EVIDENCE_NON_PROMOTING)
        if not exact.passed:
            return blocked(ActivationBlocker.RUNTIME_EVIDENCE_FAILED)
        return ActivationDecision(True, None, fingerprint, exact.receipt_id)
    same_operation = tuple(
        receipt
        for receipt in snapshot.evidence.receipts
        if receipt.validation_key.operation is requested_key.operation
    )
    if not same_operation:
        return blocked(ActivationBlocker.MISSING_EXACT_OPERATION_EVIDENCE)
    if all(receipt.historical for receipt in same_operation):
        return blocked(ActivationBlocker.HISTORICAL_EVIDENCE_NON_PROMOTING)
    if all(receipt.evidence_kind is not RuntimeEvidenceKind.RUNTIME for receipt in same_operation):
        return blocked(ActivationBlocker.NON_RUNTIME_EVIDENCE_NON_PROMOTING)
    return blocked(ActivationBlocker.EXACT_RUNTIME_IDENTITY_MISMATCH)


def require_activation(
    snapshot: ModelFamilyReadinessSnapshot,
    requested_key: RuntimeValidationKey,
    promotion: RuntimeActivationReceipt,
) -> str:
    """要求精确激活并强制重验 canonical 执行证据链。"""

    decision = evaluate_activation(snapshot, requested_key)
    if not decision.authorized:
        raise ModelActivationError(decision)
    assert decision.receipt_id is not None
    if type(promotion) is not RuntimeActivationReceipt:
        raise TypeError("promotion must use RuntimeActivationReceipt")
    if (
        promotion.readiness_receipt.receipt_id != decision.receipt_id
        or promotion.readiness_receipt.validation_key != requested_key
    ):
        raise ValueError("activation promotion does not match the exact readiness receipt")
    return decision.receipt_id


def require_promotable_activation(
    snapshot: ModelFamilyReadinessSnapshot,
    requested_key: RuntimeValidationKey,
    promotion: RuntimeActivationReceipt,
) -> str:
    """要求 caller-authored readiness 由 canonical 执行证据链重新授权。"""

    if type(promotion) is not RuntimeActivationReceipt:
        raise TypeError("promotable activation requires RuntimeActivationReceipt")
    return require_activation(snapshot, requested_key, promotion)


__all__ = [
    "ActivationBlocker",
    "ActivationDecision",
    "ModelActivationError",
    "RuntimeActivationReceipt",
    "evaluate_activation",
    "require_activation",
    "require_promotable_activation",
    "runtime_topology_fingerprint",
]
