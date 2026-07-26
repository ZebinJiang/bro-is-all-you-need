"""M12 数据集物理语义清单及其严格解析边界。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import cast

from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    DatasetModelBinding,
    DatasetSchema,
    EmbodimentSchema,
    NormalizationBinding,
    PhysicalFeatureSpec,
    canonical_data,
    sha256_fingerprint,
)

SEMANTIC_MANIFEST_SCHEMA = "autovla.semantic_manifest.v1"
SEMANTIC_MANIFEST_RECEIPT_SCHEMA = "autovla.semantic_manifest_receipt.v1"
BACKEND_DECISION = "NO_BACKEND_WINNER"
_BACKENDS = frozenset({"lerobot_local", "webdataset", "robodm_container"})
_UNKNOWN_SEMANTICS = frozenset({"", "unknown", "unspecified", "unresolved", "n/a", "none"})


def _text(value: object, name: str) -> str:
    """校验并返回非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _sha256(value: object, name: str) -> str:
    """校验完整的小写 SHA-256。"""
    result = _text(value, name)
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return result


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """校验排除 bool 的整数。"""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _finite_float(value: object, name: str, *, positive: bool = False) -> float:
    """校验排除 bool 的有限数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        raise ValueError(f"{name} must be a positive finite number")
    return result


def _strict_bool(value: object, name: str) -> bool:
    """校验精确 bool。"""
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


def _mapping(
    value: object,
    name: str,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> Mapping[str, object]:
    """收窄映射并拒绝缺失、未知或非字符串键。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    raw = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in raw):
        raise TypeError(f"{name} keys must be strings")
    result = cast(Mapping[str, object], raw)
    keys = set(result)
    missing = sorted(required - keys)
    unknown = sorted(keys - required - optional)
    if missing:
        raise ValueError(f"{name} is missing required fields: {missing}")
    if unknown:
        raise ValueError(f"{name} contains unknown fields: {unknown}")
    return result


def _sequence(value: object, name: str) -> Sequence[object]:
    """收窄列表或元组,拒绝文本等伪序列。"""
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    return cast(Sequence[object], value)


def _texts(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    """解析唯一、不可变文本序列。"""
    result = tuple(
        _text(item, f"{name}[{index}]") for index, item in enumerate(_sequence(value, name))
    )
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _ints(value: object, name: str, *, allow_negative: bool = False) -> tuple[int, ...]:
    """解析唯一整数序列,时间偏移可显式允许负数。"""
    result: list[int] = []
    for index, item in enumerate(_sequence(value, name)):
        if type(item) is not int:
            raise ValueError(f"{name}[{index}] must be an integer")
        if not allow_negative and item < 0:
            raise ValueError(f"{name}[{index}] must be non-negative")
        result.append(item)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(result)


def _pairs(value: object, name: str) -> tuple[tuple[str, str], ...]:
    """解析键唯一的二元文本序列。"""
    result: list[tuple[str, str]] = []
    for index, item in enumerate(_sequence(value, name)):
        pair = _sequence(item, f"{name}[{index}]")
        if len(pair) != 2:
            raise ValueError(f"{name}[{index}] must contain exactly two values")
        result.append(
            (
                _text(pair[0], f"{name}[{index}][0]"),
                _text(pair[1], f"{name}[{index}][1]"),
            )
        )
    keys = [key for key, _ in result]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} keys must not contain duplicates")
    return tuple(result)


def _known_semantics(value: object, name: str) -> str:
    """拒绝物理语义未知占位符。"""
    result = _text(value, name)
    if result.lower() in _UNKNOWN_SEMANTICS:
        raise ValueError(f"{name} must declare known physical semantics")
    return result


class ProjectionMode(str, Enum):
    """区分无投影直通与命名显式投影。"""

    IDENTITY = "identity"
    EXPLICIT_PROJECTION = "explicit_projection"


@dataclass(frozen=True, slots=True)
class ProjectorIdentity:
    """保存投影器名称、版本和实现指纹。"""

    mode: ProjectionMode
    projector_id: str
    version: str
    implementation_fingerprint: str

    def __post_init__(self) -> None:
        """拒绝未命名、未版本化或模式矛盾的投影器。"""
        if not isinstance(cast(object, self.mode), ProjectionMode):
            raise TypeError("mode must be ProjectionMode")
        object.__setattr__(self, "projector_id", _text(self.projector_id, "projector_id"))
        object.__setattr__(self, "version", _text(self.version, "version"))
        object.__setattr__(
            self,
            "implementation_fingerprint",
            _sha256(self.implementation_fingerprint, "implementation_fingerprint"),
        )
        if self.mode is ProjectionMode.IDENTITY and self.projector_id != "identity":
            raise ValueError("identity projection mode requires projector_id='identity'")
        if self.mode is ProjectionMode.EXPLICIT_PROJECTION and self.projector_id == "identity":
            raise ValueError("explicit_projection requires a named non-identity projector")

    @property
    def fingerprint(self) -> str:
        """返回完整投影身份的确定性指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class SemanticFeatureMapping:
    """把一个后端源字段映射到完整物理特征和对应掩码。"""

    source_field: str
    feature: PhysicalFeatureSpec
    mask_field: str

    def __post_init__(self) -> None:
        """校验源字段、物理特征和显式掩码。"""
        object.__setattr__(self, "source_field", _text(self.source_field, "source_field"))
        if not isinstance(cast(object, self.feature), PhysicalFeatureSpec):
            raise TypeError("feature must be PhysicalFeatureSpec")
        if self.feature.has_unknown_required_semantics:
            raise ValueError(
                f"feature {self.feature.semantic_key!r} has unknown required physical semantics"
            )
        object.__setattr__(self, "mask_field", _text(self.mask_field, "mask_field"))


@dataclass(frozen=True, slots=True)
class TemporalSemantics:
    """声明状态/动作时间偏移、锚点、边界和掩码策略。"""

    state_offsets: tuple[int, ...]
    action_offsets: tuple[int, ...]
    anchor: str
    boundary_policy: str
    mask_field: str
    forbid_episode_crossing: bool

    def __post_init__(self) -> None:
        """冻结完整时间语义并禁止跨 episode。"""
        object.__setattr__(
            self,
            "state_offsets",
            _ints(self.state_offsets, "state_offsets", allow_negative=True),
        )
        object.__setattr__(
            self,
            "action_offsets",
            _ints(self.action_offsets, "action_offsets", allow_negative=True),
        )
        for name in ("anchor", "boundary_policy", "mask_field"):
            object.__setattr__(
                self,
                name,
                _known_semantics(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "forbid_episode_crossing",
            _strict_bool(self.forbid_episode_crossing, "forbid_episode_crossing"),
        )
        if not self.forbid_episode_crossing:
            raise ValueError("semantic manifest must forbid episode crossing")


@dataclass(frozen=True, slots=True)
class SemanticManifest:
    """保存后端中立、不可变且物理语义完整的数据集清单。"""

    schema_version: str
    dataset_id: str
    dataset_version: str
    source_format: str
    immutable_dataset_fingerprint: str
    backend_key: str
    source_revision: str
    store_revision: str
    feature_mappings: tuple[SemanticFeatureMapping, ...]
    embodiment: EmbodimentSchema
    camera_names: tuple[str, ...]
    camera_mask_field: str
    language_semantics: str
    sample_rate_hz: float
    history: int
    horizon: int
    action_mode: str
    temporal: TemporalSemantics
    normalization: NormalizationBinding
    padding_policy: str
    mask_fields: tuple[str, ...]
    projector: ProjectorIdentity
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """校验清单身份、字段覆盖、时序、归一化和掩码闭包。"""
        if self.schema_version != SEMANTIC_MANIFEST_SCHEMA:
            raise ValueError(f"schema_version must equal {SEMANTIC_MANIFEST_SCHEMA!r}")
        for name in (
            "dataset_id",
            "dataset_version",
            "source_format",
            "source_revision",
            "store_revision",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "immutable_dataset_fingerprint",
            _sha256(self.immutable_dataset_fingerprint, "immutable_dataset_fingerprint"),
        )
        backend = _text(self.backend_key, "backend_key")
        if backend not in _BACKENDS:
            raise ValueError(f"unsupported physical backend: {backend!r}")
        object.__setattr__(self, "backend_key", backend)
        mappings = tuple(self.feature_mappings)
        if not mappings or any(
            not isinstance(cast(object, item), SemanticFeatureMapping) for item in mappings
        ):
            raise TypeError("feature_mappings must contain SemanticFeatureMapping values")
        for values, label in (
            ([item.source_field for item in mappings], "source fields"),
            ([item.feature.semantic_key for item in mappings], "semantic feature keys"),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")
        modalities = {item.feature.modality for item in mappings}
        if not {"state", "action"}.issubset(modalities):
            raise ValueError("feature mappings must declare state and action semantics")
        object.__setattr__(self, "feature_mappings", mappings)
        if not isinstance(cast(object, self.embodiment), EmbodimentSchema):
            raise TypeError("embodiment must be EmbodimentSchema")
        manifest_features = tuple(item.feature for item in mappings)
        if tuple(sha256_fingerprint(item) for item in manifest_features) != tuple(
            sha256_fingerprint(item) for item in self.embodiment.physical_features
        ):
            raise ValueError("embodiment physical features differ from manifest feature mappings")
        object.__setattr__(self, "camera_names", _texts(self.camera_names, "camera_names"))
        mounted_cameras = {name for name, _ in self.embodiment.camera_mounts}
        if set(self.camera_names) != mounted_cameras:
            raise ValueError("camera_names must exactly match embodiment camera mounts")
        object.__setattr__(
            self,
            "camera_mask_field",
            _text(self.camera_mask_field, "camera_mask_field"),
        )
        object.__setattr__(
            self,
            "language_semantics",
            _known_semantics(self.language_semantics, "language_semantics"),
        )
        object.__setattr__(
            self,
            "sample_rate_hz",
            _finite_float(self.sample_rate_hz, "sample_rate_hz", positive=True),
        )
        object.__setattr__(self, "history", _strict_int(self.history, "history", minimum=1))
        object.__setattr__(self, "horizon", _strict_int(self.horizon, "horizon", minimum=1))
        object.__setattr__(self, "action_mode", _known_semantics(self.action_mode, "action_mode"))
        if not isinstance(cast(object, self.temporal), TemporalSemantics):
            raise TypeError("temporal must be TemporalSemantics")
        if len(self.temporal.state_offsets) != self.history:
            raise ValueError("state_offsets length must equal history")
        if len(self.temporal.action_offsets) != self.horizon:
            raise ValueError("action_offsets length must equal horizon")
        if not isinstance(cast(object, self.normalization), NormalizationBinding):
            raise TypeError("normalization must be NormalizationBinding")
        feature_keys = {item.feature.semantic_key for item in mappings}
        if set(self.normalization.feature_names) != feature_keys:
            raise ValueError("normalization feature_names must cover every semantic feature")
        object.__setattr__(
            self,
            "padding_policy",
            _known_semantics(self.padding_policy, "padding_policy"),
        )
        masks = _texts(self.mask_fields, "mask_fields")
        required_masks = {
            self.camera_mask_field,
            self.temporal.mask_field,
            *(item.mask_field for item in mappings),
        }
        if not required_masks.issubset(masks):
            raise ValueError("mask_fields do not cover camera, feature, and temporal masks")
        object.__setattr__(self, "mask_fields", masks)
        if not isinstance(cast(object, self.projector), ProjectorIdentity):
            raise TypeError("projector must be ProjectorIdentity")
        if self.embodiment.projector_id != self.projector.projector_id:
            raise ValueError("embodiment projector identity differs from semantic manifest")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("semantic manifest must preserve NO_BACKEND_WINNER")

    @property
    def fingerprint(self) -> str:
        """返回包含所有语义和来源身份的确定性指纹。"""
        return sha256_fingerprint(self)

    @property
    def dataset_schema(self) -> DatasetSchema:
        """构造声明态 schema,绝不把清单声明升级为已观察行证据。"""
        return DatasetSchema(
            dataset_id=self.dataset_id,
            version=self.dataset_version,
            source_format=self.source_format,
            immutable_dataset_fingerprint=self.immutable_dataset_fingerprint,
            embodiment=self.embodiment,
            features=tuple(item.feature for item in self.feature_mappings),
            camera_names=self.camera_names,
            language_semantics=self.language_semantics,
            sample_rate_hz=self.sample_rate_hz,
            history=self.history,
            horizon=self.horizon,
            action_mode=self.action_mode,
            normalization_axes=self.normalization.axes,
            normalization_stats_fingerprint=self.normalization.statistics_fingerprint,
            padding_policy=self.padding_policy,
            mask_fields=self.mask_fields,
            row_validation_status="declared_only",
        )

    @property
    def receipt(self) -> "SemanticManifestReceipt":
        """生成只证明清单身份、不证明真实行读取的不可变收据。"""
        return SemanticManifestReceipt.from_manifest(self)

    def to_dict(self) -> dict[str, object]:
        """返回确定性 JSON 安全普通字典。"""
        value = canonical_data(self)
        if not isinstance(value, dict):
            raise AssertionError("canonical semantic manifest must be a dictionary")
        return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class SemanticManifestReceipt:
    """绑定清单、schema、具身、投影、统计和后端来源身份。"""

    receipt_schema: str
    semantic_manifest_fingerprint: str
    dataset_schema_fingerprint: str
    embodiment_schema_fingerprint: str
    dataset_id: str
    immutable_dataset_fingerprint: str
    backend_key: str
    source_revision: str
    store_revision: str
    projector_id: str
    projector_version: str
    projector_fingerprint: str
    projection_mode: ProjectionMode
    normalization_stats_fingerprint: str
    backend_decision: str = BACKEND_DECISION
    row_validation_status: str = "declared_only"

    def __post_init__(self) -> None:
        """校验收据只代表声明身份,不允许伪造已观察行状态。"""
        if self.receipt_schema != SEMANTIC_MANIFEST_RECEIPT_SCHEMA:
            raise ValueError(f"receipt_schema must equal {SEMANTIC_MANIFEST_RECEIPT_SCHEMA!r}")
        for name in (
            "semantic_manifest_fingerprint",
            "dataset_schema_fingerprint",
            "embodiment_schema_fingerprint",
            "immutable_dataset_fingerprint",
            "projector_fingerprint",
            "normalization_stats_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        for name in (
            "dataset_id",
            "source_revision",
            "store_revision",
            "projector_id",
            "projector_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.backend_key not in _BACKENDS:
            raise ValueError(f"unsupported physical backend: {self.backend_key!r}")
        if not isinstance(cast(object, self.projection_mode), ProjectionMode):
            raise TypeError("projection_mode must be ProjectionMode")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("semantic receipt must preserve NO_BACKEND_WINNER")
        if self.row_validation_status != "declared_only":
            raise ValueError("semantic manifest receipt cannot claim observed rows")

    @classmethod
    def from_manifest(cls, manifest: SemanticManifest) -> "SemanticManifestReceipt":
        """从已严格解析清单生成声明态身份收据。"""
        if not isinstance(cast(object, manifest), SemanticManifest):
            raise TypeError("manifest must be SemanticManifest")
        schema = manifest.dataset_schema
        return cls(
            receipt_schema=SEMANTIC_MANIFEST_RECEIPT_SCHEMA,
            semantic_manifest_fingerprint=manifest.fingerprint,
            dataset_schema_fingerprint=schema.fingerprint,
            embodiment_schema_fingerprint=manifest.embodiment.fingerprint,
            dataset_id=manifest.dataset_id,
            immutable_dataset_fingerprint=manifest.immutable_dataset_fingerprint,
            backend_key=manifest.backend_key,
            source_revision=manifest.source_revision,
            store_revision=manifest.store_revision,
            projector_id=manifest.projector.projector_id,
            projector_version=manifest.projector.version,
            projector_fingerprint=manifest.projector.fingerprint,
            projection_mode=manifest.projector.mode,
            normalization_stats_fingerprint=manifest.normalization.statistics_fingerprint,
        )

    @property
    def fingerprint(self) -> str:
        """返回声明态语义收据指纹。"""
        return sha256_fingerprint(self)

    def validate_binding(self, binding: DatasetModelBinding) -> None:
        """拒绝绑定与数据集、schema、投影或统计身份的任何漂移。"""
        if not isinstance(cast(object, binding), DatasetModelBinding):
            raise TypeError("binding must be DatasetModelBinding")
        expected = (
            ("dataset_id", binding.dataset_schema.dataset_id, self.dataset_id),
            (
                "immutable_dataset_fingerprint",
                binding.immutable_dataset_fingerprint,
                self.immutable_dataset_fingerprint,
            ),
            (
                "dataset_schema_fingerprint",
                binding.dataset_schema.fingerprint,
                self.dataset_schema_fingerprint,
            ),
            (
                "embodiment_schema_fingerprint",
                binding.dataset_schema.embodiment.fingerprint,
                self.embodiment_schema_fingerprint,
            ),
            ("projector_id", binding.projector_id, self.projector_id),
            (
                "normalization_stats_fingerprint",
                binding.normalization_binding.statistics_fingerprint,
                self.normalization_stats_fingerprint,
            ),
        )
        for name, observed, required in expected:
            if observed != required:
                raise ValueError(f"binding {name} differs from semantic manifest receipt")
        if binding.accepted_level is DatasetCompatibilityLevel.EXACT:
            if self.projection_mode is not ProjectionMode.IDENTITY:
                raise ValueError("exact binding requires identity semantic projector")
        elif binding.accepted_level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION:
            if self.projection_mode is not ProjectionMode.EXPLICIT_PROJECTION:
                raise ValueError("explicit_projection binding requires named semantic projector")
        else:
            raise ValueError("semantic manifest receipt requires exact or explicit_projection")


_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "dataset_id",
        "dataset_version",
        "source_format",
        "immutable_dataset_fingerprint",
        "backend_key",
        "source_revision",
        "store_revision",
        "features",
        "embodiment",
        "camera_names",
        "camera_mask_field",
        "language_semantics",
        "sample_rate_hz",
        "history",
        "horizon",
        "action_mode",
        "temporal",
        "normalization",
        "padding_policy",
        "mask_fields",
        "projector",
        "backend_decision",
    }
)


def _parse_feature(value: object, index: int) -> SemanticFeatureMapping:
    """解析一个完整源字段到物理特征的映射。"""
    name = f"features[{index}]"
    raw = _mapping(
        value,
        name,
        required=frozenset(
            {
                "source_field",
                "semantic_key",
                "dimension",
                "units",
                "coordinate_frame",
                "reference_frame",
                "ordering",
                "modality",
                "dtype",
                "representation",
                "source_indices",
                "required",
                "mask_field",
            }
        ),
        optional=frozenset({"valid_range"}),
    )
    valid_range: tuple[float, float] | None = None
    if "valid_range" in raw:
        range_values = _sequence(raw["valid_range"], f"{name}.valid_range")
        if len(range_values) != 2:
            raise ValueError(f"{name}.valid_range must contain exactly two values")
        valid_range = (
            _finite_float(range_values[0], f"{name}.valid_range[0]"),
            _finite_float(range_values[1], f"{name}.valid_range[1]"),
        )
    feature = PhysicalFeatureSpec(
        semantic_key=_known_semantics(raw["semantic_key"], f"{name}.semantic_key"),
        dimension=_strict_int(raw["dimension"], f"{name}.dimension", minimum=1),
        units=_known_semantics(raw["units"], f"{name}.units"),
        coordinate_frame=_known_semantics(
            raw["coordinate_frame"],
            f"{name}.coordinate_frame",
        ),
        reference_frame=_known_semantics(
            raw["reference_frame"],
            f"{name}.reference_frame",
        ),
        ordering=_texts(raw["ordering"], f"{name}.ordering"),
        modality=_known_semantics(raw["modality"], f"{name}.modality"),
        dtype=_known_semantics(raw["dtype"], f"{name}.dtype"),
        representation=_known_semantics(
            raw["representation"],
            f"{name}.representation",
        ),
        source_indices=_ints(raw["source_indices"], f"{name}.source_indices"),
        required=_strict_bool(raw["required"], f"{name}.required"),
        valid_range=valid_range,
    )
    return SemanticFeatureMapping(
        source_field=_text(raw["source_field"], f"{name}.source_field"),
        feature=feature,
        mask_field=_text(raw["mask_field"], f"{name}.mask_field"),
    )


def _parse_projector(value: object) -> ProjectorIdentity:
    """解析命名、版本化、带实现指纹的投影身份。"""
    raw = _mapping(
        value,
        "projector",
        required=frozenset({"mode", "projector_id", "version", "implementation_fingerprint"}),
    )
    try:
        mode = ProjectionMode(_text(raw["mode"], "projector.mode"))
    except ValueError as error:
        raise ValueError(f"projector.mode has unknown value: {raw['mode']!r}") from error
    return ProjectorIdentity(
        mode=mode,
        projector_id=_text(raw["projector_id"], "projector.projector_id"),
        version=_text(raw["version"], "projector.version"),
        implementation_fingerprint=_sha256(
            raw["implementation_fingerprint"],
            "projector.implementation_fingerprint",
        ),
    )


def _parse_temporal(value: object) -> TemporalSemantics:
    """解析不得猜测的时间窗口与边界语义。"""
    raw = _mapping(
        value,
        "temporal",
        required=frozenset(
            {
                "state_offsets",
                "action_offsets",
                "anchor",
                "boundary_policy",
                "mask_field",
                "forbid_episode_crossing",
            }
        ),
    )
    return TemporalSemantics(
        state_offsets=_ints(raw["state_offsets"], "temporal.state_offsets", allow_negative=True),
        action_offsets=_ints(
            raw["action_offsets"],
            "temporal.action_offsets",
            allow_negative=True,
        ),
        anchor=_known_semantics(raw["anchor"], "temporal.anchor"),
        boundary_policy=_known_semantics(
            raw["boundary_policy"],
            "temporal.boundary_policy",
        ),
        mask_field=_text(raw["mask_field"], "temporal.mask_field"),
        forbid_episode_crossing=_strict_bool(
            raw["forbid_episode_crossing"],
            "temporal.forbid_episode_crossing",
        ),
    )


def _parse_normalization(value: object) -> NormalizationBinding:
    """解析统计、轴、所有权、范围和 padding 恒等性。"""
    raw = _mapping(
        value,
        "normalization",
        required=frozenset(
            {
                "method",
                "statistics_fingerprint",
                "axes",
                "feature_names",
                "owner",
                "scope",
                "constant_policy",
                "padding_identity",
            }
        ),
    )
    return NormalizationBinding(
        method=_known_semantics(raw["method"], "normalization.method"),
        statistics_fingerprint=_sha256(
            raw["statistics_fingerprint"],
            "normalization.statistics_fingerprint",
        ),
        axes=_ints(raw["axes"], "normalization.axes"),
        feature_names=_texts(raw["feature_names"], "normalization.feature_names"),
        owner=_known_semantics(raw["owner"], "normalization.owner"),
        scope=_known_semantics(raw["scope"], "normalization.scope"),
        constant_policy=_known_semantics(
            raw["constant_policy"],
            "normalization.constant_policy",
        ),
        padding_identity=_strict_bool(
            raw["padding_identity"],
            "normalization.padding_identity",
        ),
    )


def parse_semantic_manifest(value: Mapping[str, object]) -> SemanticManifest:
    """严格解析一份内存语义清单,不执行文件、数据或后端读取。"""
    raw = _mapping(value, "semantic_manifest", required=_TOP_LEVEL_FIELDS)
    feature_values = _sequence(raw["features"], "features")
    mappings = tuple(_parse_feature(item, index) for index, item in enumerate(feature_values))
    if not mappings:
        raise ValueError("features must not be empty")
    projector = _parse_projector(raw["projector"])
    embodiment_raw = _mapping(
        raw["embodiment"],
        "embodiment",
        required=frozenset(
            {
                "embodiment_id",
                "version",
                "joint_order",
                "eef_order",
                "camera_mounts",
                "coordinate_conventions",
                "projector_id",
            }
        ),
    )
    embodiment = EmbodimentSchema(
        embodiment_id=_known_semantics(
            embodiment_raw["embodiment_id"],
            "embodiment.embodiment_id",
        ),
        version=_text(embodiment_raw["version"], "embodiment.version"),
        physical_features=tuple(item.feature for item in mappings),
        joint_order=_texts(
            embodiment_raw["joint_order"],
            "embodiment.joint_order",
            allow_empty=True,
        ),
        eef_order=_texts(
            embodiment_raw["eef_order"],
            "embodiment.eef_order",
            allow_empty=True,
        ),
        camera_mounts=_pairs(
            embodiment_raw["camera_mounts"],
            "embodiment.camera_mounts",
        ),
        coordinate_conventions=_texts(
            embodiment_raw["coordinate_conventions"],
            "embodiment.coordinate_conventions",
        ),
        projector_id=_text(
            embodiment_raw["projector_id"],
            "embodiment.projector_id",
        ),
    )
    return SemanticManifest(
        schema_version=_text(raw["schema_version"], "schema_version"),
        dataset_id=_text(raw["dataset_id"], "dataset_id"),
        dataset_version=_text(raw["dataset_version"], "dataset_version"),
        source_format=_text(raw["source_format"], "source_format"),
        immutable_dataset_fingerprint=_sha256(
            raw["immutable_dataset_fingerprint"],
            "immutable_dataset_fingerprint",
        ),
        backend_key=_text(raw["backend_key"], "backend_key"),
        source_revision=_text(raw["source_revision"], "source_revision"),
        store_revision=_text(raw["store_revision"], "store_revision"),
        feature_mappings=mappings,
        embodiment=embodiment,
        camera_names=_texts(raw["camera_names"], "camera_names"),
        camera_mask_field=_text(raw["camera_mask_field"], "camera_mask_field"),
        language_semantics=_known_semantics(
            raw["language_semantics"],
            "language_semantics",
        ),
        sample_rate_hz=_finite_float(
            raw["sample_rate_hz"],
            "sample_rate_hz",
            positive=True,
        ),
        history=_strict_int(raw["history"], "history", minimum=1),
        horizon=_strict_int(raw["horizon"], "horizon", minimum=1),
        action_mode=_known_semantics(raw["action_mode"], "action_mode"),
        temporal=_parse_temporal(raw["temporal"]),
        normalization=_parse_normalization(raw["normalization"]),
        padding_policy=_known_semantics(raw["padding_policy"], "padding_policy"),
        mask_fields=_texts(raw["mask_fields"], "mask_fields"),
        projector=projector,
        backend_decision=_text(raw["backend_decision"], "backend_decision"),
    )


__all__ = [
    "BACKEND_DECISION",
    "SEMANTIC_MANIFEST_RECEIPT_SCHEMA",
    "SEMANTIC_MANIFEST_SCHEMA",
    "ProjectionMode",
    "ProjectorIdentity",
    "SemanticFeatureMapping",
    "SemanticManifest",
    "SemanticManifestReceipt",
    "TemporalSemantics",
    "parse_semantic_manifest",
]
