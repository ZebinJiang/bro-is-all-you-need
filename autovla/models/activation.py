"""基于精确运行验证键的模型族激活门。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from autovla.models.readiness import (
    ModelFamilyReadinessSnapshot,
    RuntimeEvidenceKind,
    RuntimeValidationKey,
)


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
) -> str:
    """要求激活通过并返回精确匹配的收据身份。"""

    decision = evaluate_activation(snapshot, requested_key)
    if not decision.authorized:
        raise ModelActivationError(decision)
    assert decision.receipt_id is not None
    return decision.receipt_id


__all__ = [
    "ActivationBlocker",
    "ActivationDecision",
    "ModelActivationError",
    "evaluate_activation",
    "require_activation",
]
