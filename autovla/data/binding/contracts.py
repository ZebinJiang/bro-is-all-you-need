"""数据集与模型输入之间的不可变物理语义契约。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import cast


_UNKNOWN_SEMANTICS = frozenset({"", "unknown", "unspecified", "unresolved", "n/a", "none"})


def _text(value: object, name: str) -> str:
    """校验并返回非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """校验排除 bool 的整数。"""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _finite_float(value: object, name: str, *, positive: bool = False) -> float:
    """校验排除 bool 的有限浮点值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{name} must be a {qualifier}finite number")
    return result


def _strict_bool(value: object, name: str) -> bool:
    """校验值是精确 bool，而不是可强制转换的标量。"""
    if type(value) is not bool:
        raise TypeError(f"{name} must be bool")
    return value


def _texts(
    value: object,
    name: str,
    *,
    allow_empty: bool = False,
    unique: bool = True,
) -> tuple[str, ...]:
    """校验不可变文本序列并拒绝重复项。"""
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    result = tuple(_text(item, f"{name}[{index}]") for index, item in enumerate(value))
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if unique and len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _indices(value: object, name: str, *, allow_empty: bool = True) -> tuple[int, ...]:
    """校验非负且不重复的索引序列。"""
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    result = tuple(_strict_int(item, f"{name}[{index}]") for index, item in enumerate(value))
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return result


def _offsets(value: object, name: str) -> tuple[int, ...]:
    """校验允许负历史位置但排除 bool 的不重复时间偏移。"""
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    result: list[int] = []
    for index, item in enumerate(value):
        if type(item) is not int:
            raise ValueError(f"{name}[{index}] must be an integer")
        result.append(item)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if len(set(result)) != len(result):
        raise ValueError(f"{name} must not contain duplicates")
    return tuple(result)


def _pairs(value: object, name: str, *, allow_empty: bool = True) -> tuple[tuple[str, str], ...]:
    """校验键唯一的二元文本序列。"""
    if not isinstance(value, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    result: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"{name}[{index}] must contain exactly two text values")
        result.append(
            (
                _text(item[0], f"{name}[{index}][0]"),
                _text(item[1], f"{name}[{index}][1]"),
            )
        )
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    keys = [item[0] for item in result]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} keys must not contain duplicates")
    return tuple(result)


def _sha256(value: object, name: str) -> str:
    """校验小写 SHA-256 十六进制摘要。"""
    text = _text(value, name)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def canonical_data(value: object) -> object:
    """把契约值转换为确定性、JSON 可编码的数据。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: canonical_data(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {str(key): canonical_data(mapping[key]) for key in sorted(mapping, key=str)}
    if isinstance(value, (tuple, list)):
        return [canonical_data(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("canonical data must not contain non-finite floats")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_serialize(value: object) -> str:
    """返回排序键、无空白且 ASCII 稳定的规范 JSON。"""
    return json.dumps(
        canonical_data(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_fingerprint(value: object) -> str:
    """返回规范序列化内容的 SHA-256 指纹。"""
    return hashlib.sha256(canonical_serialize(value).encode("utf-8")).hexdigest()


def semantics_unknown(value: str) -> bool:
    """判断必需物理语义是否使用了明确的未知占位符。"""
    return value.strip().lower() in _UNKNOWN_SEMANTICS


class DatasetCompatibilityLevel(str, Enum):
    """数据集—模型绑定的唯一四级兼容性枚举。"""

    EXACT = "exact"
    EXPLICIT_PROJECTION = "explicit_projection"
    CONTRACT_FIXTURE_ONLY = "contract_fixture_only"
    INCOMPATIBLE = "incompatible"


def _level(value: object, name: str) -> DatasetCompatibilityLevel:
    """接受已知枚举或精确字符串，并拒绝未知兼容性值。"""
    if isinstance(value, DatasetCompatibilityLevel):
        return value
    if isinstance(value, str):
        try:
            return DatasetCompatibilityLevel(value)
        except ValueError as error:
            raise ValueError(f"{name} has unknown compatibility value: {value!r}") from error
    raise TypeError(f"{name} must be DatasetCompatibilityLevel or exact string value")


@dataclass(frozen=True, slots=True)
class PhysicalFeatureSpec:
    """描述一个状态或动作物理特征的维度、单位、坐标系和顺序。"""

    semantic_key: str
    dimension: int
    units: str
    coordinate_frame: str
    reference_frame: str
    ordering: tuple[str, ...]
    modality: str = "state"
    dtype: str = "float32"
    representation: str = "scalar"
    source_indices: tuple[int, ...] = ()
    required: bool = True
    valid_range: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        """严格校验维度、索引、有限范围和必需标记。"""
        object.__setattr__(self, "semantic_key", _text(self.semantic_key, "semantic_key"))
        object.__setattr__(self, "dimension", _strict_int(self.dimension, "dimension", minimum=1))
        for name in (
            "units",
            "coordinate_frame",
            "reference_frame",
            "modality",
            "dtype",
            "representation",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        ordering = _texts(self.ordering, "ordering")
        if len(ordering) != self.dimension:
            raise ValueError("ordering length must equal dimension")
        object.__setattr__(self, "ordering", ordering)
        indices = _indices(self.source_indices, "source_indices")
        if indices and len(indices) != self.dimension:
            raise ValueError("source_indices length must equal dimension when provided")
        object.__setattr__(self, "source_indices", indices)
        object.__setattr__(self, "required", _strict_bool(self.required, "required"))
        if self.valid_range is not None:
            if not isinstance(self.valid_range, (tuple, list)) or len(self.valid_range) != 2:
                raise ValueError("valid_range must contain exactly two finite values")
            lower = _finite_float(self.valid_range[0], "valid_range[0]")
            upper = _finite_float(self.valid_range[1], "valid_range[1]")
            if lower >= upper:
                raise ValueError("valid_range lower bound must be smaller than upper bound")
            object.__setattr__(self, "valid_range", (lower, upper))

    @property
    def has_unknown_required_semantics(self) -> bool:
        """返回必需特征是否缺少单位、坐标系、参考系、表示或分量语义。"""
        if not self.required:
            return False
        values = (
            self.units,
            self.coordinate_frame,
            self.reference_frame,
            self.representation,
            *self.ordering,
        )
        return any(semantics_unknown(value) for value in values)


@dataclass(frozen=True, slots=True)
class EmbodimentSchema:
    """描述具身身份、关节/末端顺序、相机安装和物理特征。"""

    embodiment_id: str
    version: str
    physical_features: tuple[PhysicalFeatureSpec, ...]
    joint_order: tuple[str, ...]
    eef_order: tuple[str, ...]
    camera_mounts: tuple[tuple[str, str], ...]
    coordinate_conventions: tuple[str, ...]
    projector_id: str = "identity"

    def __post_init__(self) -> None:
        """冻结并拒绝重复特征、关节、EEF 和相机名称。"""
        for name in ("embodiment_id", "version", "projector_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        features = tuple(self.physical_features)
        if not features or any(not isinstance(item, PhysicalFeatureSpec) for item in features):
            raise TypeError("physical_features must contain PhysicalFeatureSpec values")
        keys = [item.semantic_key for item in features]
        if len(set(keys)) != len(keys):
            raise ValueError("physical feature semantic keys must not contain duplicates")
        object.__setattr__(self, "physical_features", features)
        object.__setattr__(
            self,
            "joint_order",
            _texts(self.joint_order, "joint_order", allow_empty=True),
        )
        object.__setattr__(self, "eef_order", _texts(self.eef_order, "eef_order", allow_empty=True))
        object.__setattr__(self, "camera_mounts", _pairs(self.camera_mounts, "camera_mounts"))
        object.__setattr__(
            self,
            "coordinate_conventions",
            _texts(self.coordinate_conventions, "coordinate_conventions", allow_empty=True),
        )

    @property
    def fingerprint(self) -> str:
        """返回具身契约的确定性指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class DatasetSchema:
    """保存不可变数据集身份与相机、语言、时序、动作及归一化语义。"""

    dataset_id: str
    version: str
    source_format: str
    immutable_dataset_fingerprint: str
    embodiment: EmbodimentSchema
    features: tuple[PhysicalFeatureSpec, ...]
    camera_names: tuple[str, ...]
    language_semantics: str
    sample_rate_hz: float
    history: int
    horizon: int
    action_mode: str
    normalization_axes: tuple[int, ...]
    normalization_stats_fingerprint: str
    padding_policy: str
    mask_fields: tuple[str, ...]
    row_validation_status: str = "contract_only"

    def __post_init__(self) -> None:
        """校验数据集身份、唯一布局、采样率及掩码声明。"""
        for name in (
            "dataset_id",
            "version",
            "source_format",
            "language_semantics",
            "action_mode",
            "padding_policy",
            "row_validation_status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "immutable_dataset_fingerprint",
            _sha256(self.immutable_dataset_fingerprint, "immutable_dataset_fingerprint"),
        )
        if not isinstance(self.embodiment, EmbodimentSchema):
            raise TypeError("embodiment must be EmbodimentSchema")
        features = tuple(self.features)
        if not features or any(not isinstance(item, PhysicalFeatureSpec) for item in features):
            raise TypeError("features must contain PhysicalFeatureSpec values")
        keys = [item.semantic_key for item in features]
        if len(set(keys)) != len(keys):
            raise ValueError("dataset feature semantic keys must not contain duplicates")
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "camera_names", _texts(self.camera_names, "camera_names"))
        object.__setattr__(
            self,
            "sample_rate_hz",
            _finite_float(self.sample_rate_hz, "sample_rate_hz", positive=True),
        )
        object.__setattr__(self, "history", _strict_int(self.history, "history", minimum=1))
        object.__setattr__(self, "horizon", _strict_int(self.horizon, "horizon", minimum=1))
        object.__setattr__(
            self,
            "normalization_axes",
            _indices(self.normalization_axes, "normalization_axes"),
        )
        object.__setattr__(
            self,
            "normalization_stats_fingerprint",
            _sha256(self.normalization_stats_fingerprint, "normalization_stats_fingerprint"),
        )
        object.__setattr__(self, "mask_fields", _texts(self.mask_fields, "mask_fields"))

    @property
    def fingerprint(self) -> str:
        """返回数据集 schema 指纹，不替代不可变数据内容指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class ModelInputSchema:
    """描述模型族所需的相机、物理特征、时序、动作和填充形状。"""

    family_id: str
    version: str
    source_pin: str
    embodiment_id: str
    projector_id: str
    camera_names: tuple[str, ...]
    language_semantics: str
    state_features: tuple[PhysicalFeatureSpec, ...]
    action_features: tuple[PhysicalFeatureSpec, ...]
    state_dimension: int
    action_dimension: int
    sample_rate_hz: float
    history: int
    horizon: int
    action_mode: str
    normalization_axes: tuple[int, ...]
    normalization_stats_fingerprint: str
    padding_policy: str
    mask_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        """校验模型输入物理宽度、相机顺序、时序与指纹。"""
        for name in (
            "family_id",
            "version",
            "source_pin",
            "embodiment_id",
            "projector_id",
            "language_semantics",
            "action_mode",
            "padding_policy",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "camera_names", _texts(self.camera_names, "camera_names"))
        for field_name in ("state_features", "action_features"):
            specs = tuple(getattr(self, field_name))
            if not specs or any(not isinstance(item, PhysicalFeatureSpec) for item in specs):
                raise TypeError(f"{field_name} must contain PhysicalFeatureSpec values")
            keys = [item.semantic_key for item in specs]
            if len(set(keys)) != len(keys):
                raise ValueError(f"{field_name} semantic keys must not contain duplicates")
            object.__setattr__(self, field_name, specs)
        state_width = sum(item.dimension for item in self.state_features)
        action_width = sum(item.dimension for item in self.action_features)
        object.__setattr__(
            self, "state_dimension", _strict_int(self.state_dimension, "state_dimension", minimum=1)
        )
        object.__setattr__(
            self,
            "action_dimension",
            _strict_int(self.action_dimension, "action_dimension", minimum=1),
        )
        if state_width > self.state_dimension or action_width > self.action_dimension:
            raise ValueError("physical feature widths must fit padded model dimensions")
        object.__setattr__(
            self,
            "sample_rate_hz",
            _finite_float(self.sample_rate_hz, "sample_rate_hz", positive=True),
        )
        object.__setattr__(self, "history", _strict_int(self.history, "history", minimum=1))
        object.__setattr__(self, "horizon", _strict_int(self.horizon, "horizon", minimum=1))
        object.__setattr__(
            self,
            "normalization_axes",
            _indices(self.normalization_axes, "normalization_axes"),
        )
        object.__setattr__(
            self,
            "normalization_stats_fingerprint",
            _sha256(self.normalization_stats_fingerprint, "normalization_stats_fingerprint"),
        )
        object.__setattr__(self, "mask_fields", _texts(self.mask_fields, "mask_fields"))

    @property
    def fingerprint(self) -> str:
        """返回模型输入 schema 的确定性指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class CameraBinding:
    """把数据集相机按显式顺序和安装身份绑定到模型槽位。"""

    dataset_camera: str
    model_camera: str
    dataset_index: int
    model_index: int
    mount: str
    projection: str = "identity"
    mask_key: str = "camera_mask"
    required: bool = True

    def __post_init__(self) -> None:
        """校验相机名称、顺序、安装、投影和严格 bool 标记。"""
        for name in ("dataset_camera", "model_camera", "mount", "projection", "mask_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "dataset_index", _strict_int(self.dataset_index, "dataset_index"))
        object.__setattr__(self, "model_index", _strict_int(self.model_index, "model_index"))
        object.__setattr__(self, "required", _strict_bool(self.required, "required"))


@dataclass(frozen=True, slots=True)
class LanguageBinding:
    """声明语言来源、语义、格式化所有者和截断边界。"""

    dataset_key: str
    model_key: str
    semantics: str
    formatter_id: str
    tokenizer_owner: str
    truncation_limit: int
    required: bool = True

    def __post_init__(self) -> None:
        """校验语言字段并拒绝模糊布尔/整数。"""
        for name in ("dataset_key", "model_key", "semantics", "formatter_id", "tokenizer_owner"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "truncation_limit",
            _strict_int(self.truncation_limit, "truncation_limit", minimum=1),
        )
        object.__setattr__(self, "required", _strict_bool(self.required, "required"))


@dataclass(frozen=True, slots=True)
class StateBinding:
    """声明状态特征、索引、投影、丢弃/填充字段和严格掩码。"""

    source_features: tuple[str, ...]
    target_features: tuple[str, ...]
    source_indices: tuple[int, ...]
    target_indices: tuple[int, ...]
    projector_id: str
    projected_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    padding_value: float = 0.0
    mask_key: str = "state_mask"

    def __post_init__(self) -> None:
        """校验状态映射的唯一字段、索引、有限填充值和 projector。"""
        object.__setattr__(self, "source_features", _texts(self.source_features, "source_features"))
        object.__setattr__(self, "target_features", _texts(self.target_features, "target_features"))
        object.__setattr__(
            self,
            "source_indices",
            _indices(self.source_indices, "source_indices", allow_empty=False),
        )
        object.__setattr__(
            self,
            "target_indices",
            _indices(self.target_indices, "target_indices", allow_empty=False),
        )
        for name in ("projector_id", "mask_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("projected_fields", "dropped_fields", "filled_fields"):
            object.__setattr__(self, name, _texts(getattr(self, name), name, allow_empty=True))
        object.__setattr__(
            self,
            "padding_value",
            _finite_float(self.padding_value, "padding_value"),
        )


@dataclass(frozen=True, slots=True)
class ActionBinding:
    """声明动作特征、模式、索引、投影、逆映射和损失掩码。"""

    source_features: tuple[str, ...]
    target_features: tuple[str, ...]
    source_indices: tuple[int, ...]
    target_indices: tuple[int, ...]
    action_mode: str
    projector_id: str
    inverse_mapping: str
    projected_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    padding_value: float = 0.0
    mask_key: str = "action_mask"

    def __post_init__(self) -> None:
        """校验动作映射、有限填充、模式及逆映射声明。"""
        object.__setattr__(self, "source_features", _texts(self.source_features, "source_features"))
        object.__setattr__(self, "target_features", _texts(self.target_features, "target_features"))
        object.__setattr__(
            self,
            "source_indices",
            _indices(self.source_indices, "source_indices", allow_empty=False),
        )
        object.__setattr__(
            self,
            "target_indices",
            _indices(self.target_indices, "target_indices", allow_empty=False),
        )
        for name in ("action_mode", "projector_id", "inverse_mapping", "mask_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in ("projected_fields", "dropped_fields", "filled_fields"):
            object.__setattr__(self, name, _texts(getattr(self, name), name, allow_empty=True))
        object.__setattr__(
            self,
            "padding_value",
            _finite_float(self.padding_value, "padding_value"),
        )


@dataclass(frozen=True, slots=True)
class TemporalBinding:
    """声明采样率、历史/预测窗口、时间锚点、边界和观测掩码。"""

    source_sample_rate_hz: float
    model_sample_rate_hz: float
    history: int
    horizon: int
    source_offsets: tuple[int, ...]
    model_offsets: tuple[int, ...]
    anchor: str
    boundary_policy: str
    mask_key: str
    forbid_episode_crossing: bool = True

    def __post_init__(self) -> None:
        """校验有限采样率、窗口、偏移和 episode 边界策略。"""
        object.__setattr__(
            self,
            "source_sample_rate_hz",
            _finite_float(self.source_sample_rate_hz, "source_sample_rate_hz", positive=True),
        )
        object.__setattr__(
            self,
            "model_sample_rate_hz",
            _finite_float(self.model_sample_rate_hz, "model_sample_rate_hz", positive=True),
        )
        object.__setattr__(self, "history", _strict_int(self.history, "history", minimum=1))
        object.__setattr__(self, "horizon", _strict_int(self.horizon, "horizon", minimum=1))
        object.__setattr__(self, "source_offsets", _offsets(self.source_offsets, "source_offsets"))
        object.__setattr__(self, "model_offsets", _offsets(self.model_offsets, "model_offsets"))
        for name in ("anchor", "boundary_policy", "mask_key"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "forbid_episode_crossing",
            _strict_bool(self.forbid_episode_crossing, "forbid_episode_crossing"),
        )


@dataclass(frozen=True, slots=True)
class NormalizationBinding:
    """声明归一化方法、统计摘要、轴、适用字段、所有者和 padding 恒等性。"""

    method: str
    statistics_fingerprint: str
    axes: tuple[int, ...]
    feature_names: tuple[str, ...]
    owner: str
    scope: str
    constant_policy: str
    padding_identity: bool

    def __post_init__(self) -> None:
        """校验统计指纹、唯一轴/字段和严格 padding 标记。"""
        for name in ("method", "owner", "scope", "constant_policy"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "statistics_fingerprint",
            _sha256(self.statistics_fingerprint, "statistics_fingerprint"),
        )
        object.__setattr__(self, "axes", _indices(self.axes, "axes"))
        object.__setattr__(self, "feature_names", _texts(self.feature_names, "feature_names"))
        object.__setattr__(
            self, "padding_identity", _strict_bool(self.padding_identity, "padding_identity")
        )


@dataclass(frozen=True, slots=True)
class DatasetModelBinding:
    """聚合数据集、模型和各模态显式绑定，不执行数据读取或模型处理。"""

    binding_id: str
    schema_version: str
    dataset_schema: DatasetSchema
    model_schema: ModelInputSchema
    embodiment_id: str
    projector_id: str
    camera_bindings: tuple[CameraBinding, ...]
    language_binding: LanguageBinding
    state_binding: StateBinding
    action_binding: ActionBinding
    temporal_binding: TemporalBinding
    normalization_binding: NormalizationBinding
    accepted_level: DatasetCompatibilityLevel
    dropped_fields: tuple[str, ...] = ()
    filled_fields: tuple[str, ...] = ()
    projected_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验完整绑定类型、相机槽位唯一性和聚合字段去重。"""
        for name in ("binding_id", "schema_version", "embodiment_id", "projector_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if not isinstance(self.dataset_schema, DatasetSchema):
            raise TypeError("dataset_schema must be DatasetSchema")
        if not isinstance(self.model_schema, ModelInputSchema):
            raise TypeError("model_schema must be ModelInputSchema")
        cameras = tuple(self.camera_bindings)
        if not cameras or any(not isinstance(item, CameraBinding) for item in cameras):
            raise TypeError("camera_bindings must contain CameraBinding values")
        for values, label in (
            ([item.dataset_camera for item in cameras], "dataset cameras"),
            ([item.model_camera for item in cameras], "model cameras"),
            ([item.dataset_index for item in cameras], "dataset camera indices"),
            ([item.model_index for item in cameras], "model camera indices"),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{label} must not contain duplicates")
        object.__setattr__(self, "camera_bindings", cameras)
        required_types = (
            ("language_binding", LanguageBinding),
            ("state_binding", StateBinding),
            ("action_binding", ActionBinding),
            ("temporal_binding", TemporalBinding),
            ("normalization_binding", NormalizationBinding),
        )
        for field_name, expected_type in required_types:
            if not isinstance(getattr(self, field_name), expected_type):
                raise TypeError(f"{field_name} must be {expected_type.__name__}")
        object.__setattr__(self, "accepted_level", _level(self.accepted_level, "accepted_level"))
        for name in ("dropped_fields", "filled_fields", "projected_fields"):
            object.__setattr__(self, name, _texts(getattr(self, name), name, allow_empty=True))
        if self.dataset_schema.immutable_dataset_fingerprint != self.immutable_dataset_fingerprint:
            raise ValueError("binding dataset fingerprint must remain immutable")

    @property
    def immutable_dataset_fingerprint(self) -> str:
        """返回绑定所引用的不可变数据集指纹。"""
        return self.dataset_schema.immutable_dataset_fingerprint

    @property
    def fingerprint(self) -> str:
        """返回包含 schema 和所有投影确认的稳定绑定指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class DatasetCompatibilityReport:
    """保存确定性兼容性结论、指纹、原因和显式变换清单。"""

    level: DatasetCompatibilityLevel
    binding_fingerprint: str
    dataset_schema_fingerprint: str
    model_schema_fingerprint: str
    immutable_dataset_fingerprint: str
    reason_codes: tuple[str, ...]
    transforms: tuple[str, ...]
    dropped_fields: tuple[str, ...]
    filled_fields: tuple[str, ...]
    projected_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    batch_factory_allowed: bool
    real_data_validated: bool

    def __post_init__(self) -> None:
        """校验报告枚举、所有 SHA-256、去重列表和严格声明布尔值。"""
        object.__setattr__(self, "level", _level(self.level, "level"))
        for name in (
            "binding_fingerprint",
            "dataset_schema_fingerprint",
            "model_schema_fingerprint",
            "immutable_dataset_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        for name in (
            "reason_codes",
            "transforms",
            "dropped_fields",
            "filled_fields",
            "projected_fields",
            "warnings",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), name, allow_empty=True))
        object.__setattr__(
            self,
            "batch_factory_allowed",
            _strict_bool(self.batch_factory_allowed, "batch_factory_allowed"),
        )
        object.__setattr__(
            self,
            "real_data_validated",
            _strict_bool(self.real_data_validated, "real_data_validated"),
        )
        if self.real_data_validated:
            raise ValueError("static binding reports cannot claim real-data validation")

    @property
    def fingerprint(self) -> str:
        """返回完整兼容性报告的稳定指纹。"""
        return sha256_fingerprint(self)


__all__ = [
    "ActionBinding",
    "CameraBinding",
    "DatasetCompatibilityLevel",
    "DatasetCompatibilityReport",
    "DatasetModelBinding",
    "DatasetSchema",
    "EmbodimentSchema",
    "LanguageBinding",
    "ModelInputSchema",
    "NormalizationBinding",
    "PhysicalFeatureSpec",
    "StateBinding",
    "TemporalBinding",
    "canonical_data",
    "canonical_serialize",
    "semantics_unknown",
    "sha256_fingerprint",
]
