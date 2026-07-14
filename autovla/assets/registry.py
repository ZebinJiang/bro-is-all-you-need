"""模型资产规范注册表与官方 GR00T 固定规范。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from autovla.assets.contracts import ModelAssetFile, ModelAssetSpec
from autovla.assets.errors import ModelAssetConfigurationError


@dataclass(frozen=True, slots=True, init=False)
class ModelAssetRegistry:
    """不可变键到资产规范的轻量注册表。"""

    _specs: Mapping[str, ModelAssetSpec]

    def __init__(self, specs: tuple[ModelAssetSpec, ...] = ()) -> None:
        """拒绝重复键并冻结映射。"""

        mapping = {spec.key: spec for spec in specs}
        if len(mapping) != len(specs):
            raise ModelAssetConfigurationError("duplicate model asset registry key")
        object.__setattr__(self, "_specs", MappingProxyType(mapping))

    def require(self, key: str) -> ModelAssetSpec:
        """返回注册规范，未知键给出明确错误。"""

        try:
            return self._specs[key]
        except KeyError as exc:
            raise ModelAssetConfigurationError(f"unknown model asset key: {key!r}") from exc

    def list(self) -> tuple[ModelAssetSpec, ...]:
        """按 key 稳定排序返回全部规范。"""

        return tuple(self._specs[key] for key in sorted(self._specs))


GR00T_N1D6_ASSET_SPEC = ModelAssetSpec(
    key="gr00t_n1d6",
    family_key="gr00t_n1d6",
    provider="huggingface",
    source_url="https://huggingface.co/nvidia/GR00T-N1.6-3B",
    public_identifier="nvidia/GR00T-N1.6-3B",
    repository="nvidia/GR00T-N1.6-3B",
    revision="d0814e7ecb19202e7c8468b46098b0b7ef3a6d61",
    license_name="NVIDIA License",
    license_file_path="LICENSE",
    use_limitation="non-commercial research or evaluation only",
    redistribution=(
        "AutoVLA does not redistribute or commit this asset; any redistribution must follow "
        "the NVIDIA License with complete license and retained notices"
    ),
    checksum_policy="sha256-size-v1",
    remote_code_required=False,
    files=(
        ModelAssetFile(
            "LICENSE",
            4063,
            "fdc54058d8b52bbb3b06c924326ff95a15687b08b15f92bc63adabc291638c89",
            "license",
        ),
        ModelAssetFile(
            "config.json",
            1818,
            "f2702d11bbde7ebf250b81f28bbef606bf1aa2acdb5ce4f5304a2a29054c3c7b",
            "model_config",
        ),
        ModelAssetFile(
            "embodiment_id.json",
            148,
            "d30b5175fdf87b6b40f6b62f8f0e131fcd4b59759a666956190e8110ac61629f",
            "embodiment_mapping",
        ),
        ModelAssetFile(
            "model-00001-of-00002.safetensors",
            4991091456,
            "9710d31d331b79cfa229fd23605ba9ad47e207cb0f4c7722fe0bacdc666c8326",
            "base_model_weights",
        ),
        ModelAssetFile(
            "model-00002-of-00002.safetensors",
            1582283096,
            "eb79bbd7893068897cda18c86ed91064e92e20e356dea97bc398bf9c8bf2fa35",
            "base_model_weights",
        ),
        ModelAssetFile(
            "model.safetensors.index.json",
            121820,
            "4baab54d48f5492daeea0a18d29bf8956661367820d6a19feb0dab10848ef5ab",
            "checkpoint_index",
        ),
        ModelAssetFile(
            "processor_config.json",
            9318,
            "3c38bc24a9bbb333a567f9093abb959c1205a04acdb0a0229f86262ada4e0274",
            "processor_config",
        ),
        ModelAssetFile(
            "statistics.json",
            262849,
            "cefa9f4c612a350a4d406a501c6640d0a2371004d63d7b7e3c9703aac41a455b",
            "normalization_statistics",
        ),
    ),
)

DEFAULT_MODEL_ASSET_REGISTRY = ModelAssetRegistry((GR00T_N1D6_ASSET_SPEC,))
