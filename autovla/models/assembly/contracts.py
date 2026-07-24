"""模型族中立的装配请求、结果和运行时工厂契约。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generic, Protocol, TypeVar, cast, runtime_checkable

from autovla.data.transforms import TransformPlan
from autovla.models.capabilities import PrecisionSupport, TopologySupport

if TYPE_CHECKING:
    from autovla.assets.contracts import ModelAssetBundle
    from autovla.assets.lifecycle import AuthorizedModelAsset
    from autovla.config import ExperimentConfig
    from autovla.models.assembly.plan import ModelAssemblyPlan
    from autovla.models.assembly.runtime import ModelRuntimeBundle
    from autovla.runtime_profiles.contracts import (
        ResolvedRuntimeLock,
        RuntimeEnvironmentReceipt,
        RuntimeProfileSpec,
    )


_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_MISSING = object()
_ZERO_PARTITION_MARKERS = (
    "ds_id",
    "ds_status",
    "ds_tensor",
    "ds_numel",
    "partition_numel",
)


def _require_sha256(value: str, *, field_name: str) -> None:
    """校验稳定的小写 SHA256 身份。"""

    if len(value) != 64 or any(character not in _SHA256_CHARACTERS for character in value):
        raise ValueError(f"{field_name} must be a stable SHA256 fingerprint")


def _require_non_negative_integer(value: int, *, field_name: str) -> None:
    """拒绝 bool 混淆并校验非负计数。"""

    if type(value) is not int or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _validated_logical_shape(value: object, *, field_name: str) -> tuple[int, ...]:
    """校验不依赖 Torch 的完整逻辑 shape。"""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field_name} must be a sequence")
    shape: list[int] = []
    for dimension in cast(Sequence[object], value):
        if type(dimension) is not int or dimension < 0:
            raise ValueError(f"{field_name} must contain non-negative built-in integers")
        shape.append(dimension)
    return tuple(shape)


def logical_parameter_shape(parameter: object) -> tuple[int, ...]:
    """返回普通或 ZeRO 参数的完整逻辑 shape,缺失分区元数据时失败关闭。"""

    raw_ds_shape = getattr(parameter, "ds_shape", _MISSING)
    if raw_ds_shape is not _MISSING:
        if raw_ds_shape is None:
            raise RuntimeError("partitioned parameter lacks a reliable DeepSpeed ds_shape")
        return _validated_logical_shape(raw_ds_shape, field_name="parameter.ds_shape")
    if any(hasattr(parameter, marker) for marker in _ZERO_PARTITION_MARKERS):
        raise RuntimeError("partitioned parameter lacks a reliable DeepSpeed ds_shape")
    raw_shape = getattr(parameter, "shape", _MISSING)
    if raw_shape is _MISSING:
        raise TypeError("parameter must expose shape")
    return _validated_logical_shape(raw_shape, field_name="parameter.shape")


def logical_parameter_element_count(parameter: object) -> int:
    """返回 rank-invariant 参数元素数,普通参数保持 ``numel()`` 语义。"""

    if getattr(parameter, "ds_shape", _MISSING) is not _MISSING or any(
        hasattr(parameter, marker) for marker in _ZERO_PARTITION_MARKERS
    ):
        count = 1
        for dimension in logical_parameter_shape(parameter):
            count *= dimension
        return count
    numel = getattr(parameter, "numel", None)
    if not callable(numel):
        raise TypeError("parameter must expose callable numel")
    count = numel()
    if type(count) is not int or count < 0:
        raise ValueError("parameter.numel() must return a non-negative built-in integer")
    return count


def _validate_request_input_types(
    config: object,
    asset_bundle: object,
    transform_plan: object,
    precision: object,
    topology: object,
    initialization_context_factory: object,
) -> None:
    """对类型化构造器仍执行运行时关闭校验。"""

    if not isinstance(config, ModelConfigIdentity):
        raise TypeError("model config must satisfy ModelConfigIdentity")
    from autovla.assets.contracts import ModelAssetBundle

    if not isinstance(asset_bundle, ModelAssetBundle):
        raise TypeError("asset bundle must satisfy the verified ModelAssetBundle protocol")
    if not isinstance(transform_plan, TransformPlan):
        raise TypeError("transform_plan must be the canonical TransformPlan")
    if not isinstance(precision, PrecisionSupport):
        raise TypeError("precision must be PrecisionSupport")
    if not isinstance(topology, TopologySupport):
        raise TypeError("topology must be TopologySupport")
    if not isinstance(
        initialization_context_factory,
        AssemblyInitializationContextFactory,
    ):
        raise TypeError("initialization context factory must satisfy its shared protocol")


@runtime_checkable
class ModelConfigIdentity(Protocol):
    """限定通用装配所需的最小不可变配置身份。"""

    @property
    def family_key(self) -> str:
        """返回规范家族键。"""

        ...

    @property
    def fingerprint(self) -> str:
        """返回稳定 SHA256 配置身份。"""

        ...


@runtime_checkable
class AssemblyInitializationContextFactory(Protocol):
    """描述策略提供的模型初始化上下文,不依赖具体分布式框架。"""

    @property
    def identity(self) -> str:
        """返回进入计划指纹的稳定上下文身份。"""

        ...

    def __call__(self) -> AbstractContextManager[None]:
        """返回一次模型构造使用的上下文管理器。"""

        ...


OfficialCheckpointLoadT = TypeVar("OfficialCheckpointLoadT")
PartitionedCheckpointLoadT_co = TypeVar("PartitionedCheckpointLoadT_co", covariant=True)


@runtime_checkable
class PartitionedCheckpointLoadSink(Protocol[PartitionedCheckpointLoadT_co]):
    """由模型族拥有的分区 checkpoint 张量写入边界。

    模型族负责键映射、严格审计、形状、来源和实际张量复制。分布式策略只负责
    逐参数协调与复制 buffer 的同步,不得解释 checkpoint 命名空间。
    """

    def prepare(self) -> None:
        """仅由 rank 0 准备本地 checkpoint 映射和来源审计。"""

        ...

    def audit_tensor(
        self,
        name: str,
        logical_shape: tuple[int, ...],
        /,
    ) -> None:
        """在任何 mutation 前审计一个参数或复制 buffer 的逻辑 shape。"""

        ...

    def complete_audit(
        self,
        *,
        parameter_names: tuple[str, ...],
        buffer_names: tuple[str, ...],
    ) -> None:
        """确认 checkpoint 与模型参数和 buffer 名称严格一一覆盖。"""

        ...

    def load_tensor(self, name: str, tensor: object, /) -> None:
        """把一个已审计 checkpoint 张量复制到给定目标。"""

        ...

    def finish(self) -> Mapping[str, object]:
        """在 rank 0 确认全部写入并导出可 collective 传输的纯载荷。"""

        ...

    def restore_result(
        self,
        payload: Mapping[str, object],
        /,
    ) -> PartitionedCheckpointLoadT_co:
        """由每个 rank 严格恢复模型族拥有的加载证据。"""

        ...


@runtime_checkable
class OfficialCheckpointLoadBoundary(Protocol):
    """描述策略拥有的官方 checkpoint 加载决策边界。"""

    def load_official_checkpoint(
        self,
        model: object,
        loader: Callable[[], OfficialCheckpointLoadT],
        /,
        *,
        partitioned_loader: (
            Callable[[], PartitionedCheckpointLoadSink[OfficialCheckpointLoadT]] | None
        ) = None,
    ) -> OfficialCheckpointLoadT:
        """执行有界加载,或在模型状态不允许普通加载时提前失败。"""

        ...


@dataclass(frozen=True, slots=True)
class LocalInitializationContextFactory:
    """提供单卡和无分区运行使用的本地空上下文。"""

    @property
    def identity(self) -> str:
        """返回稳定的本地空上下文身份。"""

        return "autovla.assembly.initialization.local_noop.v1"

    def __call__(self) -> AbstractContextManager[None]:
        """返回不改变模型构造行为的空上下文。"""

        return nullcontext()

    def load_official_checkpoint(
        self,
        model: object,
        loader: Callable[[], OfficialCheckpointLoadT],
        /,
        *,
        partitioned_loader: (
            Callable[[], PartitionedCheckpointLoadSink[OfficialCheckpointLoadT]] | None
        ) = None,
    ) -> OfficialCheckpointLoadT:
        """在未分区本地模型上执行家族严格加载器。"""

        del model, partitioned_loader
        return loader()


LOCAL_INITIALIZATION_CONTEXT_FACTORY = LocalInitializationContextFactory()


@dataclass(frozen=True, slots=True)
class BaseModelAssetIdentity:
    """保存训练组合后仍需传播的已验证基础资产身份。"""

    key: str
    revision: str
    spec_identity_sha256: str

    def __post_init__(self) -> None:
        """拒绝空资产键、修订和非 SHA256 规范身份。"""

        if not self.key.strip() or not self.revision.strip():
            raise ValueError("base model asset key and revision must not be empty")
        _require_sha256(self.spec_identity_sha256, field_name="base model asset spec identity")


@dataclass(frozen=True, slots=True)
class ModelAssemblyRequest:
    """保存解析和执行装配所需的规范副作用前输入。

    输入仅绑定家族键、类型化配置、已验证资产、R3 变换计划和运行拓扑。
    构造请求不会解析家族注册表、导入家族实现或加载 checkpoint。
    """

    family_key: str
    config: ModelConfigIdentity
    asset_bundle: ModelAssetBundle
    transform_plan: TransformPlan
    precision: PrecisionSupport
    topology: TopologySupport
    local_files_only: bool = True
    initialization_context_factory: AssemblyInitializationContextFactory = (
        LOCAL_INITIALIZATION_CONTEXT_FACTORY
    )

    def __post_init__(self) -> None:
        """在注册表解析前关闭类型、身份和本地资产语义。"""

        if not self.family_key.strip() or self.family_key != self.family_key.strip():
            raise ValueError("family_key must be non-empty canonical text")
        _validate_request_input_types(
            self.config,
            self.asset_bundle,
            self.transform_plan,
            self.precision,
            self.topology,
            self.initialization_context_factory,
        )
        if type(self.local_files_only) is not bool or not self.local_files_only:
            raise ValueError("model assembly request must remain local_files_only")
        if not self.initialization_context_factory.identity.strip():
            raise ValueError("initialization context identity must not be empty")
        if self.config.family_key != self.family_key:
            raise ValueError("typed config family_key must match requested family_key")
        if self.asset_bundle.family_key != self.family_key:
            raise ValueError("verified asset bundle family_key must match requested family_key")
        self.asset_bundle.validate()
        for name, fingerprint in (
            ("config", self.config.fingerprint),
            ("asset bundle", self.asset_bundle.fingerprint),
            ("transform plan", self.transform_plan.fingerprint),
        ):
            _require_sha256(fingerprint, field_name=name)

    def load_official_checkpoint(
        self,
        model: object,
        loader: Callable[[], OfficialCheckpointLoadT],
        /,
        *,
        partitioned_loader: (
            Callable[[], PartitionedCheckpointLoadSink[OfficialCheckpointLoadT]] | None
        ) = None,
    ) -> OfficialCheckpointLoadT:
        """通过唯一策略边界加载官方权重,禁止 family 绕过分区所有权。"""

        boundary = self.initialization_context_factory
        if not isinstance(boundary, OfficialCheckpointLoadBoundary):
            raise RuntimeError(
                "model assembly initialization context lacks official checkpoint load boundary"
            )
        return boundary.load_official_checkpoint(
            model,
            loader,
            partitioned_loader=partitioned_loader,
        )


@dataclass(frozen=True, slots=True)
class PreparedTrainingAssembly:
    """返回家族拥有的训练装配请求及可选基础资产身份。"""

    request: ModelAssemblyRequest
    base_asset_identity: BaseModelAssetIdentity | None = None

    def __post_init__(self) -> None:
        """保证准备结果只携带规范装配请求。"""

        raw_request = cast(object, self.request)
        if not isinstance(raw_request, ModelAssemblyRequest):
            raise TypeError("prepared training assembly requires ModelAssemblyRequest")


@runtime_checkable
class TrainingAssemblyAdapter(Protocol):
    """由模型族把通用实验配置投影为规范训练装配请求。"""

    def prepare_training_assembly(
        self,
        config: ExperimentConfig,
        initialization_context_factory: AssemblyInitializationContextFactory,
        /,
    ) -> PreparedTrainingAssembly:
        """解析本地资产和家族配置,但不进入模型初始化上下文。"""

        ...


@dataclass(frozen=True, slots=True)
class AssemblyEvidenceIdentity:
    """绑定装配计划及其配置、资产和变换身份。"""

    plan_fingerprint: str
    config_fingerprint: str
    asset_bundle_fingerprint: str
    transform_plan_fingerprint: str
    initialization_context_identity: str

    def __post_init__(self) -> None:
        """校验全部身份均为稳定 SHA256。"""

        for name, fingerprint in (
            ("plan", self.plan_fingerprint),
            ("config", self.config_fingerprint),
            ("asset bundle", self.asset_bundle_fingerprint),
            ("transform plan", self.transform_plan_fingerprint),
        ):
            _require_sha256(fingerprint, field_name=name)
        if not self.initialization_context_identity.strip():
            raise ValueError("initialization_context_identity must not be empty")

    @classmethod
    def from_plan(cls, plan: ModelAssemblyPlan) -> AssemblyEvidenceIdentity:
        """从已验证计划提取副作用前身份快照。"""

        return cls(
            plan_fingerprint=plan.provenance_fingerprint,
            config_fingerprint=plan.config_fingerprint,
            asset_bundle_fingerprint=plan.asset_bundle_fingerprint,
            transform_plan_fingerprint=plan.transform_plan_fingerprint,
            initialization_context_identity=plan.initialization_context_identity,
        )


@dataclass(frozen=True, slots=True)
class CheckpointShapeMismatch:
    """记录一个 checkpoint 参数与模型参数的形状差异。"""

    key: str
    checkpoint_shape: tuple[int, ...]
    model_shape: tuple[int, ...]

    def __post_init__(self) -> None:
        """校验参数键和两侧非负形状。"""

        if not self.key.strip():
            raise ValueError("shape mismatch key must not be empty")
        for field_name, shape in (
            ("checkpoint_shape", self.checkpoint_shape),
            ("model_shape", self.model_shape),
        ):
            if any(type(dimension) is not int or dimension < 0 for dimension in shape):
                raise ValueError(f"{field_name} must contain non-negative integers")


@dataclass(frozen=True, slots=True)
class CheckpointLoadEvidence:
    """记录一次本地 checkpoint 加载的结构化结果。"""

    identity: AssemblyEvidenceIdentity
    adapter_identity: str
    checkpoint_fingerprint: str
    strictness: str
    loaded_parameter_count: int
    missing_keys: tuple[str, ...] = ()
    unexpected_keys: tuple[str, ...] = ()
    shape_mismatches: tuple[CheckpointShapeMismatch, ...] = ()
    known_optional_missing_keys: tuple[str, ...] = ()
    known_optional_unexpected_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验适配器、checkpoint 和参数键证据。"""

        if not self.adapter_identity.strip():
            raise ValueError("adapter_identity must not be empty")
        if not self.strictness.strip():
            raise ValueError("strictness must not be empty")
        _require_sha256(self.checkpoint_fingerprint, field_name="checkpoint")
        _require_non_negative_integer(
            self.loaded_parameter_count,
            field_name="loaded_parameter_count",
        )
        for field_name, keys in (
            ("missing_keys", self.missing_keys),
            ("unexpected_keys", self.unexpected_keys),
            ("known_optional_missing_keys", self.known_optional_missing_keys),
            ("known_optional_unexpected_keys", self.known_optional_unexpected_keys),
        ):
            if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
                raise ValueError(f"{field_name} must contain unique non-empty keys")
        mismatch_keys = tuple(item.key for item in self.shape_mismatches)
        if len(set(mismatch_keys)) != len(mismatch_keys):
            raise ValueError("shape_mismatches must contain unique parameter keys")
        if not set(self.known_optional_missing_keys).issubset(self.missing_keys):
            raise ValueError("known optional missing keys must classify missing_keys")
        if not set(self.known_optional_unexpected_keys).issubset(self.unexpected_keys):
            raise ValueError("known optional unexpected keys must classify unexpected_keys")


@dataclass(frozen=True, slots=True)
class TuningFreezeEvidence:
    """记录构造后可训练和冻结组件及参数计数。"""

    identity: AssemblyEvidenceIdentity
    strategy: str
    trainable_components: tuple[str, ...]
    frozen_components: tuple[str, ...]
    trainable_parameter_count: int
    frozen_parameter_count: int

    def __post_init__(self) -> None:
        """拒绝空组件名、重复归属和无效参数计数。"""

        if not self.strategy.strip():
            raise ValueError("strategy must not be empty")
        for field_name, names in (
            ("trainable_components", self.trainable_components),
            ("frozen_components", self.frozen_components),
        ):
            if any(not name.strip() for name in names) or len(set(names)) != len(names):
                raise ValueError(f"{field_name} must contain unique non-empty names")
        overlap = set(self.trainable_components) & set(self.frozen_components)
        if overlap:
            raise ValueError("a component cannot be both trainable and frozen")
        _require_non_negative_integer(
            self.trainable_parameter_count,
            field_name="trainable_parameter_count",
        )
        _require_non_negative_integer(
            self.frozen_parameter_count,
            field_name="frozen_parameter_count",
        )


@dataclass(frozen=True, slots=True)
class ModelRuntimeAssetEvidence:
    """保存进入运行包的资产清单和已验证 bundle 身份。"""

    asset_bundle_fingerprint: str
    manifest_fingerprint: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """要求资产身份为稳定 SHA256 且证据标识唯一有序。"""

        _require_sha256(self.asset_bundle_fingerprint, field_name="asset bundle")
        _require_sha256(self.manifest_fingerprint, field_name="asset manifest")
        if (
            self.evidence_ids != tuple(sorted(self.evidence_ids))
            or not self.evidence_ids
            or any(not item.strip() for item in self.evidence_ids)
            or len(set(self.evidence_ids)) != len(self.evidence_ids)
        ):
            raise ValueError("asset evidence ids must be unique, non-empty and sorted")


ProcessorT = TypeVar("ProcessorT")
BackboneT = TypeVar("BackboneT")
ActionHeadT = TypeVar("ActionHeadT")
ModelT = TypeVar("ModelT")
CheckpointAdapterT = TypeVar("CheckpointAdapterT")
PolicyBundleT = TypeVar("PolicyBundleT")
ProcessorFactoryT_co = TypeVar("ProcessorFactoryT_co", covariant=True)
BackboneFactoryT_co = TypeVar("BackboneFactoryT_co", covariant=True)
ActionHeadFactoryT_co = TypeVar("ActionHeadFactoryT_co", covariant=True)
CheckpointAdapterFactoryT_co = TypeVar("CheckpointAdapterFactoryT_co", covariant=True)
PolicyBundleFactoryT_co = TypeVar("PolicyBundleFactoryT_co", covariant=True)


@dataclass(frozen=True, slots=True)
class RuntimeAssemblyInput:
    """保存任何模型族进入 canonical assembly 前必须消费的运行与资产证据。

    该对象不读取 payload、不导入模型依赖,也不创建参数。它只绑定已验证画像、
    exact lock、canonical 环境收据和 lifecycle 授权资产,并在 family factory
    获得控制权前完成全部身份校验。
    """

    profile: RuntimeProfileSpec
    lock: ResolvedRuntimeLock
    environment: RuntimeEnvironmentReceipt
    authorized_assets: tuple[AuthorizedModelAsset, ...]

    def __post_init__(self) -> None:
        """拒绝非 canonical 类型、失败环境、重复授权和身份漂移。"""

        from autovla.assets.lifecycle import AuthorizedModelAsset
        from autovla.runtime_profiles.contracts import (
            ResolvedRuntimeLock,
            RuntimeEnvironmentReceipt,
            RuntimeProfileSpec,
        )

        if type(self.profile) is not RuntimeProfileSpec:
            raise TypeError("runtime assembly profile must use RuntimeProfileSpec")
        if type(self.lock) is not ResolvedRuntimeLock:
            raise TypeError("runtime assembly lock must use ResolvedRuntimeLock")
        if type(self.environment) is not RuntimeEnvironmentReceipt:
            raise TypeError("runtime assembly environment must use RuntimeEnvironmentReceipt")
        raw_assets = cast(object, self.authorized_assets)
        if type(raw_assets) is not tuple or not raw_assets:
            raise ValueError("runtime assembly requires lifecycle-authorized assets")
        assets = cast(tuple[object, ...], raw_assets)
        if any(type(asset) is not AuthorizedModelAsset for asset in assets):
            raise TypeError("runtime assembly assets must use AuthorizedModelAsset")
        typed_assets = cast(tuple[AuthorizedModelAsset, ...], raw_assets)
        keys = tuple(asset.resolved.manifest.key for asset in typed_assets)
        fingerprints = tuple(asset.fingerprint for asset in typed_assets)
        if (
            keys != tuple(sorted(keys))
            or len(keys) != len(set(keys))
            or len(fingerprints) != len(set(fingerprints))
        ):
            raise ValueError(
                "runtime assembly authorized assets must be unique and sorted by asset key"
            )
        self.lock.validate_profile(self.profile)
        self.environment.validate_profile(self.profile)
        self.environment.validate_lock(self.lock)
        if self.environment.verification_status != "pass":
            raise ValueError("runtime assembly requires a passing environment receipt")

    @property
    def runtime_profile_identity(self) -> str:
        """返回 M11 bundle 字段使用的 M12 exact profile-lock 身份。"""

        return f"{self.profile.profile_id}@lock-fingerprint:{self.lock.fingerprint}"

    @property
    def fingerprint(self) -> str:
        """返回不包含本地路径或模型 payload 的统一装配输入身份。"""

        payload = {
            "schema_version": "autovla.runtime_assembly_input.v1",
            "profile_fingerprint": self.profile.fingerprint,
            "lock_fingerprint": self.lock.fingerprint,
            "environment_fingerprint": self.environment.fingerprint,
            "authorized_asset_fingerprints": [
                asset.fingerprint for asset in self.authorized_assets
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def validate_request(self, request: ModelAssemblyRequest) -> ModelRuntimeAssetEvidence:
        """在任何 family side effect 前要求授权资产精确覆盖请求资产包。"""

        if type(request) is not ModelAssemblyRequest:
            raise TypeError("runtime assembly requires ModelAssemblyRequest")
        if request.family_key != self.profile.family_key:
            raise ValueError("runtime profile family differs from assembly request")
        raw_assets = cast(
            object,
            getattr(request.asset_bundle, "assets_by_role", None),
        )
        if not isinstance(raw_assets, Mapping) or not raw_assets:
            raise TypeError("runtime assembly asset bundle must expose assets_by_role")
        requested = tuple(cast(Mapping[object, object], raw_assets).values())
        authorized = self.authorized_assets
        if len(requested) != len(authorized):
            raise ValueError("authorized assets do not exactly cover the assembly request")
        from autovla.assets.contracts import ResolvedModelAsset

        matched: set[str] = set()
        for raw_resolved in requested:
            if not isinstance(raw_resolved, ResolvedModelAsset):
                raise ValueError("assembly request contains an unauthorized or stale model asset")
            matches = tuple(
                asset
                for asset in authorized
                if asset.resolved.manifest.key not in matched and asset.authorizes(raw_resolved)
            )
            if len(matches) != 1:
                raise ValueError("assembly request contains an unauthorized or stale model asset")
            matched.add(matches[0].resolved.manifest.key)
        if len(matched) != len(authorized):
            raise ValueError("runtime assembly contains unused authorized assets")
        manifest_payload = {
            role: manifest.to_dict()
            for role, manifest in sorted(request.asset_bundle.manifest.items())
        }
        manifest_encoded = json.dumps(
            manifest_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ModelRuntimeAssetEvidence(
            asset_bundle_fingerprint=request.asset_bundle.fingerprint,
            manifest_fingerprint=hashlib.sha256(manifest_encoded).hexdigest(),
            evidence_ids=tuple(sorted(asset.fingerprint for asset in authorized)),
        )


@dataclass(frozen=True, slots=True)
class RuntimeAssemblyBundle(
    Generic[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
):
    """在旧 ``ModelRuntimeBundle`` 外绑定完整 M12 运行和授权证据。

    ``model_runtime`` 仍引用唯一 canonical ``ModelAssemblyResult``,因此该封装
    不复制参数、张量或 checkpoint 证据,也不会形成第二套 assembly stack。
    """

    model_runtime: ModelRuntimeBundle[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
    runtime: RuntimeAssemblyInput

    def __post_init__(self) -> None:
        """要求外层 M12 证据与内层 canonical bundle 完全一致。"""

        from autovla.models.assembly.runtime import ModelRuntimeBundle

        if not isinstance(cast(object, self.model_runtime), ModelRuntimeBundle):
            raise TypeError("runtime assembly bundle requires ModelRuntimeBundle")
        if type(self.runtime) is not RuntimeAssemblyInput:
            raise TypeError("runtime assembly bundle requires RuntimeAssemblyInput")
        if self.model_runtime.family_definition.family_key != self.runtime.profile.family_key:
            raise ValueError("runtime assembly bundle family identity drifted")
        if self.model_runtime.runtime_profile_identity != self.runtime.runtime_profile_identity:
            raise ValueError("runtime assembly bundle profile identity drifted")

    @property
    def assembly_result(
        self,
    ) -> ModelAssemblyResult[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]:
        """返回唯一 canonical assembly result。"""

        return self.model_runtime.assembly_result


@runtime_checkable
class RuntimeModelFactory(Protocol):
    """描述统一 caller 所需的最小 family factory 面。"""

    def __call__(
        self,
        request: ModelAssemblyRequest,
        /,
    ) -> ModelAssemblyResult[object, object, object, object, object, object]:
        """消费已通过前置门的请求并返回 canonical assembly result。"""

        ...


def assemble_runtime_bundle(
    request: ModelAssemblyRequest,
    factory: RuntimeModelFactory,
    runtime: RuntimeAssemblyInput,
    /,
) -> RuntimeAssemblyBundle[object, object, object, object, object, object]:
    """以同一 caller 为所有 family 构造带完整 M12 证据的运行包。"""

    raw_factory = cast(object, factory)
    if not isinstance(raw_factory, RuntimeModelFactory):
        raise TypeError("runtime assembly factory must satisfy RuntimeModelFactory")
    asset_evidence = runtime.validate_request(request)
    result = raw_factory(request)
    if not isinstance(cast(object, result), ModelAssemblyResult):
        raise TypeError("runtime assembly factory must return ModelAssemblyResult")
    from autovla.models.assembly.runtime import ModelRuntimeBundle

    model_runtime = ModelRuntimeBundle(
        assembly_result=result,
        family_definition=result.plan.definition,
        runtime_profile_identity=runtime.runtime_profile_identity,
        asset_evidence=asset_evidence,
    )
    return RuntimeAssemblyBundle(model_runtime=model_runtime, runtime=runtime)


@dataclass(frozen=True, slots=True)
class ModelAssemblyResult(
    Generic[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
):
    """保存模型构造、加载和调优闭合后的类型化证据。

    结果中的组件不限定 Torch、JAX 或任一家族类型。两个证据记录必须绑定
    同一计划快照,从而在配置、资产或变换身份漂移时关闭结果发布。
    """

    plan: ModelAssemblyPlan
    processor: ProcessorT
    backbone: BackboneT
    action_head: ActionHeadT
    model: ModelT
    checkpoint_adapter: CheckpointAdapterT
    policy_bundle: PolicyBundleT | None
    checkpoint_load: CheckpointLoadEvidence
    tuning_freeze: TuningFreezeEvidence

    def __post_init__(self) -> None:
        """验证计划类型并拒绝任一结果证据的身份漂移。"""

        from autovla.models.assembly.plan import ModelAssemblyPlan

        if type(self.plan) is not ModelAssemblyPlan:
            raise TypeError("plan must be the canonical ModelAssemblyPlan")
        for name, component in (
            ("processor", self.processor),
            ("backbone", self.backbone),
            ("action_head", self.action_head),
            ("model", self.model),
            ("checkpoint_adapter", self.checkpoint_adapter),
        ):
            if component is None:
                raise ValueError(f"required assembly component {name} must not be None")
        self.plan.validate_identity_snapshot()
        expected = AssemblyEvidenceIdentity.from_plan(self.plan)
        if self.checkpoint_load.identity != expected:
            raise ValueError("checkpoint load evidence identity drifted from assembly plan")
        if self.tuning_freeze.identity != expected:
            raise ValueError("tuning/freeze evidence identity drifted from assembly plan")


@runtime_checkable
class ModelProcessorFactory(Protocol[ProcessorFactoryT_co]):
    """从同一规范请求构造家族处理器。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> ProcessorFactoryT_co:
        """返回绑定请求身份的处理器。"""

        ...


@runtime_checkable
class VisionLanguageBackboneFactory(Protocol[BackboneFactoryT_co]):
    """从同一规范请求构造视觉语言骨干。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> BackboneFactoryT_co:
        """返回绑定请求身份的骨干。"""

        ...


@runtime_checkable
class ActionHeadFactory(Protocol[ActionHeadFactoryT_co]):
    """从同一规范请求构造动作头。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> ActionHeadFactoryT_co:
        """返回绑定请求身份的动作头。"""

        ...


@runtime_checkable
class CheckpointAdapterFactory(Protocol[CheckpointAdapterFactoryT_co]):
    """从同一规范请求构造 checkpoint 适配器。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> CheckpointAdapterFactoryT_co:
        """返回绑定请求身份的 checkpoint 适配器。"""

        ...


@runtime_checkable
class PolicyBundleFactory(Protocol[PolicyBundleFactoryT_co]):
    """从同一规范请求构造可选策略包。"""

    def __call__(self, request: ModelAssemblyRequest, /) -> PolicyBundleFactoryT_co:
        """返回绑定请求身份的策略包。"""

        ...


@runtime_checkable
class ModelFactory(
    Protocol[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]
):
    """执行完整装配并返回绑定同一计划的类型化结果。"""

    def __call__(
        self,
        request: ModelAssemblyRequest,
        /,
    ) -> ModelAssemblyResult[
        ProcessorT,
        BackboneT,
        ActionHeadT,
        ModelT,
        CheckpointAdapterT,
        PolicyBundleT,
    ]:
        """构造组件、加载 checkpoint 并返回结构化证据。"""

        ...


__all__ = [
    "LOCAL_INITIALIZATION_CONTEXT_FACTORY",
    "ActionHeadFactory",
    "AssemblyEvidenceIdentity",
    "AssemblyInitializationContextFactory",
    "BaseModelAssetIdentity",
    "CheckpointAdapterFactory",
    "CheckpointLoadEvidence",
    "CheckpointShapeMismatch",
    "LocalInitializationContextFactory",
    "ModelAssemblyRequest",
    "ModelAssemblyResult",
    "ModelConfigIdentity",
    "ModelFactory",
    "ModelProcessorFactory",
    "ModelRuntimeAssetEvidence",
    "OfficialCheckpointLoadBoundary",
    "PartitionedCheckpointLoadSink",
    "PolicyBundleFactory",
    "PreparedTrainingAssembly",
    "TrainingAssemblyAdapter",
    "TuningFreezeEvidence",
    "VisionLanguageBackboneFactory",
    "logical_parameter_element_count",
    "logical_parameter_shape",
]
