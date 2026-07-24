"""N1.7 processor/modality/action_config 的纯契约投影。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeVar, cast

import numpy as np
import torch
from numpy.typing import NDArray

from autovla.core.types.training import TrainingBatch
from autovla.data.transforms import (
    DEFAULT_SE3_TOLERANCES,
    ExecutionSide,
    RotationRepresentation,
    SE3FrameConvention,
    SE3RelativeActionTransform,
    SE3RotationCodec,
    SE3TypedParameter,
    TransformPlan,
    closed_pose_row_validity,
)
from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.interfaces.processor import ModelProcessor
from autovla.models.outputs import ActionPrediction, ModelInputBatch

Float32Array = NDArray[np.float32]
Float64Array = NDArray[np.float64]
FloatingArray = Float32Array | Float64Array
BoolArray = NDArray[np.bool_]
ImageArray = NDArray[np.generic]


class _LocalQwenProcessor(Protocol):
    """描述本地 Transformers processor 的最小调用面。"""

    tokenizer: object

    def __call__(self, **kwargs: object) -> Mapping[str, object]:
        """返回 input_ids、attention_mask、pixel_values 和 image_grid_thw。"""

        ...


class _ActionType(str, Enum):
    """区分末端位姿与普通动作。"""

    EEF = "eef"
    NON_EEF = "non_eef"


class _ActionRepresentation(str, Enum):
    """声明 artifact action_config 的物理表示。"""

    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class _ActionFormat(str, Enum):
    """声明 processor 可投影的动作编码。"""

    XYZ_ROT6D = "xyz_rot6d"
    VECTOR = "vector"


@dataclass(frozen=True, slots=True)
class _ActionProjection:
    """保存一个动作切片及规范 SE(3) 投影元数据。"""

    key: str
    state_key: str
    action_type: _ActionType
    representation: _ActionRepresentation
    action_format: _ActionFormat
    source_indices: tuple[int, ...]
    canonical_pose_indices: tuple[int, int, int, int, int, int] | None = None
    state_pose_indices: tuple[int, int, int, int, int, int] | None = None

    def __post_init__(self) -> None:
        """拒绝不完整或越过 132 维 envelope 的投影。"""

        if not self.key.strip() or not self.state_key.strip():
            raise ValueError("action and state keys must not be empty")
        if not self.source_indices or len(set(self.source_indices)) != len(self.source_indices):
            raise ValueError("source action indices must be non-empty and unique")
        if any(
            type(index) is not int or index < 0 or index >= 132 for index in self.source_indices
        ):
            raise ValueError("source action indices must stay inside dimension 132")
        for field, indices in (
            ("canonical pose", self.canonical_pose_indices),
            ("state pose", self.state_pose_indices),
        ):
            if indices is not None and (
                len(set(indices)) != 6
                or any(type(index) is not int or index < 0 or index >= 132 for index in indices)
            ):
                raise ValueError(f"{field} indices must be unique inside dimension 132")
        relative_eef = (
            self.action_type is _ActionType.EEF
            and self.representation is _ActionRepresentation.RELATIVE
        )
        if relative_eef and (
            self.action_format is not _ActionFormat.XYZ_ROT6D
            or len(self.source_indices) != 9
            or self.canonical_pose_indices is None
            or self.state_pose_indices is None
        ):
            raise ValueError("relative EEF XYZ_ROT6D requires source and canonical pose indices")
        if not relative_eef and (
            self.canonical_pose_indices is not None or self.state_pose_indices is not None
        ):
            raise ValueError("only relative EEF actions may declare SE3 pose indices")


@dataclass(frozen=True, slots=True)
class _ProcessorProjection:
    """保存已关闭的有序 processor 投影。"""

    image_keys: tuple[str, ...]
    state_keys: tuple[str, ...]
    action_configs: tuple[_ActionProjection, ...]
    image_grid_thw: tuple[tuple[int, int, int], ...]
    left_padding: bool = True
    images_before_language: bool = True


_EnumT = TypeVar("_EnumT", bound=Enum)


def _enum_value(enum_type: type[_EnumT], value: object, field: str) -> _EnumT:
    """把 artifact 字符串收窄到封闭枚举。"""

    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported action_config {field}: {value!r}") from exc


class Gr00tN1d7Processor(ModelProcessor):
    """验证动态图像网格、132 维 padding/mask 和 action_config 投影。

    本类不导入 Qwen/Transformers 且不搬运 tensor。实际 tokenizer 和图像
    processor 必须由后续已许可的本地资产运行波次注入。
    """

    def __init__(
        self,
        config: Gr00tN1d7Config,
        qwen_processor: _LocalQwenProcessor | None = None,
        *,
        statistics: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        """绑定 artifact 配置、本地 Qwen processor 与具身统计量。"""

        self.config = _require_config(config)
        self._qwen_processor = qwen_processor
        self._statistics = dict(statistics or {})

    @classmethod
    def from_request(cls, request: ModelAssemblyRequest) -> Gr00tN1d7Processor:
        """实现共享组件工厂输入面。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config)

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        training: bool,
    ) -> ModelInputBatch:
        """把 canonical ``TrainingBatch`` 转为 Qwen3-VL flexible-resolution 输入。

        图像保持 batch/camera/history 顺序, 状态与动作归一化并 pad 到 132,
        动作 horizon pad 到 40; 所有 mask 都保持逐元素严格 bool。
        """

        if self._qwen_processor is None:
            raise ValueError("local Qwen3-VL processor assets are required for prepare_batch")
        batch_size = len(batch.language)
        embodiments = _batch_embodiments(batch, batch_size)
        embodiment_ids = torch.tensor(
            [self._embodiment_id(name) for name in embodiments],
            dtype=torch.long,
            device=device,
        )
        images, per_sample_images = _ordered_images(batch)
        tokenizer = getattr(self._qwen_processor, "tokenizer", None)
        if tokenizer is not None and hasattr(tokenizer, "padding_side"):
            tokenizer.padding_side = "left"
        encoded = self._qwen_processor(
            text=[
                _vision_prompt(text, len(per_sample_images[index]))
                for index, text in enumerate(batch.language)
            ],
            images=per_sample_images,
            padding=True,
            return_tensors="pt",
        )
        required = ("input_ids", "attention_mask", "pixel_values", "image_grid_thw")
        if any(not isinstance(encoded.get(name), torch.Tensor) for name in required):
            raise ValueError("Qwen3-VL processor must return four required tensors")
        input_ids = cast(torch.Tensor, encoded["input_ids"]).to(device=device)
        attention_mask = cast(torch.Tensor, encoded["attention_mask"]).to(device=device).bool()
        pixel_values = cast(torch.Tensor, encoded["pixel_values"]).to(device=device, dtype=dtype)
        image_grid_thw = cast(torch.Tensor, encoded["image_grid_thw"]).to(
            device=device, dtype=torch.long
        )
        target_dtype = dtype or pixel_values.dtype
        state, raw_state = self._prepare_state(
            batch.state, embodiments, device=device, dtype=target_dtype
        )
        actions, action_mask = self._prepare_actions(
            batch.actions,
            batch.action_mask,
            embodiments,
            device=device,
            dtype=target_dtype,
        )
        return ModelInputBatch(
            images=images,
            input_ids=input_ids,
            attention_mask=attention_mask,
            state=state,
            embodiment_ids=embodiment_ids,
            actions=actions,
            action_mask=action_mask,
            raw_state=raw_state,
            embodiments=embodiments,
            camera_order=tuple(batch.images),
            sample_source=batch.sample_source,
            physical_action_shapes=tuple(
                (min(batch.actions.shape[1], 40), min(batch.actions.shape[2], 132))
                for _ in range(batch_size)
            ),
            metadata={
                "pixel_values": pixel_values,
                "image_grid_thw": image_grid_thw,
                "training": training,
                "statistics_fingerprint": batch.statistics_fingerprint,
                "dataset_fingerprint": batch.dataset_fingerprint,
            },
        )

    def decode_actions(
        self,
        actions: torch.Tensor,
        *,
        batch: ModelInputBatch,
    ) -> ActionPrediction:
        """按每个 embodiment 统计量反归一化并保留 ``[B,40,132]`` mask。"""

        if actions.shape != (batch.batch_size, 40, 132):
            raise ValueError("N1.7 decoded actions must have shape [B,40,132]")
        decoded = actions.clone()
        for index, embodiment in enumerate(batch.embodiments):
            mean, std = self._normalization(embodiment, "action")
            mean_tensor = torch.as_tensor(mean, device=actions.device, dtype=actions.dtype)
            std_tensor = torch.as_tensor(std, device=actions.device, dtype=actions.dtype)
            decoded[index] = actions[index] * std_tensor + mean_tensor
        mask = (
            batch.action_mask
            if batch.action_mask is not None
            else torch.ones_like(actions, dtype=torch.bool)
        )
        return ActionPrediction(actions, mask, decoded)

    def _embodiment_id(self, name: str) -> int:
        """解析具身 projector id, 禁止未知身份回退。"""

        try:
            return self.config.embodiment_ids[name]
        except KeyError as exc:
            raise ValueError(f"unknown N1.7 embodiment: {name!r}") from exc

    def _normalization(self, embodiment: str, kind: str) -> tuple[Float32Array, Float32Array]:
        """读取显式 mean/std; 不允许 identity 静默回退。"""

        try:
            record = self._statistics[embodiment]
            raw = record[kind]
        except KeyError as exc:
            raise ValueError(f"{kind} statistics missing for {embodiment!r}") from exc
        if not isinstance(raw, Mapping):
            raise TypeError(f"{kind} statistics must be a mapping")
        mean = np.asarray(raw.get("mean"), dtype=np.float32)
        std = np.asarray(raw.get("std"), dtype=np.float32)
        if mean.ndim != 1 or std.shape != mean.shape or not bool((std > 0).all()):
            raise ValueError(f"{kind} statistics must contain positive one-dimensional std")
        if mean.size > 132 or not bool(np.isfinite(mean).all() and np.isfinite(std).all()):
            raise ValueError(f"{kind} statistics exceed the finite 132-dimensional envelope")
        padded_mean = np.zeros((132,), dtype=np.float32)
        padded_std = np.ones((132,), dtype=np.float32)
        padded_mean[: mean.size] = mean
        padded_std[: std.size] = std
        return padded_mean, padded_std

    def _prepare_state(
        self,
        raw_state: object,
        embodiments: tuple[str, ...],
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """归一化状态并输出 ``[B,1,132]``。"""

        if raw_state is None:
            raise ValueError("N1.7 requires state inputs")
        values = torch.as_tensor(np.array(raw_state, copy=True), device=device, dtype=dtype)
        if values.ndim == 2:
            values = values.unsqueeze(1)
        if values.ndim != 3 or values.shape[-1] > 132:
            raise ValueError("state must have shape [B,D] or [B,T,D] with D<=132")
        # N1.7 视觉可含历史, 但状态和语言严格使用当前步。
        values = values[:, -1:, :]
        padded = torch.zeros((*values.shape[:-1], 132), device=device, dtype=dtype)
        padded[..., : values.shape[-1]] = values
        normalized = padded.clone()
        for index, embodiment in enumerate(embodiments):
            mean, std = self._normalization(embodiment, "state")
            normalized[index] = (
                padded[index] - torch.as_tensor(mean, device=device, dtype=dtype)
            ) / torch.as_tensor(std, device=device, dtype=dtype)
        return normalized, padded

    def _prepare_actions(
        self,
        raw_actions: object,
        raw_mask: object,
        embodiments: tuple[str, ...],
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """逐元素归一化并 pad 动作和 bool mask 到 ``[B,40,132]``。"""

        values = torch.as_tensor(np.array(raw_actions, copy=True), device=device, dtype=dtype)
        mask = torch.as_tensor(np.array(raw_mask, copy=True), device=device)
        if mask.dtype != torch.bool or values.ndim != 3 or mask.shape != values.shape:
            raise ValueError("actions and strict bool mask must share [B,H,D]")
        if values.shape[1] > 40 or values.shape[2] > 132:
            raise ValueError("actions exceed the N1.7 40x132 envelope")
        padded = torch.zeros((values.shape[0], 40, 132), device=device, dtype=dtype)
        padded_mask = torch.zeros_like(padded, dtype=torch.bool)
        padded[:, : values.shape[1], : values.shape[2]] = values
        padded_mask[:, : mask.shape[1], : mask.shape[2]] = mask
        for index, embodiment in enumerate(embodiments):
            mean, std = self._normalization(embodiment, "action")
            padded[index] = (
                padded[index] - torch.as_tensor(mean, device=device, dtype=dtype)
            ) / torch.as_tensor(std, device=device, dtype=dtype)
        return padded, padded_mask

    def project_contract(
        self,
        *,
        image_keys: Sequence[str],
        state_keys: Sequence[str],
        action_configs: Sequence[Mapping[str, object]],
        image_grid_thw: Sequence[Sequence[int]],
    ) -> _ProcessorProjection:
        """把本地 processor/modality JSON 投影为固定顺序契约。"""

        images = tuple(image_keys)
        states = tuple(state_keys)
        if not images or len(set(images)) != len(images) or any(not key.strip() for key in images):
            raise ValueError("image modality keys must be non-empty and unique")
        if not states or len(set(states)) != len(states) or any(not key.strip() for key in states):
            raise ValueError("state modality keys must be non-empty and unique")
        grids: list[tuple[int, int, int]] = []
        for raw_grid in image_grid_thw:
            grid = tuple(raw_grid)
            if len(grid) != 3 or any(type(value) is not int or value <= 0 for value in grid):
                raise ValueError("image_grid_thw entries must be positive [T,H,W] triples")
            grids.append((grid[0], grid[1], grid[2]))
        if len(grids) != len(images):
            raise ValueError("dynamic image grids must align with ordered image modalities")
        projections = tuple(self._project_action(item) for item in action_configs)
        occupied: set[int] = set()
        canonical_occupied: set[int] = set()
        for projection in projections:
            if occupied.intersection(projection.source_indices):
                raise ValueError("action_config slices must not overlap")
            occupied.update(projection.source_indices)
            canonical = projection.canonical_pose_indices
            if canonical is not None:
                if canonical_occupied.intersection(canonical):
                    raise ValueError("canonical action pose slices must not overlap")
                canonical_occupied.update(canonical)
        for projection in projections:
            canonical = set(projection.canonical_pose_indices or ())
            foreign_source = occupied.difference(projection.source_indices)
            if canonical.intersection(foreign_source):
                raise ValueError("canonical action pose must not overwrite another source slice")
        if not projections:
            raise ValueError("at least one action_config is required")
        return _ProcessorProjection(images, states, projections, tuple(grids))

    def transform_plan(self, projection: _ProcessorProjection) -> TransformPlan:
        """为相对 EEF 项生成唯一共享 TransformPlan/SE(3) 阶段。"""

        stages: list[SE3RelativeActionTransform] = []
        for action in projection.action_configs:
            if action.canonical_pose_indices is None or action.state_pose_indices is None:
                continue
            stages.append(
                SE3RelativeActionTransform(
                    action_feature="actions",
                    state_feature="reference_state",
                    action_translation_indices=action.canonical_pose_indices[:3],
                    action_rotation_indices=action.canonical_pose_indices[3:],
                    state_translation_indices=action.state_pose_indices[:3],
                    state_rotation_indices=action.state_pose_indices[3:],
                    rotation_representation=RotationRepresentation.AXIS_ANGLE,
                    frame_convention=SE3FrameConvention.REFERENCE_LOCAL,
                    valid_dimension_mask=(True,) * 132,
                    mask_feature="action_mask",
                    parameters=(
                        SE3TypedParameter("family", "gr00t_n1d7"),
                        SE3TypedParameter("action_config_key", action.key),
                        SE3TypedParameter("source_format", action.action_format.value),
                    ),
                    provenance="n1d7_action_config_projection_to_canonical_se3",
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                    tolerances=DEFAULT_SE3_TOLERANCES,
                )
            )
        return TransformPlan(tuple(stages))

    def forward_action_projection(
        self,
        *,
        actions: FloatingArray,
        action_mask: BoolArray,
        projection: _ProcessorProjection,
    ) -> tuple[FloatingArray, BoolArray]:
        """把 ``[40,132]`` 的 XYZ_ROT6D 源槽投影到规范轴角槽。

        ROT6D 按旋转矩阵前两行的顺序解释。正向投影只改写投影拥有的
        source/canonical 槽及其 mask,其他动作维度和 mask 保持逐位不变。
        """

        values, masks = self._validate_projection_arrays(actions, action_mask, projection)
        output = _copy_floating_array(values)
        output_mask = np.array(masks, dtype=np.bool_, copy=True)
        for item in projection.action_configs:
            if item.canonical_pose_indices is None:
                continue
            source = list(item.source_indices)
            canonical = list(item.canonical_pose_indices)
            valid = closed_pose_row_validity(
                masks[:, source],
                context=f"action projection {item.key!r}",
            )
            output_mask[:, source] = False
            output_mask[:, canonical] = valid[:, None]
            for row in np.flatnonzero(valid):
                source_pose = values[row, source]
                rotation = _rot6d_to_matrix(source_pose[3:])
                output[row, canonical[:3]] = source_pose[:3]
                output[row, canonical[3:]] = _N1D7_ROTATION_CODEC.from_matrix(
                    rotation,
                    RotationRepresentation.AXIS_ANGLE,
                )
        _require_finite_output(output)
        return output, output_mask

    def inverse_action_projection(
        self,
        *,
        actions: FloatingArray,
        action_mask: BoolArray,
        projection: _ProcessorProjection,
    ) -> tuple[FloatingArray, BoolArray]:
        """把规范轴角槽逆投影为 ``[40,132]`` 的 XYZ_ROT6D 源槽。

        逆投影输出旋转矩阵的前两行,因此规范 SO(3) 行可稳定往返,其他
        非退化 ROT6D 输入会被确定性正交化;未拥有的维度和 mask 不变。
        """

        values, masks = self._validate_projection_arrays(actions, action_mask, projection)
        output = _copy_floating_array(values)
        output_mask = np.array(masks, dtype=np.bool_, copy=True)
        for item in projection.action_configs:
            if item.canonical_pose_indices is None:
                continue
            source = list(item.source_indices)
            canonical = list(item.canonical_pose_indices)
            valid = closed_pose_row_validity(
                masks[:, canonical],
                context=f"action projection {item.key!r}",
            )
            output_mask[:, canonical] = False
            output_mask[:, source] = valid[:, None]
            for row in np.flatnonzero(valid):
                canonical_pose = values[row, canonical]
                rotation = _N1D7_ROTATION_CODEC.to_matrix(
                    canonical_pose[3:],
                    RotationRepresentation.AXIS_ANGLE,
                )
                output[row, source[:3]] = canonical_pose[:3]
                rot6d = np.asarray(
                    [
                        rotation[0, 0],
                        rotation[0, 1],
                        rotation[0, 2],
                        rotation[1, 0],
                        rotation[1, 1],
                        rotation[1, 2],
                    ],
                    dtype=np.float64,
                )
                output[row, source[3:]] = rot6d
        _require_finite_output(output)
        return output, output_mask

    def _validate_projection_arrays(
        self,
        actions: FloatingArray,
        action_mask: BoolArray,
        projection: _ProcessorProjection,
    ) -> tuple[FloatingArray, BoolArray]:
        """严格校验家族动作数组,不执行输入类型或精度隐式转换。"""

        values, masks = _require_projection_array_types(actions, action_mask)
        expected = (self.config.action_horizon, self.config.max_action_dim)
        if values.shape != expected or masks.shape != expected:
            raise ValueError("N1.7 action projection requires actions and mask shaped [40,132]")
        if type(projection) is not _ProcessorProjection:
            raise TypeError("projection must be an N1.7 processor projection")
        if not bool(np.isfinite(values).all()):
            raise ValueError("N1.7 action projection requires finite actions")
        return values, masks

    @staticmethod
    def validate_padded_shapes(
        *,
        state_width: int,
        action_shape: tuple[int, int],
        state_mask_width: int,
        action_mask_shape: tuple[int, int],
    ) -> None:
        """关闭 state/action padding 与 mask 的 132/40 契约。"""

        if (state_width, action_shape, state_mask_width, action_mask_shape) != (
            132,
            (40, 132),
            132,
            (40, 132),
        ):
            raise ValueError("N1.7 padded state/action/mask shapes must be 132 and [40,132]")

    @staticmethod
    def _project_action(payload: Mapping[str, object]) -> _ActionProjection:
        """投影一个已解析的 action_config 记录。"""

        indices = payload.get("indices")
        if not isinstance(indices, Sequence) or isinstance(indices, (str, bytes)):
            raise ValueError("action_config indices must be a sequence")
        raw_indices = cast(Sequence[object], indices)
        if any(type(index) is not int for index in raw_indices):
            raise ValueError("action_config indices must contain exact integers")
        source_indices = tuple(cast(int, index) for index in raw_indices)
        canonical = payload.get("canonical_pose_indices")
        state_pose = payload.get("state_pose_indices")
        canonical_indices = _pose_indices(canonical, "canonical_pose_indices")
        state_pose_indices = _pose_indices(state_pose, "state_pose_indices")
        return _ActionProjection(
            key=str(payload.get("key", "")),
            state_key=str(payload.get("state_key", "")),
            action_type=_enum_value(_ActionType, payload.get("type"), "type"),
            representation=_enum_value(
                _ActionRepresentation, payload.get("representation"), "representation"
            ),
            action_format=_enum_value(_ActionFormat, payload.get("format"), "format"),
            source_indices=source_indices,
            canonical_pose_indices=canonical_indices,
            state_pose_indices=state_pose_indices,
        )


def _pose_indices(
    value: object,
    field: str,
) -> tuple[int, int, int, int, int, int] | None:
    """把可选位姿索引关闭为六个精确整数。"""

    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a six-index sequence")
    indices = tuple(cast(Sequence[object], value))
    if len(indices) != 6 or any(type(index) is not int for index in indices):
        raise ValueError(f"{field} must contain six exact integers")
    return cast(tuple[int, int, int, int, int, int], indices)


def _require_config(value: object) -> Gr00tN1d7Config:
    """在动态入口保留精确配置类型并向静态调用者返回关闭类型。"""

    if not isinstance(value, Gr00tN1d7Config):
        raise TypeError("processor requires Gr00tN1d7Config")
    return value


def _batch_embodiments(batch: TrainingBatch, batch_size: int) -> tuple[str, ...]:
    """返回逐样本具身身份并拒绝缺失或长度漂移。"""

    if batch.embodiment is None or len(batch.embodiment) != batch_size:
        raise ValueError("N1.7 TrainingBatch requires one embodiment per sample")
    return tuple(batch.embodiment)


def _vision_prompt(language: str, image_count: int) -> str:
    """把有序图像占位符置于语言之前, 匹配 Qwen3-VL chat token。"""

    if image_count <= 0:
        raise ValueError("Qwen3-VL prompt requires at least one image")
    marker = "<|vision_start|><|image_pad|><|vision_end|>"
    return marker * image_count + language


def _ordered_images(
    batch: TrainingBatch,
) -> tuple[dict[str, torch.Tensor], list[list[ImageArray]]]:
    """保持相机/历史顺序; 原图留在 CPU, 只搬运 processor 输出。"""

    batch_size = len(batch.language)
    output: dict[str, torch.Tensor] = {}
    per_sample: list[list[ImageArray]] = [[] for _ in range(batch_size)]
    for camera_name, raw_values in batch.images.items():
        values = np.asarray(raw_values)
        if values.shape[0] != batch_size or values.ndim not in {4, 5}:
            raise ValueError(f"camera {camera_name!r} must have [B,H,W,C] or [B,T,H,W,C]")
        if values.shape[-1] != 3:
            raise ValueError("Qwen3-VL images must contain exactly three channels")
        output[camera_name] = torch.as_tensor(np.array(values, copy=True))
        for sample_index in range(batch_size):
            sample = values[sample_index]
            frames = (sample,) if sample.ndim == 3 else tuple(sample)
            per_sample[sample_index].extend(np.array(frame, copy=True) for frame in frames)
    if not output or any(not images for images in per_sample):
        raise ValueError("N1.7 requires at least one ordered image per sample")
    return output, per_sample


def _require_projection_array_types(
    actions: object,
    action_mask: object,
) -> tuple[FloatingArray, BoolArray]:
    """在动态入口验证 NumPy 容器类型,不转换 dtype 或复制数据。"""

    if not isinstance(actions, np.ndarray) or not isinstance(action_mask, np.ndarray):
        raise TypeError("actions and action_mask must be NumPy arrays")
    raw_actions = cast(NDArray[np.generic], actions)
    raw_mask = cast(NDArray[np.generic], action_mask)
    if raw_actions.dtype == np.dtype(np.float32):
        values: FloatingArray = np.asarray(raw_actions, dtype=np.float32)
    elif raw_actions.dtype == np.dtype(np.float64):
        values = np.asarray(raw_actions, dtype=np.float64)
    else:
        raise TypeError("actions dtype must be exactly float32 or float64")
    if raw_mask.dtype != np.dtype(np.bool_):
        raise TypeError("action_mask dtype must be exactly bool")
    masks = np.asarray(raw_mask, dtype=np.bool_)
    return values, masks


def _copy_floating_array(values: FloatingArray) -> FloatingArray:
    """按已验证 dtype 复制浮点动作,避免泛型 dtype 扩散。"""

    if values.dtype == np.dtype(np.float32):
        return np.array(values, dtype=np.float32, copy=True)
    return np.array(values, dtype=np.float64, copy=True)


_ROT6D_DEGENERACY_EPS = 1e-8
_N1D7_ROTATION_CODEC = SE3RotationCodec(DEFAULT_SE3_TOLERANCES)


def _rot6d_to_matrix(values: FloatingArray) -> Float64Array:
    """用前两行 Gram-Schmidt 投影有限且非退化的 ROT6D。"""

    vector = np.asarray(values, dtype=np.float64)
    rows = np.asarray(np.reshape(vector, (2, 3)), dtype=np.float64)
    first_norm = float(np.linalg.norm(rows[0]))
    if first_norm <= _ROT6D_DEGENERACY_EPS:
        raise ValueError("ROT6D first axis is degenerate")
    first = rows[0] / first_norm
    second_residual = rows[1] - float(np.dot(first, rows[1])) * first
    second_norm = float(np.linalg.norm(second_residual))
    if second_norm <= _ROT6D_DEGENERACY_EPS:
        raise ValueError("ROT6D axes are collinear or degenerate")
    second = second_residual / second_norm
    third = np.cross(first, second)
    return np.stack((first, second, third), axis=0)


def _require_finite_output(actions: FloatingArray) -> None:
    """拒绝任何数值投影产生非有限动作。"""

    if not bool(np.isfinite(actions).all()):
        raise ValueError("N1.7 action projection produced non-finite actions")


def _build_processor(request: ModelAssemblyRequest) -> Gr00tN1d7Processor:
    """沿唯一 N1.7 工厂从本地资产构造 processor。"""

    from autovla.models.families.gr00t_n1d7.factory import Gr00tN1d7ModelFactory

    return Gr00tN1d7ModelFactory().build_processor(request)


__all__ = ["Gr00tN1d7Processor", "_build_processor"]
