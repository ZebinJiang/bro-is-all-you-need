"""模型资产规范注册表与官方 GR00T 固定规范。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from autovla.assets.contracts import ModelAssetFile, ModelAssetSpec
from autovla.assets.errors import ModelAssetConfigurationError


class ModelFamilyAssetState(str, Enum):
    """描述 M10 家族资产能否进入本地运行时验证。"""

    BLOCKED_C3_DATA = "BLOCKED_C3_DATA"
    BLOCKED_ASSET_LICENSE = "BLOCKED_ASSET_LICENSE"
    DEFERRED_BY_USER_PRIORITY = "DEFERRED_BY_USER_PRIORITY"


@dataclass(frozen=True, slots=True)
class ModelFamilyAssetStatus:
    """保存不访问文件系统或网络的家族资产状态。"""

    family_key: str
    state: ModelFamilyAssetState
    registered_asset_keys: tuple[str, ...]
    first_blocker: str
    runtime_authorized: bool = False

    def __post_init__(self) -> None:
        """校验状态记录不可伪造运行时授权。"""

        if not self.family_key or not self.first_blocker:
            raise ModelAssetConfigurationError("family asset status fields must not be empty")
        if type(self.state) is not ModelFamilyAssetState:
            raise ModelAssetConfigurationError("family asset state must use its closed enum")
        if len(set(self.registered_asset_keys)) != len(self.registered_asset_keys):
            raise ModelAssetConfigurationError("family asset keys must be unique")
        if type(self.runtime_authorized) is not bool or self.runtime_authorized:
            raise ModelAssetConfigurationError("M10 asset status must not authorize runtime")


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
        """返回注册规范,未知键给出明确错误。"""

        try:
            return self._specs[key]
        except KeyError as exc:
            raise ModelAssetConfigurationError(f"unknown model asset key: {key!r}") from exc

    def list(self) -> tuple[ModelAssetSpec, ...]:
        """按 key 稳定排序返回全部规范。"""

        return tuple(self._specs[key] for key in sorted(self._specs))


@dataclass(frozen=True, slots=True, init=False)
class ModelFamilyAssetStatusRegistry:
    """保存全部活跃及延后家族的失败关闭资产状态。"""

    _statuses: Mapping[str, ModelFamilyAssetStatus]

    def __init__(self, statuses: tuple[ModelFamilyAssetStatus, ...]) -> None:
        """拒绝重复家族并冻结状态映射。"""

        mapping = {status.family_key: status for status in statuses}
        if len(mapping) != len(statuses):
            raise ModelAssetConfigurationError("duplicate model family asset status")
        object.__setattr__(self, "_statuses", MappingProxyType(mapping))

    def require(self, family_key: str) -> ModelFamilyAssetStatus:
        """返回家族状态,未知键失败关闭。"""

        try:
            return self._statuses[family_key]
        except KeyError as exc:
            raise ModelAssetConfigurationError(
                f"unknown model family asset status: {family_key!r}"
            ) from exc

    def list(self, *, include_deferred: bool = False) -> tuple[ModelFamilyAssetStatus, ...]:
        """默认列出三个活跃家族,可显式包含延后家族。"""

        return tuple(
            self._statuses[key]
            for key in sorted(self._statuses)
            if include_deferred
            or self._statuses[key].state is not ModelFamilyAssetState.DEFERRED_BY_USER_PRIORITY
        )


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

_EAGLE = "gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2"

GR00T_N1D6_EAGLE_SUPPORT_SPEC = ModelAssetSpec(
    key="gr00t_n1d6_eagle_support",
    family_key="gr00t_n1d6",
    provider="local",
    source_url=(
        "https://github.com/NVIDIA/Isaac-GR00T/tree/"
        "5dc80c4afd726b34faad1d8f7e007a13b34e4c88/"
        "gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2"
    ),
    public_identifier="NVIDIA/Isaac-GR00T/Eagle-Block2A-2B-v2-support-data",
    repository="NVIDIA/Isaac-GR00T",
    revision="5dc80c4afd726b34faad1d8f7e007a13b34e4c88",
    license_name="NVIDIA License",
    license_file_path="LICENSE",
    use_limitation="non-commercial research under the pinned NVIDIA source license",
    redistribution=(
        "Preserve the complete NVIDIA License and all notices; this support-data bundle "
        "contains no executable Python and is distinct from model weights"
    ),
    checksum_policy="sha256-size-v1",
    remote_code_required=False,
    files=(
        ModelAssetFile(
            "LICENSE",
            4729,
            "564046abbef821cefd5c169d34ee1e96b3dfb72cf0be81de41ef8f4a1323c5a3",
            "license",
        ),
        ModelAssetFile(
            f"{_EAGLE}/config.json",
            2321,
            "2212673538fb6802d9d7d03380a3d4ae66cf230cf29a7955b3aea097f06a535b",
            "eagle_config",
        ),
        ModelAssetFile(
            f"{_EAGLE}/preprocessor_config.json",
            781,
            "f8762cfe6cc0d430fb17d9ff2d36590c1e53fa32d2a4b8b4b00da95b81a700c5",
            "image_processor_config",
        ),
        ModelAssetFile(
            f"{_EAGLE}/processor_config.json",
            394,
            "a4ef98b2fd4caa9d492101867effa4f094c2c1a9754cdb49782b287e9688040b",
            "processor_config",
        ),
        ModelAssetFile(
            f"{_EAGLE}/tokenizer_config.json",
            12035,
            "82e01decc6a6a7c36bcb238cf6dbc315d68455436ca1ac2171060626ede2082b",
            "tokenizer_config",
        ),
        ModelAssetFile(
            f"{_EAGLE}/vocab.json",
            3383407,
            "87a257b04b17642a0688c98cd1df89c398bda4fee532d6f88b38a659ecb4ac8d",
            "tokenizer_vocabulary",
        ),
        ModelAssetFile(
            f"{_EAGLE}/merges.txt",
            1671852,
            "85407d96ccd088398c5df07b7c764ed04dcc084b0e746f70016c16968be5e490",
            "tokenizer_merges",
        ),
        ModelAssetFile(
            f"{_EAGLE}/special_tokens_map.json",
            781,
            "1f7a26d4bd862741d920097c370aaac4010b483c0dec3c85e2b42954cd8ea342",
            "special_tokens",
        ),
        ModelAssetFile(
            f"{_EAGLE}/added_tokens.json",
            941,
            "4dd6146d2eccfb4a5c8e147df8876eb92be19ed60a3e65aab4d5d3e9f51f6d6a",
            "added_tokens",
        ),
        ModelAssetFile(
            f"{_EAGLE}/chat_template.json",
            1023,
            "6f8531a4671423abfe39617975d3be5d5ef57e95aabc81610279b9bbf7be1044",
            "chat_template",
        ),
        ModelAssetFile(
            f"{_EAGLE}/generation_config.json",
            121,
            "f15f5de33244a61325923e99bad2c061029acb8d6dd5c57f8458b3949ddd8f97",
            "generation_config",
        ),
    ),
)

DEFAULT_MODEL_ASSET_REGISTRY = ModelAssetRegistry(
    (GR00T_N1D6_ASSET_SPEC, GR00T_N1D6_EAGLE_SUPPORT_SPEC)
)

DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY = ModelFamilyAssetStatusRegistry(
    (
        ModelFamilyAssetStatus(
            family_key="gr00t_n1d6",
            state=ModelFamilyAssetState.BLOCKED_C3_DATA,
            registered_asset_keys=("gr00t_n1d6", "gr00t_n1d6_eagle_support"),
            first_blocker="BLOCKED_C3_DATA",
        ),
        ModelFamilyAssetStatus(
            family_key="gr00t_n1d7",
            state=ModelFamilyAssetState.BLOCKED_ASSET_LICENSE,
            registered_asset_keys=(),
            first_blocker=(
                "checkpoint terms conflict and Cosmos license/access receipts are unresolved"
            ),
        ),
        ModelFamilyAssetStatus(
            family_key="pi0_5",
            state=ModelFamilyAssetState.BLOCKED_ASSET_LICENSE,
            registered_asset_keys=(),
            first_blocker="PI05_CHECKPOINT_AND_GEMMA_TERMS_RECEIPT_MISSING",
        ),
        ModelFamilyAssetStatus(
            family_key="pi0",
            state=ModelFamilyAssetState.DEFERRED_BY_USER_PRIORITY,
            registered_asset_keys=(),
            first_blocker="DEFERRED_BY_USER_PRIORITY",
        ),
        ModelFamilyAssetStatus(
            family_key="pi0_fast",
            state=ModelFamilyAssetState.DEFERRED_BY_USER_PRIORITY,
            registered_asset_keys=(),
            first_blocker="DEFERRED_BY_USER_PRIORITY",
        ),
    )
)
