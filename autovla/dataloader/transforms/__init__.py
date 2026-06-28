"""AutoVLA dataloader transforms 导出。"""

from collections.abc import Mapping
from typing import Any, Literal, cast

from autovla.dataloader.contracts import (
    ComposeConfig,
    SerializableTransformProtocol,
    TransformContext,
    TransformSpec,
)
from autovla.dataloader.statistics import FeatureStatistics
from autovla.dataloader.transforms.action_mode import ActionModeTransform
from autovla.dataloader.transforms.compose import (
    ComposeTransform,
    TransformRegistry,
    stable_transform_fingerprint,
)
from autovla.dataloader.transforms.image import ImageAugment, ImageNormalize, ImageResize
from autovla.dataloader.transforms.state_action import (
    StateActionNormalize,
    StateActionUnnormalize,
)


def _params(spec: TransformSpec) -> Mapping[str, object]:
    """返回 TransformSpec 的参数映射。"""
    return spec.params


def _tuple_param(value: object, *, name: str) -> tuple[object, ...]:
    """读取 JSON 序列参数。"""
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a JSON array")
    return cast(tuple[object, ...], value)


def _string_param(value: object, *, name: str) -> str:
    """读取字符串参数。"""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _channel_order_param(value: object, *, name: str) -> Literal["HWC", "CHW"]:
    """读取并收窄图像 channel order。"""
    text = _string_param(value, name=name)
    if text == "HWC":
        return "HWC"
    if text == "CHW":
        return "CHW"
    raise ValueError("channel_order must be HWC or CHW")


def _input_range_param(value: object, *, name: str) -> Literal["0_255", "0_1"]:
    """读取并收窄图像输入范围。"""
    text = _string_param(value, name=name)
    if text == "0_255":
        return "0_255"
    if text == "0_1":
        return "0_1"
    raise ValueError("input_range must be 0_255 or 0_1")


def _augment_mode_param(value: object, *, name: str) -> Literal["none", "horizontal_flip"]:
    """读取并收窄图像增强模式。"""
    text = _string_param(value, name=name)
    if text == "none":
        return "none"
    if text == "horizontal_flip":
        return "horizontal_flip"
    raise ValueError(f"unsupported image augment mode: {text}")


def _action_mode_param(value: object, *, name: str) -> Literal["absolute", "delta", "relative"]:
    """读取并收窄动作模式。"""
    text = _string_param(value, name=name)
    if text == "absolute":
        return "absolute"
    if text == "delta":
        return "delta"
    if text == "relative":
        return "relative"
    raise ValueError("unsupported action mode")


def _reference_frame_param(
    value: object, *, name: str
) -> Literal["world", "previous_action", "state"]:
    """读取并收窄动作参考系。"""
    text = _string_param(value, name=name)
    if text == "world":
        return "world"
    if text == "previous_action":
        return "previous_action"
    if text == "state":
        return "state"
    raise ValueError("unsupported reference frame")


def _first_step_policy_param(value: object, *, name: str) -> Literal["absolute", "zero"]:
    """读取并收窄 delta 首步策略。"""
    text = _string_param(value, name=name)
    if text == "absolute":
        return "absolute"
    if text == "zero":
        return "zero"
    raise ValueError("first_step_policy must be absolute or zero")


def _float_param(value: object, *, name: str) -> float:
    """读取 float 参数。"""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    return float(value)


def _int_param(value: object, *, name: str) -> int:
    """读取 int 参数。"""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    return value


def _feature_statistics(value: object) -> FeatureStatistics | None:
    """从 JSON-safe payload 恢复可选 FeatureStatistics。"""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("feature statistics must be a JSON object")
    return FeatureStatistics.from_json_dict(cast(Mapping[str, Any], value))


def _image_resize_from_spec(spec: TransformSpec) -> ImageResize:
    """从配置恢复 ImageResize。"""
    params = _params(spec)
    size = _tuple_param(params["size"], name="size")
    if len(size) != 2:
        raise ValueError("size must have two elements")
    return ImageResize(
        size=(_int_param(size[0], name="height"), _int_param(size[1], name="width")),
        channel_order=_channel_order_param(
            params.get("channel_order", "HWC"), name="channel_order"
        ),
    )


def _image_normalize_from_spec(spec: TransformSpec) -> ImageNormalize:
    """从配置恢复 ImageNormalize。"""
    params = _params(spec)
    mean = tuple(
        _float_param(value, name="mean") for value in _tuple_param(params["mean"], name="mean")
    )
    std = tuple(
        _float_param(value, name="std") for value in _tuple_param(params["std"], name="std")
    )
    return ImageNormalize(
        mean=mean,
        std=std,
        channel_order=_channel_order_param(
            params.get("channel_order", "HWC"), name="channel_order"
        ),
        input_range=_input_range_param(params.get("input_range", "0_1"), name="input_range"),
    )


def _image_augment_from_spec(spec: TransformSpec) -> ImageAugment:
    """从配置恢复 ImageAugment。"""
    params = _params(spec)
    return ImageAugment(
        mode=_augment_mode_param(params.get("mode", "none"), name="mode"),
        probability=_float_param(params.get("probability", 1.0), name="probability"),
        seed=_int_param(params.get("seed", 0), name="seed"),
        channel_order=_channel_order_param(
            params.get("channel_order", "HWC"), name="channel_order"
        ),
    )


def _state_action_normalize_from_spec(spec: TransformSpec) -> StateActionNormalize:
    """从配置恢复 StateActionNormalize。"""
    params = _params(spec)
    return StateActionNormalize(
        state=_feature_statistics(params.get("state")),
        action=_feature_statistics(params.get("action")),
    )


def _state_action_unnormalize_from_spec(spec: TransformSpec) -> StateActionUnnormalize:
    """从配置恢复 StateActionUnnormalize。"""
    params = _params(spec)
    return StateActionUnnormalize(
        state=_feature_statistics(params.get("state")),
        action=_feature_statistics(params.get("action")),
    )


def _action_mode_from_spec(spec: TransformSpec) -> ActionModeTransform:
    """从配置恢复 ActionModeTransform。"""
    params = _params(spec)
    reference = params.get("first_action_reference")
    first_action_reference = (
        tuple(
            _float_param(value, name="first_action_reference")
            for value in _tuple_param(reference, name="first_action_reference")
        )
        if reference is not None
        else None
    )
    indices = tuple(
        _int_param(value, name="state_to_action_indices")
        for value in _tuple_param(
            params.get("state_to_action_indices", ()), name="state_to_action_indices"
        )
    )
    return ActionModeTransform(
        mode=_action_mode_param(params["mode"], name="mode"),
        reference_frame=_reference_frame_param(params["reference_frame"], name="reference_frame"),
        first_step_policy=_first_step_policy_param(
            params.get("first_step_policy", "absolute"), name="first_step_policy"
        ),
        state_to_action_indices=indices,
        first_action_reference=first_action_reference,
        inverse_mode=bool(params.get("inverse_mode", False)),
    )


def default_transform_registry() -> TransformRegistry:
    """返回包含 Data 生产转换工厂的默认注册表。"""
    registry = TransformRegistry()
    registry.register("image_resize", _image_resize_from_spec)
    registry.register("image_normalize", _image_normalize_from_spec)
    registry.register("image_augment", _image_augment_from_spec)
    registry.register("state_action_normalize", _state_action_normalize_from_spec)
    registry.register("state_action_unnormalize", _state_action_unnormalize_from_spec)
    registry.register("action_mode", _action_mode_from_spec)
    return registry


__all__ = [
    "ActionModeTransform",
    "ComposeConfig",
    "ComposeTransform",
    "ImageAugment",
    "ImageNormalize",
    "ImageResize",
    "SerializableTransformProtocol",
    "StateActionNormalize",
    "StateActionUnnormalize",
    "TransformContext",
    "TransformRegistry",
    "TransformSpec",
    "default_transform_registry",
    "stable_transform_fingerprint",
]
