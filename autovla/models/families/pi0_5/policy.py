# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/blob/15a9616a00943ada6c20a0f158e3adb39df2ccac/src/openpi/policies/policy.py
# ruff: noqa: RUF002
"""Pi0.5 家族私有的无标签本地推理策略和会话。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

import numpy as np
import torch
from numpy.typing import NDArray

from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.normalization import Pi05SemanticNormalizationPlan
from autovla.models.families.pi0_5.source_map import PI05_SOURCE_MAP_FINGERPRINT
from autovla.models.outputs import ActionPrediction, ModelInputBatch
from autovla.models.readiness import (
    PrecisionMode,
    RuntimeEvidenceKind,
    RuntimeEvidenceReceipt,
    RuntimeOperation,
)

Float32Array = NDArray[np.float32]


class _InferenceProcessor(Protocol):
    """描述会话使用的 Pi0.5 无标签处理器面。"""

    config: Pi05Config
    normalization_plan: Pi05SemanticNormalizationPlan | None

    @property
    def fingerprint(self) -> str:
        """返回处理器身份。"""

        ...

    def prepare_observation(
        self,
        *,
        images: Mapping[str, object],
        image_masks: Mapping[str, object] | None,
        language: tuple[str, ...],
        state: object,
        embodiments: tuple[str, ...],
        sample_source: tuple[Mapping[str, object], ...],
        physical_action_horizon: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> ModelInputBatch:
        """准备不含动作标签的模型输入。"""

        ...


class _InferenceModel(Protocol):
    """描述会话需要的最小动作预测面。"""

    config: Pi05Config

    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """从无标签输入预测归一化动作。"""

        ...


@dataclass(frozen=True, slots=True)
class Pi05InferenceRequest:
    """保存不含训练动作或标签的 Pi0.5 推理请求。"""

    request_id: str
    images: Mapping[str, object]
    language: tuple[str, ...]
    state: object
    embodiment: tuple[str, ...]
    physical_action_horizon: int
    image_masks: Mapping[str, object] | None = None
    sample_source: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        """复制输入数组并校验 batch 级身份。"""

        if not self.request_id.strip():
            raise ValueError("Pi0.5 inference request_id must not be empty")
        state = np.asarray(self.state)
        if state.dtype != np.float32 or state.ndim != 2 or not np.isfinite(state).all():
            raise ValueError("Pi0.5 inference state must be finite float32[B,D]")
        batch_size = state.shape[0]
        if batch_size <= 0:
            raise ValueError("Pi0.5 inference batch must not be empty")
        if len(self.language) != batch_size or any(not item.strip() for item in self.language):
            raise ValueError("Pi0.5 inference language must match batch size")
        if len(self.embodiment) != batch_size or any(not item.strip() for item in self.embodiment):
            raise ValueError("Pi0.5 inference embodiment must match batch size")
        if type(self.physical_action_horizon) is not int or self.physical_action_horizon <= 0:
            raise ValueError("physical_action_horizon must be a positive exact int")
        if not self.images:
            raise ValueError("Pi0.5 inference images must not be empty")
        owned_images: dict[str, object] = {}
        for name, value in self.images.items():
            if not name.strip():
                raise ValueError("Pi0.5 inference camera names must not be empty")
            array = np.asarray(value)
            if array.ndim != 4 or array.shape[0] != batch_size:
                raise ValueError("Pi0.5 inference images must be batch-major rank-4 arrays")
            owned = np.array(array, copy=True)
            owned.setflags(write=False)
            owned_images[name] = owned
        if self.sample_source and len(self.sample_source) != batch_size:
            raise ValueError("Pi0.5 sample_source must match batch size")
        sources = self.sample_source or tuple({} for _ in range(batch_size))
        owned_state = np.array(state, dtype=np.float32, copy=True)
        owned_state.setflags(write=False)
        object.__setattr__(self, "state", owned_state)
        object.__setattr__(self, "images", MappingProxyType(owned_images))
        object.__setattr__(
            self,
            "sample_source",
            tuple(MappingProxyType(dict(item)) for item in sources),
        )
        if self.image_masks is not None:
            owned_masks: dict[str, object] = {}
            for name, value in self.image_masks.items():
                mask = np.asarray(value)
                if mask.dtype != np.bool_ or mask.shape != (batch_size,):
                    raise ValueError("Pi0.5 inference image masks must be strict bool[B]")
                owned = np.array(mask, dtype=np.bool_, copy=True)
                owned.setflags(write=False)
                owned_masks[name] = owned
            object.__setattr__(
                self,
                "image_masks",
                MappingProxyType(owned_masks),
            )


@dataclass(frozen=True, slots=True)
class Pi05InferenceEvidence:
    """记录一次无标签请求的完整处理顺序和身份。"""

    request_id: str
    session_fingerprint: str
    runtime_evidence_fingerprint: str
    processor_fingerprint: str
    normalization_receipt_fingerprint: str
    normalization_plan_fingerprint: str
    source_map_fingerprint: str
    steps: tuple[str, ...]
    schema_version: str = "autovla.pi0_5.inference_evidence.v1"

    def __post_init__(self) -> None:
        """要求身份非空且步骤顺序固定。"""

        values = (
            self.request_id,
            self.session_fingerprint,
            self.runtime_evidence_fingerprint,
            self.processor_fingerprint,
            self.normalization_receipt_fingerprint,
            self.normalization_plan_fingerprint,
            self.source_map_fingerprint,
        )
        if any(not value.strip() for value in values):
            raise ValueError("Pi0.5 inference evidence identities must not be empty")
        if self.steps != ("prepare", "predict", "decode", "inverse", "trim"):
            raise ValueError("Pi0.5 inference evidence steps must preserve official order")

    @property
    def fingerprint(self) -> str:
        """返回请求证据的稳定 SHA256。"""

        payload = {
            "normalization_plan_fingerprint": self.normalization_plan_fingerprint,
            "normalization_receipt_fingerprint": self.normalization_receipt_fingerprint,
            "processor_fingerprint": self.processor_fingerprint,
            "request_id": self.request_id,
            "runtime_evidence_fingerprint": self.runtime_evidence_fingerprint,
            "schema_version": self.schema_version,
            "session_fingerprint": self.session_fingerprint,
            "source_map_fingerprint": self.source_map_fingerprint,
            "steps": self.steps,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class Pi05InferenceResult:
    """保存裁剪后的物理动作和完整证据。"""

    actions: Float32Array
    evidence: Pi05InferenceEvidence

    def __post_init__(self) -> None:
        """冻结有限 ``[B,H,D]`` 物理动作。"""

        actions = np.asarray(self.actions)
        if (
            actions.dtype != np.float32
            or actions.ndim != 3
            or min(actions.shape) <= 0
            or not np.isfinite(actions).all()
        ):
            raise ValueError("Pi0.5 inference result must be finite float32[B,H,D]")
        owned = np.array(actions, dtype=np.float32, copy=True)
        owned.setflags(write=False)
        object.__setattr__(self, "actions", owned)


@dataclass(frozen=True, slots=True)
class Pi05PolicyBundle:
    """绑定装配对象、归一化计划和已通过的真实运行身份。"""

    processor: _InferenceProcessor
    model: _InferenceModel
    normalization_plan: Pi05SemanticNormalizationPlan
    verified_runtime_identity: RuntimeEvidenceReceipt

    def __post_init__(self) -> None:
        """拒绝配置、计划、家族或运行证据漂移。"""

        if self.processor.config != self.model.config:
            raise ValueError("Pi0.5 policy components must share one config")
        if self.processor.normalization_plan is not self.normalization_plan:
            raise ValueError("Pi0.5 policy processor must consume the exact normalization plan")
        receipt = self.verified_runtime_identity
        if type(receipt) is not RuntimeEvidenceReceipt:
            raise TypeError("verified_runtime_identity must be RuntimeEvidenceReceipt")
        key = receipt.validation_key
        if (
            receipt.evidence_kind is not RuntimeEvidenceKind.RUNTIME
            or receipt.historical
            or not receipt.passed
            or not key.is_complete_runtime_identity
        ):
            raise ValueError(
                "Pi0.5 policy requires passed non-historical complete runtime evidence"
            )
        if (
            key.family_key != "pi0_5"
            or key.definition_fingerprint != PI05_SPEC.fingerprint
            or key.operation is not RuntimeOperation.PREDICTION
        ):
            raise ValueError("Pi0.5 policy runtime identity does not match prediction family")
        if key.source_sha is None:
            raise ValueError("Pi0.5 policy runtime identity requires an exact source SHA")

    @property
    def fingerprint(self) -> str:
        """返回不包含参数或路径的策略包身份。"""

        payload = {
            "config_fingerprint": self.processor.config.fingerprint,
            "normalization_plan_fingerprint": self.normalization_plan.fingerprint,
            "processor_fingerprint": self.processor.fingerprint,
            "runtime_evidence_fingerprint": self.verified_runtime_identity.fingerprint,
            "schema_version": "autovla.pi0_5.policy_bundle.v1",
            "source_map_fingerprint": PI05_SOURCE_MAP_FINGERPRINT,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def new_session(
        self,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> Pi05PolicySession:
        """按已验证设备和精度创建一个家族私有会话。"""

        key = self.verified_runtime_identity.validation_key
        if device.type != "cuda":
            raise ValueError("verified Pi0.5 production policy requires a CUDA device")
        expected_dtype = {
            PrecisionMode.BF16: torch.bfloat16,
            PrecisionMode.FP32: torch.float32,
        }.get(key.precision)
        if expected_dtype is None or dtype is not expected_dtype:
            raise ValueError("session dtype drifted from verified Pi0.5 runtime precision")
        return Pi05PolicySession(
            processor=self.processor,
            model=self.model,
            normalization_plan=self.normalization_plan,
            runtime_evidence=self.verified_runtime_identity,
            device=device,
            dtype=dtype,
        )


class Pi05PolicySession:
    """执行显式 prepare/predict/decode/inverse/trim 生命周期。"""

    def __init__(
        self,
        *,
        processor: _InferenceProcessor,
        model: _InferenceModel,
        normalization_plan: Pi05SemanticNormalizationPlan,
        runtime_evidence: RuntimeEvidenceReceipt,
        device: torch.device,
        dtype: torch.dtype,
    ) -> None:
        """保存共享对象引用，不复制模型或参数。"""

        self._processor = processor
        self._model = model
        self._plan = normalization_plan
        self._runtime_evidence = runtime_evidence
        self._device = device
        self._dtype = dtype
        self._closed = False
        self._request_count = 0
        self._last_evidence: Pi05InferenceEvidence | None = None

    @property
    def fingerprint(self) -> str:
        """返回 family/assets/processor/device/precision 会话身份。"""

        payload = {
            "device": str(self._device),
            "dtype": str(self._dtype),
            "normalization_plan_fingerprint": self._plan.fingerprint,
            "processor_fingerprint": self._processor.fingerprint,
            "runtime_evidence_fingerprint": self._runtime_evidence.fingerprint,
            "schema_version": "autovla.pi0_5.policy_session.v1",
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def prepare(self, request: Pi05InferenceRequest) -> ModelInputBatch:
        """准备无标签 observation，不构造伪动作。"""

        self._require_open()
        return self._processor.prepare_observation(
            images=request.images,
            image_masks=request.image_masks,
            language=request.language,
            state=request.state,
            embodiments=request.embodiment,
            sample_source=request.sample_source,
            physical_action_horizon=request.physical_action_horizon,
            device=self._device,
            dtype=self._dtype,
        )

    def predict(
        self,
        prepared: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """预测归一化动作，不调用训练 forward。"""

        self._require_open()
        return self._model.predict_actions(prepared, generator=generator)

    def decode(self, prediction: ActionPrediction) -> Float32Array:
        """仅执行反 quantile，显式保留后续 inverse 阶段。"""

        self._require_open()
        host = prediction.normalized_actions.detach().to(device="cpu", dtype=torch.float32).numpy()
        return self._plan.denormalize_model_actions(host)

    def inverse(self, model_semantics: object) -> Float32Array:
        """执行与输入语义正向严格配对的动作逆变换。"""

        self._require_open()
        return self._plan.inverse_semantics(model_semantics)

    def trim(self, physical_actions: object, *, horizon: int) -> Float32Array:
        """按请求 horizon 和收据特征顺序裁剪物理动作。"""

        self._require_open()
        return self._plan.trim_actions(physical_actions, horizon=horizon)

    def run(
        self,
        request: Pi05InferenceRequest,
        *,
        generator: torch.Generator | None = None,
    ) -> Pi05InferenceResult:
        """按固定五阶段顺序执行一次无标签本地推理。"""

        prepared = self.prepare(request)
        prediction = self.predict(prepared, generator=generator)
        model_semantics = self.decode(prediction)
        physical = self.inverse(model_semantics)
        actions = self.trim(physical, horizon=request.physical_action_horizon)
        self._request_count += 1
        self._last_evidence = Pi05InferenceEvidence(
            request_id=request.request_id,
            session_fingerprint=self.fingerprint,
            runtime_evidence_fingerprint=self._runtime_evidence.fingerprint,
            processor_fingerprint=self._processor.fingerprint,
            normalization_receipt_fingerprint=self._plan.receipt.fingerprint,
            normalization_plan_fingerprint=self._plan.fingerprint,
            source_map_fingerprint=PI05_SOURCE_MAP_FINGERPRINT,
            steps=("prepare", "predict", "decode", "inverse", "trim"),
        )
        return Pi05InferenceResult(actions=actions, evidence=self._last_evidence)

    def evidence(self) -> Pi05InferenceEvidence:
        """返回最近一次完成请求的不可变证据。"""

        self._require_open()
        if self._last_evidence is None:
            raise RuntimeError("Pi0.5 policy session has no completed request evidence")
        return self._last_evidence

    def reset(self) -> None:
        """重置 episode 计数和最近证据，不重载模型。"""

        self._require_open()
        self._request_count = 0
        self._last_evidence = None

    def close(self) -> None:
        """关闭会话并清除请求状态；共享模型生命周期由 bundle 所有。"""

        self._request_count = 0
        self._last_evidence = None
        self._closed = True

    def _require_open(self) -> None:
        """拒绝关闭后的任何会话操作。"""

        if self._closed:
            raise RuntimeError("Pi0.5 policy session is closed")


__all__ = [
    "Pi05InferenceEvidence",
    "Pi05InferenceRequest",
    "Pi05InferenceResult",
    "Pi05PolicyBundle",
    "Pi05PolicySession",
]
