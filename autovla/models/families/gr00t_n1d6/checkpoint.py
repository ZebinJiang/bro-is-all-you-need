"""GR00T N1.6.1 本地 checkpoint 发现、转换和加载。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Iterator, Protocol, TypeGuard, cast, runtime_checkable

import numpy as np

if TYPE_CHECKING:
    import torch

from autovla.assets import (
    GR00T_N1D6_ASSET_SPEC,
    ModelAssetSpec,
    ModelAssetStore,
    ResolvedModelAsset,
)
from autovla.core.registry.errors import OptionalDependencyError
from autovla.core.semantics import AlignmentMode, AlignmentPolicy, TensorLayout
from autovla.data.normalization import ConstantFeaturePolicy
from autovla.models.components.relative_actions import (
    EndEffectorRepresentation,
    RelativeActionKind,
    RelativeActionPolicy,
)
from autovla.models.families.gr00t_n1d6.config import (
    EmbodimentStatistics,
    FeatureStatistics,
    Gr00tN1d6Config,
    PerHorizonFeatureStatistics,
)
from autovla.models.families.gr00t_n1d6.errors import LocalModelAssetError
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.models.outputs import (
    CheckpointCompatibilityReport,
    CheckpointLoadReport,
    CompatibilityIssue,
)

UPSTREAM_REPOSITORY = "https://github.com/NVIDIA/Isaac-GR00T"
UPSTREAM_PIN = "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"
SOURCE_LICENSE = "NVIDIA License (n1.6.1-release root)"
_SAFE_SHARD_BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.safetensors")
_OFFICIAL_ATTENTION_QKV = re.compile(
    r"^(action_head\.model\.transformer_blocks\.(?P<block>[0-9]+)\.attn1)\."
    r"to_(?P<projection>[qkv])\.(?P<parameter>weight|bias)$"
)


def _canonical_parameter_key(value: str) -> bool:
    """判断参数键是否非空、无空段且不含路径或控制字符。"""

    parts = value.split(".")
    return bool(parts) and all(
        part
        and part.strip() == part
        and not any(char.isspace() or char in "/\\" or ord(char) < 32 for char in part)
        for part in parts
    )


@dataclass(frozen=True, slots=True)
class UpstreamCheckpointLayout:
    """描述固定上游 shard index 与前缀命名空间。"""

    index_file: str
    shard_files: tuple[str, ...]
    key_count: int
    backbone_key_count: int
    action_head_key_count: int

    def __post_init__(self) -> None:
        """严格校验 index 路径、唯一安全 shard basename 和精确计数类型。"""

        raw_index = cast(object, self.index_file)
        if not isinstance(raw_index, str) or not raw_index.strip():
            raise ValueError("checkpoint index_file must be non-empty")
        index_path = Path(raw_index)
        if (
            "://" in raw_index
            or not index_path.is_absolute()
            or ".." in index_path.parts
            or index_path.name != "model.safetensors.index.json"
            or str(index_path) != raw_index
        ):
            raise ValueError("checkpoint index_file must identify model.safetensors.index.json")
        raw_shards = cast(object, self.shard_files)
        if type(raw_shards) is not tuple or not raw_shards:
            raise ValueError("checkpoint shard_files must be a non-empty tuple")
        shard_records = cast(tuple[object, ...], raw_shards)
        shards: list[str] = []
        for name in shard_records:
            if (
                not isinstance(name, str)
                or not name
                or Path(name).is_absolute()
                or Path(name).name != name
                or not _SAFE_SHARD_BASENAME.fullmatch(name)
            ):
                raise ValueError("checkpoint shard files must be safe safetensors basenames")
            shards.append(name)
        if len(shards) != len(set(shards)):
            raise ValueError("checkpoint shard_files must be unique")
        raw_counts = (
            cast(object, self.key_count),
            cast(object, self.backbone_key_count),
            cast(object, self.action_head_key_count),
        )
        if any(type(value) is not int or value < 0 for value in raw_counts):
            raise ValueError("checkpoint key counts must be non-negative exact integers")
        key_count, backbone_count, action_count = cast(tuple[int, int, int], raw_counts)
        if key_count <= 0 or backbone_count + action_count > key_count:
            raise ValueError("checkpoint key partition counts are inconsistent")
        object.__setattr__(self, "shard_files", tuple(shards))


@dataclass(frozen=True, slots=True)
class AutoVLAParameterLayout:
    """描述本地模型期望键集合及形状,不复制 tensor。"""

    shapes: Mapping[str, tuple[int, ...]]

    def __post_init__(self) -> None:
        """校验键和形状并用 mapping proxy 冻结布局。"""

        raw_shapes = cast(object, self.shapes)
        if not isinstance(raw_shapes, Mapping) or not raw_shapes:
            raise ValueError("parameter layout shapes must be a non-empty mapping")
        frozen: dict[str, tuple[int, ...]] = {}
        for key, shape in cast(Mapping[object, object], raw_shapes).items():
            if not isinstance(key, str) or not _canonical_parameter_key(key):
                raise ValueError("parameter layout keys must be canonical non-empty strings")
            if key in frozen:
                raise ValueError("parameter layout keys must be unique")
            if type(shape) is not tuple:
                raise ValueError("parameter layout shapes must contain non-negative exact integers")
            raw_dimensions = cast(tuple[object, ...], shape)
            if any(type(value) is not int or value < 0 for value in raw_dimensions):
                raise ValueError("parameter layout shapes must contain non-negative exact integers")
            frozen[key] = cast(tuple[int, ...], raw_dimensions)
        object.__setattr__(self, "shapes", MappingProxyType(frozen))


@dataclass(frozen=True, slots=True)
class CheckpointKeyRule:
    """描述一个可审计的前缀或容器键转换规则。"""

    source_prefix: str
    target_prefix: str

    def __post_init__(self) -> None:
        """要求来源前缀唯一可识别,目标仅允许规范容器前缀或空 strip。"""

        source = cast(object, self.source_prefix)
        target = cast(object, self.target_prefix)
        if (
            not isinstance(source, str)
            or not source
            or source.strip() != source
            or not source.endswith(".")
            or not _canonical_parameter_key(source[:-1])
        ):
            raise ValueError("checkpoint source prefix must be non-empty and end with a dot")
        if not isinstance(target, str) or target.strip() != target:
            raise ValueError("checkpoint target prefix must be a canonical string")
        if target and (not target.endswith(".") or not _canonical_parameter_key(target[:-1])):
            raise ValueError("checkpoint target prefix must be empty or end with a dot")
        if source == target:
            raise ValueError("checkpoint key rule must change its prefix")


@dataclass(frozen=True, slots=True)
class CheckpointLoadPolicy:
    """控制严格加载或只检查,不允许静默兼容。"""

    strict: bool = True
    inspect_only: bool = False
    allow_known_optional: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """拒绝布尔伪装、重复空 optional key 和互斥模式组合。"""

        if type(self.strict) is not bool or type(self.inspect_only) is not bool:
            raise ValueError("checkpoint policy flags must be exact bool")
        raw_optional = cast(object, self.allow_known_optional)
        if type(raw_optional) is not tuple:
            raise ValueError("checkpoint optional keys must be a tuple")
        optional_records = cast(tuple[object, ...], raw_optional)
        if any(
            not isinstance(key, str) or not _canonical_parameter_key(key)
            for key in optional_records
        ):
            raise ValueError("checkpoint optional keys must be non-empty canonical strings")
        optional_keys = cast(tuple[str, ...], optional_records)
        if len(optional_keys) != len(set(optional_keys)):
            raise ValueError("checkpoint optional keys must be unique")
        if self.inspect_only and self.strict:
            raise ValueError("checkpoint inspect_only and strict modes are mutually exclusive")
        if self.strict and optional_keys:
            raise ValueError("strict checkpoint policy cannot allow optional keys")
        object.__setattr__(self, "allow_known_optional", optional_keys)


CHECKPOINT_KEY_RULES = (
    CheckpointKeyRule("module.", ""),
    CheckpointKeyRule("_orig_mod.", ""),
    CheckpointKeyRule("action_head.state_encoder.", "action_head.conditioner.state_encoder."),
    CheckpointKeyRule("action_head.action_encoder.", "action_head.conditioner.action_encoder."),
    CheckpointKeyRule("action_head.action_decoder.", "action_head.conditioner.action_decoder."),
)

_PROCESSOR_FILES = ("processor_config.json", "statistics.json")
_OFFICIAL_ASSET_FILES = (
    "LICENSE",
    "config.json",
    "embodiment_id.json",
    "processor_config.json",
    "statistics.json",
    "model.safetensors.index.json",
)
_EAGLE_FILES = (
    "config.json",
    "preprocessor_config.json",
    "processor_config.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
    "chat_template.json",
)
_WRAPPER_PREFIXES = ("module.", "_orig_mod.")
_CHECKPOINT_REQUIRED = (
    "config.json",
    "processor_config.json",
    "statistics.json",
    "provenance.json",
    *tuple(f"eagle/{name}" for name in _EAGLE_FILES),
    "exactly one complete local weight representation",
)


@runtime_checkable
class _SafeTensorLoader(Protocol):
    """描述 safetensors 的最小本地加载调用。"""

    def __call__(self, filename: str, *, device: str) -> object:
        """读取单个本地 safetensors 文件。"""
        ...


@runtime_checkable
class _TensorConcatenator(Protocol):
    """描述 ``torch.cat`` 的最小延迟导入接口。"""

    def __call__(
        self,
        tensors: tuple[torch.Tensor, ...],
        *,
        dim: int,
    ) -> torch.Tensor:
        """沿指定轴拼接同一注意力投影组。"""
        ...


@dataclass(frozen=True, slots=True)
class _CheckpointSource:
    """绑定一次调用链中的根与可复用 verified asset receipt。"""

    root: Path
    resolved_asset: ResolvedModelAsset | None


class Gr00tN1d6CheckpointAdapter(ModelCheckpointAdapter):
    """只接受现有本地目录并拒绝歧义权重、碰撞和静默 reshape。"""

    def __init__(self, official_spec: ModelAssetSpec = GR00T_N1D6_ASSET_SPEC) -> None:
        """绑定必须用于官方目录验证的固定资产规范。"""

        if official_spec.family_key != "gr00t_n1d6":
            raise ValueError("official checkpoint spec must belong to gr00t_n1d6")
        self._official_spec = official_spec

    def inspect(
        self,
        path: str | Path | ResolvedModelAsset,
    ) -> CheckpointCompatibilityReport:
        """先验证官方资产,再发现配置和唯一权重表示。"""

        return self._inspect_source(self._checkpoint_source(path))

    def _inspect_source(self, source: _CheckpointSource) -> CheckpointCompatibilityReport:
        """复用同一 verified receipt 执行不读取 tensor 的布局检查。"""

        root = source.root
        official_asset = source.resolved_asset is not None
        issues: list[CompatibilityIssue] = []
        config_path = root / "config.json"
        processor_paths = tuple(root / name for name in _PROCESSOR_FILES)
        eagle_root = root / "eagle"
        if official_asset:
            missing = [
                str(root / name) for name in _OFFICIAL_ASSET_FILES if not (root / name).is_file()
            ]
        else:
            missing = [str(config_path)] if not config_path.is_file() else []
            missing.extend(str(item) for item in processor_paths if not item.is_file())
            missing.extend(
                str(eagle_root / name) for name in _EAGLE_FILES if not (eagle_root / name).is_file()
            )
        try:
            formats = self._discover_weight_formats(root)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LocalModelAssetError(
                "checkpoint_path",
                root,
                _CHECKPOINT_REQUIRED,
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc
        if len(formats) != 1:
            issues.append(
                CompatibilityIssue(
                    code="ambiguous_weight_format",
                    message="checkpoint must contain exactly one complete weight representation",
                )
            )
            weight_format = None
            weight_files: tuple[Path, ...] = ()
        else:
            weight_format, weight_files = next(iter(formats.items()))
        if missing:
            issues.append(
                CompatibilityIssue(
                    code="missing_local_asset",
                    message="checkpoint layout lacks required local files",
                )
            )
        provenance = root / (".autovla-asset.json" if official_asset else "provenance.json")
        if not provenance.is_file():
            issues.append(
                CompatibilityIssue(
                    code="missing_provenance",
                    message="checkpoint lacks provenance.json",
                )
            )
        return CheckpointCompatibilityReport(
            root=str(root),
            weight_format=weight_format,
            weight_files=tuple(str(item) for item in weight_files),
            required_files=(
                _OFFICIAL_ASSET_FILES
                if official_asset
                else (
                    "config.json",
                    *_PROCESSOR_FILES,
                    *(f"eagle/{name}" for name in _EAGLE_FILES),
                    "provenance.json",
                )
            ),
            missing_files=tuple(missing),
            config_file=str(config_path) if config_path.is_file() else None,
            processor_files=tuple(str(item) for item in processor_paths if item.is_file()),
            provenance_file=str(provenance) if provenance.is_file() else None,
            compatible=not issues,
            issues=tuple(issues),
        )

    def inspect_upstream_layout(
        self,
        path: str | Path | ResolvedModelAsset,
    ) -> UpstreamCheckpointLayout:
        """先验证官方资产,再解析 shard index 与真实键分区计数。"""

        root = self._checkpoint_source(path).root
        index = root / "model.safetensors.index.json"
        raw = json.loads(index.read_text(encoding="utf-8"))
        payload = _string_object_mapping(raw, name="safetensors index")
        weight_map = _string_object_mapping(payload.get("weight_map"), name="weight_map")
        shards: set[str] = set()
        for filename in weight_map.values():
            if not isinstance(filename, str) or not _SAFE_SHARD_BASENAME.fullmatch(filename):
                raise ValueError("safetensors shard name must be a contained basename")
            shards.add(filename)
        keys = tuple(weight_map)
        return UpstreamCheckpointLayout(
            index_file=str(index),
            shard_files=tuple(sorted(shards)),
            key_count=len(keys),
            backbone_key_count=sum(key.startswith("backbone.") for key in keys),
            action_head_key_count=sum(key.startswith("action_head.") for key in keys),
        )

    def parse_official_metadata(
        self,
        path: str | Path | ResolvedModelAsset,
        *,
        eagle_asset_path: str | Path,
    ) -> Gr00tN1d6Config:
        """解析官方 JSON;有完成清单时必须先验证,不加载 tensor。"""

        if isinstance(path, ResolvedModelAsset):
            source = self._checkpoint_source(path, field="model_asset_path")
        else:
            root = _local_directory(path, field="model_asset_path")
            source = (
                self._checkpoint_source(root, field="model_asset_path")
                if (root / ".autovla-asset.json").exists()
                else _CheckpointSource(root=root, resolved_asset=None)
            )
        return self._parse_official_metadata_source(source, eagle_asset_path=eagle_asset_path)

    def _parse_official_metadata_source(
        self,
        source: _CheckpointSource,
        *,
        eagle_asset_path: str | Path,
    ) -> Gr00tN1d6Config:
        """从已选择根解析官方 metadata 并保留 verified receipt。"""

        root = source.root
        payload = _string_object_mapping(
            json.loads((root / "config.json").read_text(encoding="utf-8")),
            name="official config.json",
        )
        _validate_official_config(payload)
        del eagle_asset_path
        return Gr00tN1d6Config(
            embodiment_ids=_load_embodiment_ids(root / "embodiment_id.json"),
            statistics=_load_official_statistics(
                root / "statistics.json", root / "processor_config.json"
            ),
            use_relative_actions=True,
            formalize_language=True,
        )

    def _checkpoint_source(
        self,
        path: str | Path | ResolvedModelAsset,
        *,
        field: str = "checkpoint_path",
    ) -> _CheckpointSource:
        """验证官方 manifest/spec,或收窄到不会伪装官方资产的 legacy 根。"""

        if isinstance(path, ResolvedModelAsset):
            root = path.root
            store = self._store_for_official_root(root, field=field)
            verified = store.validate_resolved(path, self._official_spec)
            return _CheckpointSource(root=verified.root, resolved_asset=verified)
        root = _local_directory(path, field=field)
        manifest = root / ".autovla-asset.json"
        if manifest.exists() or manifest.is_symlink():
            store = self._store_for_official_root(root, field=field)
            verified = store.verify(self._official_spec)
            if verified.root != root:
                raise LocalModelAssetError(
                    field,
                    root,
                    ("contained key/revision asset layout",),
                )
            return _CheckpointSource(root=root, resolved_asset=verified)
        if _looks_like_unmanifested_official_asset(root):
            raise LocalModelAssetError(
                field,
                root,
                (".autovla-asset.json",),
                detail=(
                    "official GR00T files cannot use the legacy migration path or bypass "
                    "license, containment, size, and SHA256 verification"
                ),
            )
        return _CheckpointSource(root=root, resolved_asset=None)

    def _store_for_official_root(self, root: Path, *, field: str) -> ModelAssetStore:
        """要求官方根严格采用 store/key/revision 布局。"""

        if root.name != self._official_spec.revision or root.parent.name != self._official_spec.key:
            raise LocalModelAssetError(
                field,
                root,
                (f"{self._official_spec.key}/{self._official_spec.revision}",),
                detail="official asset root does not match the immutable store layout",
            )
        try:
            store_root = root.parents[1]
        except IndexError as exc:
            raise LocalModelAssetError(
                field,
                root,
                ("contained model asset store root",),
            ) from exc
        return ModelAssetStore(store_root)

    def _discover_weight_formats(self, root: Path) -> dict[str, tuple[Path, ...]]:
        """返回完整且互斥的本地权重表示。"""
        formats: dict[str, tuple[Path, ...]] = {}
        single = root / "model.safetensors"
        if single.is_file():
            formats["safetensors"] = (single,)
        index = root / "model.safetensors.index.json"
        if index.is_file():
            raw_payload: object = json.loads(index.read_text(encoding="utf-8"))
            payload = _string_object_mapping(raw_payload, name="safetensors index")
            weight_map = _object_mapping(payload.get("weight_map"))
            if weight_map is None or not weight_map:
                raise ValueError("safetensors index must contain non-empty weight_map")
            shard_names: set[str] = set()
            for name in weight_map.values():
                if not isinstance(name, str):
                    raise ValueError("safetensors index shard names must be strings")
                if not _SAFE_SHARD_BASENAME.fullmatch(name):
                    raise ValueError("safetensors shard names must be contained basenames")
                shard_names.add(name)
            shards = tuple(sorted(root / name for name in shard_names))
            if not all(shard.is_file() and not shard.is_symlink() for shard in shards):
                raise FileNotFoundError("safetensors index references a missing local shard")
            formats["sharded_safetensors"] = shards
        return formats

    def convert_state_dict(
        self,
        state_dict: Mapping[str, torch.Tensor],
    ) -> Mapping[str, torch.Tensor]:
        """显式转换官方模块命名,并按 block 布局组合 Q/K/V。"""
        validated = _tensor_mapping(state_dict, name="convert_state_dict input")
        converted: dict[str, torch.Tensor] = {}
        attention_groups: dict[tuple[str, int, str], dict[str, torch.Tensor]] = {}
        for source_key, tensor in validated.items():
            key = source_key
            changed = True
            while changed:
                changed = False
                for rule in CHECKPOINT_KEY_RULES[:2]:
                    if key.startswith(rule.source_prefix):
                        key = rule.target_prefix + key[len(rule.source_prefix) :]
                        changed = True
            match = _OFFICIAL_ATTENTION_QKV.fullmatch(key)
            if match is not None:
                group_key = (
                    match.group(1),
                    int(match.group("block")),
                    match.group("parameter"),
                )
                projection = match.group("projection")
                group = attention_groups.setdefault(group_key, {})
                if projection in group:
                    raise ValueError(f"duplicate official attention projection: {key!r}")
                group[projection] = tensor
                continue
            _insert_converted(converted, _map_official_family_key(key), tensor)
        for (prefix, block, parameter), projections in sorted(attention_groups.items()):
            missing = tuple(name for name in "qkv" if name not in projections)
            if missing:
                raise ValueError(
                    "official attention projection group is incomplete: "
                    f"prefix={prefix!r}, parameter={parameter!r}, missing={missing}"
                )
            ordered = tuple(projections[name] for name in "qkv")
            if parameter == "bias" or block % 2 == 1:
                target = f"{prefix}.in_proj_{parameter}"
                _insert_converted(converted, target, _concatenate_tensors(ordered))
                continue
            for name, tensor in zip("qkv", ordered, strict=True):
                _insert_converted(converted, f"{prefix}.{name}_proj_weight", tensor)
        return converted

    def parameter_layout(self, model: torch.nn.Module) -> AutoVLAParameterLayout:
        """读取模型 state_dict 形状布局,不克隆参数数据。"""

        return AutoVLAParameterLayout(
            shapes={name: tuple(tensor.shape) for name, tensor in model.state_dict().items()}
        )

    def load_local(
        self,
        model: torch.nn.Module,
        path: str | Path | ResolvedModelAsset,
        *,
        strictness: str = "strict",
        device: torch.device | str = "cpu",
        dtype: torch.dtype | None = None,
        policy: CheckpointLoadPolicy | None = None,
    ) -> CheckpointLoadReport:
        """安全加载本地张量并在写入前完成键/形状审计。"""
        if policy is not None:
            strictness = (
                "inspect_only"
                if policy.inspect_only
                else ("strict" if policy.strict else "allow_known_optional")
            )
        if strictness not in {"strict", "allow_known_optional", "diagnostic", "inspect_only"}:
            raise ValueError(
                "strictness must be strict, allow_known_optional, diagnostic, or inspect_only"
            )
        checkpoint_source = self._checkpoint_source(path)
        compatibility = self._inspect_source(checkpoint_source)
        if not compatibility.compatible:
            raise LocalModelAssetError(
                "checkpoint_path",
                compatibility.root,
                tuple(compatibility.missing_files) or _CHECKPOINT_REQUIRED,
                detail="checkpoint layout is incomplete or weight representation is ambiguous",
            )
        expected = model.state_dict()
        seen: set[str] = set()
        unexpected: list[str] = []
        shape_mismatches: list[str] = []
        mapped: list[str] = []
        for shard in self._iter_state_dicts(compatibility, device=device):
            converted = self.convert_state_dict(shard)
            overlap = seen & set(converted)
            if overlap:
                raise ValueError(f"duplicate keys across checkpoint shards: {sorted(overlap)}")
            seen.update(converted)
            for key, tensor in converted.items():
                if key not in expected:
                    unexpected.append(key)
                elif expected[key].shape != tensor.shape:
                    shape_mismatches.append(key)
                else:
                    mapped.append(key)
            # packed Q/K/V 是临时张量,每个 shard 审计后立即释放引用。
            del converted
        missing = sorted(set(expected) - seen)
        unexpected.sort()
        shape_mismatches.sort()
        known_optional = {
            "action_head.mask_token",
            *(policy.allow_known_optional if policy is not None else ()),
        }
        fatal_missing = [key for key in missing if key not in known_optional]
        if strictness == "strict":
            fatal_missing = missing
        fatal = bool(fatal_missing or unexpected or shape_mismatches)
        inspect_only = strictness in {"diagnostic", "inspect_only"}
        if fatal and not inspect_only:
            raise ValueError(
                "checkpoint mapping failed: "
                f"missing={fatal_missing}, unexpected={unexpected}, shapes={shape_mismatches}"
            )
        if not inspect_only:
            mismatch_set = set(shape_mismatches)
            for shard in self._iter_state_dicts(compatibility, device=device):
                converted = self.convert_state_dict(shard)
                loadable: dict[str, torch.Tensor] = {}
                for key, tensor in converted.items():
                    if key not in expected or key in mismatch_set:
                        continue
                    if dtype is not None and tensor.is_floating_point():
                        tensor = tensor.to(dtype=dtype)
                    loadable[key] = tensor.to(device=device)
                model.load_state_dict(loadable, strict=False)
                del converted, loadable
        return CheckpointLoadReport(
            compatibility=compatibility,
            mapped_keys=tuple(sorted(mapped)),
            missing_keys=tuple(missing),
            unexpected_keys=tuple(unexpected),
            shape_mismatches=tuple(shape_mismatches),
            strictness=strictness,
            provenance=self.provenance_manifest(
                compatibility,
                resolved_asset=checkpoint_source.resolved_asset,
            ),
        )

    def _iter_state_dicts(
        self,
        report: CheckpointCompatibilityReport,
        *,
        device: torch.device | str,
    ) -> Iterator[Mapping[str, torch.Tensor]]:
        """逐 shard 读取 safetensors,安全边界等价于 ``weights_only=True``。"""
        if report.weight_format in {"safetensors", "sharded_safetensors"}:
            if importlib.util.find_spec("safetensors") is None:
                raise OptionalDependencyError(
                    "local safetensors checkpoint requires the 'model-gr00t-n1d6' extra"
                )
            module: object = importlib.import_module("safetensors.torch")
            loader: object = getattr(module, "load_file", None)
            if not isinstance(loader, _SafeTensorLoader):
                raise TypeError("safetensors.torch.load_file must be callable")

            for filename in report.weight_files:
                raw_shard = loader(filename, device=str(device))
                yield _tensor_mapping(raw_shard, name=filename)
            return
        raise ValueError("checkpoint report must select local safetensors weights")

    def load_family_config(
        self,
        path: str | Path | ResolvedModelAsset,
        *,
        eagle_asset_path: str | Path | None = None,
    ) -> Gr00tN1d6Config:
        """从静态 JSON 重建 AutoVLA 配置,不执行 checkpoint Python。"""
        source = self._checkpoint_source(path)
        root = source.root
        try:
            report = self._inspect_source(source)
            if not report.compatible:
                missing = tuple(report.missing_files) or _CHECKPOINT_REQUIRED
                raise LocalModelAssetError("checkpoint_path", root, missing)
            raw_payload: object = json.loads((root / "config.json").read_text(encoding="utf-8"))
            payload = _string_object_mapping(raw_payload, name="family config")
            embodiment_path = root / "embodiment_id.json"
            embodiment_ids = (
                _load_embodiment_ids(embodiment_path) if embodiment_path.is_file() else None
            )
            if source.resolved_asset is not None:
                if eagle_asset_path is None:
                    raise LocalModelAssetError(
                        "eagle_asset_path",
                        None,
                        ("explicit licensed local nvidia/Eagle-Block2A-2B-v2 directory",),
                        detail=(
                            "Eagle anonymous metadata is HTTP 401; revision and license are "
                            "unresolved, so AutoVLA cannot register or fetch it"
                        ),
                    )
                return self._parse_official_metadata_source(
                    source,
                    eagle_asset_path=eagle_asset_path,
                )
            return Gr00tN1d6Config(
                architecture_variant=cast(
                    str, payload.get("architecture_variant", "official_n1d6")
                ),
                statistics=_load_statistics(root / "statistics.json"),
                embodiment_ids={} if embodiment_ids is None else embodiment_ids,
            )
        except LocalModelAssetError:
            raise
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LocalModelAssetError(
                "checkpoint_path",
                root,
                _CHECKPOINT_REQUIRED,
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc

    def provenance_manifest(
        self,
        report: CheckpointCompatibilityReport,
        *,
        resolved_asset: ResolvedModelAsset | None = None,
    ) -> Mapping[str, object]:
        """优先复用 verified manifest 摘要,legacy 权重只执行一次完整摘要读取。"""

        weight_names = tuple(Path(filename).name for filename in report.weight_files)
        if resolved_asset is None:
            weight_hashes = {
                Path(filename).name: _sha256(Path(filename)) for filename in report.weight_files
            }
            integrity_source = "legacy_local_integrity_read"
        else:
            manifest_hashes = {item.path: item.sha256 for item in resolved_asset.manifest.files}
            missing = tuple(name for name in weight_names if name not in manifest_hashes)
            if missing:
                raise ValueError(
                    f"verified asset manifest lacks checkpoint weight records: {missing}"
                )
            weight_hashes = {name: manifest_hashes[name] for name in weight_names}
            integrity_source = "verified_model_asset_manifest"
        return {
            "schema_version": "autovla.gr00t_n1d6_checkpoint_provenance.v1",
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_pin": UPSTREAM_PIN,
            "source_license": SOURCE_LICENSE,
            "checkpoint_root": report.root,
            "weight_format": report.weight_format,
            "weight_files": weight_hashes,
            "integrity_source": integrity_source,
            "key_rules": {
                "strip_prefixes": _WRAPPER_PREFIXES,
                "embodiment_container": (
                    "action_head.{state,action}_{encoder,decoder} -> action_head.conditioner.*"
                ),
            },
            "local_files_only": True,
        }


def _local_directory(path: str | Path, *, field: str = "checkpoint_path") -> Path:
    """解析现有本地目录并显式拒绝 URL/repository ID。"""
    text = str(path)
    if "://" in text:
        raise LocalModelAssetError(field, path, _CHECKPOINT_REQUIRED, detail="URL is forbidden")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise LocalModelAssetError(
            field,
            candidate,
            _CHECKPOINT_REQUIRED,
            detail="path must be absolute",
        )
    resolved = candidate.resolve(strict=False)
    if not resolved.is_dir():
        raise LocalModelAssetError(
            field,
            resolved,
            _CHECKPOINT_REQUIRED,
            detail="directory does not exist",
        )
    return resolved


def _looks_like_unmanifested_official_asset(root: Path) -> bool:
    """识别不能降级到 legacy migration 路径的官方 GR00T 文件集合。"""

    if (root / "embodiment_id.json").exists():
        return True
    config = root / "config.json"
    if not config.is_file():
        return False
    try:
        payload: object = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    mapping = _object_mapping(payload)
    return mapping is not None and mapping.get("model_name") == "nvidia/Eagle-Block2A-2B-v2"


def _map_family_key(key: str) -> str:
    """把 upstream 分散 projector 键映射到本地 conditioner 容器。"""
    for rule in CHECKPOINT_KEY_RULES[2:]:
        if key.startswith(rule.source_prefix):
            return rule.target_prefix + key[len(rule.source_prefix) :]
    return key


def _map_official_family_key(key: str) -> str:
    """映射官方 timestep、attention 输出和 FFN 容器名。"""

    key = _map_family_key(key)
    replacements = (
        (
            "action_head.model.timestep_encoder.timestep_embedder.linear_1.",
            "action_head.model.time_encoder.linear1.",
        ),
        (
            "action_head.model.timestep_encoder.timestep_embedder.linear_2.",
            "action_head.model.time_encoder.linear2.",
        ),
        (".attn1.to_out.0.", ".attn1.out_proj."),
        (".ff.net.0.proj.", ".ff.proj_in."),
        (".ff.net.2.", ".ff.proj_out."),
    )
    for source, target in replacements:
        if source in key:
            return key.replace(source, target, 1)
    return key


def _insert_converted(
    converted: dict[str, torch.Tensor],
    key: str,
    tensor: torch.Tensor,
) -> None:
    """插入单个转换结果并拒绝来源碰撞。"""

    if key in converted:
        raise ValueError(f"checkpoint key collision after mapping: {key!r}")
    converted[key] = tensor


def _concatenate_tensors(tensors: tuple[torch.Tensor, ...]) -> torch.Tensor:
    """延迟调用 torch.cat,避免 metadata-only 导入强依赖 torch。"""

    module: object = importlib.import_module("torch")
    concatenator: object = getattr(module, "cat", None)
    if not isinstance(concatenator, _TensorConcatenator):
        raise TypeError("torch.cat must be callable")
    return concatenator(tensors, dim=0)


def _sha256(path: Path) -> str:
    """流式计算本地文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_statistics(path: Path) -> Mapping[str, EmbodimentStatistics]:
    """读取显式 AutoVLA per-embodiment 状态/动作统计结构。"""
    raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
    payload = _string_object_mapping(raw_payload, name="statistics.json")
    raw_embodiments = _object_mapping(payload.get("embodiments"))
    if raw_embodiments is None or not raw_embodiments:
        raise ValueError("statistics.json must contain non-empty embodiments")
    result: dict[str, EmbodimentStatistics] = {}
    for raw_name, raw_record in raw_embodiments.items():
        if not isinstance(raw_name, str):
            raise ValueError("statistics embodiment names must be strings")
        name = raw_name
        record = _string_object_mapping(raw_record, name=f"statistics for {name!r}")
        state = _load_feature_statistics(record.get("state"), name=f"{name}.state")
        action = _load_feature_statistics(record.get("action"), name=f"{name}.action")
        raw_policies = record.get("relative_action_policies", [])
        if not _is_object_list(raw_policies):
            raise ValueError(f"{name}.relative_action_policies must be a list")
        policies = tuple(
            _load_relative_action_policy(raw, name=f"{name}.relative_action_policies[{index}]")
            for index, raw in enumerate(raw_policies)
        )
        result[name] = EmbodimentStatistics(
            state=state,
            action=action,
            relative_action_policies=policies,
        )
    return result


def _validate_official_config(payload: Mapping[str, object]) -> None:
    """核对已验证本地 metadata 的官方 50/128/128 envelope。"""

    expected = {
        "action_horizon": 50,
        "max_state_dim": 128,
        "max_action_dim": 128,
        "max_num_embodiments": 32,
        "model_name": "nvidia/Eagle-Block2A-2B-v2",
    }
    mismatches = {
        key: (payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if mismatches:
        raise ValueError(f"official GR00T config mismatch: {mismatches}")


def _load_official_statistics(
    statistics_path: Path,
    processor_path: Path,
) -> Mapping[str, EmbodimentStatistics]:
    """按 processor modality 顺序映射官方 top-level embodiment 统计。"""

    statistics = _string_object_mapping(
        json.loads(statistics_path.read_text(encoding="utf-8")),
        name="official statistics.json",
    )
    processor = _string_object_mapping(
        json.loads(processor_path.read_text(encoding="utf-8")),
        name="official processor_config.json",
    )
    kwargs = _string_object_mapping(processor.get("processor_kwargs"), name="processor_kwargs")
    exact_flags = {
        "max_action_horizon": 50,
        "max_state_dim": 128,
        "max_action_dim": 128,
        "use_percentiles": False,
        "clip_outliers": True,
        "use_relative_action": True,
    }
    if any(kwargs.get(key) != value for key, value in exact_flags.items()):
        raise ValueError("official processor dimensions/normalization flags do not match pin")
    modalities = _string_object_mapping(kwargs.get("modality_configs"), name="modality_configs")
    result: dict[str, EmbodimentStatistics] = {}
    for embodiment, raw_record in statistics.items():
        record = _string_object_mapping(raw_record, name=f"statistics.{embodiment}")
        raw_modality = modalities.get(embodiment)
        if raw_modality is None:
            raise ValueError(f"processor modality config missing for {embodiment!r}")
        modality = _string_object_mapping(raw_modality, name=f"modality_configs.{embodiment}")
        state_order = _modality_order(modality, "state", embodiment)
        action_order = _modality_order(modality, "action", embodiment)
        state_config = _string_object_mapping(
            modality.get("state"), name=f"modality_configs.{embodiment}.state"
        )
        action_config = _string_object_mapping(
            modality.get("action"), name=f"modality_configs.{embodiment}.action"
        )
        state_mean_std = (
            _optional_string_tuple(
                state_config.get("mean_std_embedding_keys"),
                name=f"{embodiment}.state.mean_std_embedding_keys",
            )
            if "mean_std_embedding_keys" in state_config
            else state_order
        )
        action_mean_std = (
            _optional_string_tuple(
                action_config.get("mean_std_embedding_keys"),
                name=f"{embodiment}.action.mean_std_embedding_keys",
            )
            if "mean_std_embedding_keys" in action_config
            else action_order
        )
        sin_cos_keys = (
            _optional_string_tuple(
                state_config.get("sin_cos_embedding_keys"),
                name=f"{embodiment}.state.sin_cos_embedding_keys",
            )
            if kwargs.get("apply_sincos_state_encoding", False) is True
            else ()
        )
        state_mean, state_std, sin_cos_slices = _flatten_official_normalization(
            record,
            "state",
            state_order,
            mean_std_modalities=state_mean_std,
            sin_cos_modalities=sin_cos_keys,
        )
        action_mean, action_std, _ = _flatten_official_normalization(
            record,
            "action",
            action_order,
            mean_std_modalities=action_mean_std,
            sin_cos_modalities=(),
        )
        state = _r3_mean_std(state_mean, state_std, order=state_order)
        action = _r3_mean_std(action_mean, action_std, order=action_order)
        relative_record = _object_mapping(record.get("relative_action"))
        relative_order = (
            tuple(name for name in action_order if name in relative_record)
            if relative_record
            else ()
        )
        relative = None
        if relative_order:
            relative_mean = _matrix_official_stat(record, relative_order, "mean")
            relative_std = _matrix_official_stat(record, relative_order, "std")
            relative = PerHorizonFeatureStatistics(
                method="mean_std",
                layout=TensorLayout.time_feature(len(relative_mean), len(relative_mean[0])),
                mean=np.asarray(relative_mean, dtype=np.float32),
                std=np.asarray(relative_std, dtype=np.float32),
                constant_feature_policy=ConstantFeaturePolicy.IDENTITY,
                alignment=AlignmentPolicy(AlignmentMode.EXACT),
            )
        source_fingerprint = hashlib.sha256(
            statistics_path.read_bytes() + b"\0" + processor_path.read_bytes()
        ).hexdigest()
        camera_order = _optional_modality_order(modality, "video", embodiment)
        policies = _official_relative_action_policies(
            action_config,
            record=record,
            state_order=state_order,
            action_order=action_order,
        )
        result[embodiment] = EmbodimentStatistics(
            state=state,
            action=action,
            relative_action=relative,
            relative_action_policies=policies,
            state_modality_order=state_order,
            action_modality_order=action_order,
            relative_action_modality_order=relative_order,
            state_clip=True,
            action_clip=True,
            relative_action_clip=True,
            source_fingerprint=source_fingerprint,
            camera_order=camera_order,
            sin_cos_state_slices=sin_cos_slices,
            mean_std_state_modalities=state_mean_std,
            mean_std_action_modalities=action_mean_std,
        )
    return result


def _optional_string_tuple(raw: object, *, name: str) -> tuple[str, ...]:
    """读取可选且唯一的官方字符串列表。"""

    if raw is None:
        return ()
    if not _is_object_list(raw) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"{name} must be a string list or null")
    result = tuple(cast(str, item) for item in raw)
    if len(result) != len(set(result)):
        raise ValueError(f"{name} must contain unique values")
    return result


def _optional_modality_order(
    modalities: Mapping[str, object], group: str, embodiment: str
) -> tuple[str, ...]:
    """读取可选模态顺序;旧迁移 fixture 缺失时保留显式默认。"""

    if modalities.get(group) is None:
        return ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")
    return _modality_order(modalities, group, embodiment)


def _flatten_official_normalization(
    record: Mapping[str, object],
    group: str,
    order: tuple[str, ...],
    *,
    mean_std_modalities: tuple[str, ...],
    sin_cos_modalities: tuple[str, ...],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[int, int], ...]]:
    """把 per-modality 策略等价投影为一个可逆 mean/std 规范阶段。"""

    group_record = _string_object_mapping(record.get(group), name=f"statistics.{group}")
    centers: list[float] = []
    scales: list[float] = []
    sin_cos_slices: list[tuple[int, int]] = []
    raw_cursor = 0
    for modality in order:
        feature = _string_object_mapping(
            group_record.get(modality), name=f"statistics.{group}.{modality}"
        )
        mean = _float_tuple(feature.get("mean"), name=f"{group}.{modality}.mean")
        dimension = len(mean)
        if modality in sin_cos_modalities:
            sin_cos_slices.append((raw_cursor, raw_cursor + dimension))
            centers.extend(0.0 for _ in range(2 * dimension))
            scales.extend(1.0 for _ in range(2 * dimension))
        elif modality in mean_std_modalities:
            centers.extend(mean)
            scales.extend(_float_tuple(feature.get("std"), name=f"{group}.{modality}.std"))
        else:
            minimum = _float_tuple(feature.get("min"), name=f"{group}.{modality}.min")
            maximum = _float_tuple(feature.get("max"), name=f"{group}.{modality}.max")
            if len(minimum) != dimension or len(maximum) != dimension:
                raise ValueError("official min/max dimensions must match modality dimension")
            centers.extend((low + high) / 2.0 for low, high in zip(minimum, maximum, strict=True))
            scales.extend((high - low) / 2.0 for low, high in zip(minimum, maximum, strict=True))
        raw_cursor += dimension
    return tuple(centers), tuple(scales), tuple(sin_cos_slices)


def _official_relative_action_policies(
    action_config: Mapping[str, object],
    *,
    record: Mapping[str, object],
    state_order: tuple[str, ...],
    action_order: tuple[str, ...],
) -> tuple[RelativeActionPolicy, ...]:
    """把官方 action_config 投影为共享 joint/SE3 变换所需切片。"""

    raw_configs = action_config.get("action_configs")
    if raw_configs is None:
        return ()
    if not _is_object_list(raw_configs) or len(raw_configs) != len(action_order):
        raise ValueError("official action_configs must align with action modality order")
    state_group = _string_object_mapping(record.get("state"), name="statistics.state")
    action_group = _string_object_mapping(record.get("action"), name="statistics.action")
    state_offsets: dict[str, tuple[int, int]] = {}
    cursor = 0
    for modality in state_order:
        feature = _string_object_mapping(state_group.get(modality), name=f"state.{modality}")
        dimension = len(_float_tuple(feature.get("mean"), name=f"state.{modality}.mean"))
        state_offsets[modality] = (cursor, dimension)
        cursor += dimension
    policies: list[RelativeActionPolicy] = []
    action_cursor = 0
    for modality, raw_config in zip(action_order, raw_configs, strict=True):
        feature = _string_object_mapping(action_group.get(modality), name=f"action.{modality}")
        dimension = len(_float_tuple(feature.get("mean"), name=f"action.{modality}.mean"))
        config = _string_object_mapping(raw_config, name=f"action_config.{modality}")
        representation = str(config.get("rep", "absolute")).lower()
        if representation == "relative":
            state_key = config.get("state_key") or modality
            if not isinstance(state_key, str) or state_key not in state_offsets:
                raise ValueError("relative action state_key must identify a state modality")
            state_start, state_dimension = state_offsets[state_key]
            if state_dimension != dimension:
                raise ValueError("relative action and reference-state dimensions must match")
            action_type = str(config.get("type", "non_eef")).lower()
            raw_format = str(config.get("format", "default")).lower().replace("+", "_")
            kind = (
                RelativeActionKind.END_EFFECTOR
                if action_type in {"eef", "actiontype.eef"}
                else RelativeActionKind.JOINT
            )
            eef_representation = None
            if kind is RelativeActionKind.END_EFFECTOR:
                if raw_format not in {"xyz_rotvec", "actionformat.xyz_rotvec"}:
                    raise ValueError("official EEF action format lacks a canonical SE3 mapping")
                eef_representation = EndEffectorRepresentation.XYZ_ROTVEC
            policies.append(
                RelativeActionPolicy(
                    kind=kind,
                    action_start=action_cursor,
                    state_start=state_start,
                    dimension=dimension,
                    representation=eef_representation,
                )
            )
        action_cursor += dimension
    return tuple(policies)


def _modality_order(
    modalities: Mapping[str, object], group: str, embodiment: str
) -> tuple[str, ...]:
    """读取官方 flatten 顺序,不使用 JSON object 自然顺序替代。"""

    config = _string_object_mapping(
        modalities.get(group), name=f"modality_configs.{embodiment}.{group}"
    )
    raw = config.get("modality_keys")
    if not _is_object_list(raw) or not raw or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"official {embodiment}.{group} modality_keys must be strings")
    return tuple(cast(str, item) for item in raw)


def _flatten_official_stat(
    record: Mapping[str, object],
    group: str,
    order: tuple[str, ...],
    statistic: str,
) -> tuple[float, ...]:
    """按 modality 顺序拼接一维 state/action 统计。"""

    group_record = _string_object_mapping(record.get(group), name=f"statistics.{group}")
    values: list[float] = []
    for modality in order:
        feature = _string_object_mapping(
            group_record.get(modality), name=f"statistics.{group}.{modality}"
        )
        values.extend(_float_tuple(feature.get(statistic), name=f"{group}.{modality}.{statistic}"))
    return tuple(values)


def _matrix_official_stat(
    record: Mapping[str, object],
    order: tuple[str, ...],
    statistic: str,
) -> tuple[tuple[float, ...], ...]:
    """按 action modality 顺序逐 timestep 拼接 relative_action ``[T,D]``。"""

    group = _string_object_mapping(record.get("relative_action"), name="relative_action")
    matrices: list[tuple[tuple[float, ...], ...]] = []
    for modality in order:
        feature = _string_object_mapping(group.get(modality), name=f"relative_action.{modality}")
        raw_rows = feature.get(statistic)
        if not _is_object_list(raw_rows) or not raw_rows:
            raise ValueError(f"relative_action.{modality}.{statistic} must be [T,D]")
        rows = tuple(
            _float_tuple(row, name=f"relative_action.{modality}.{statistic}[{index}]")
            for index, row in enumerate(raw_rows)
        )
        matrices.append(rows)
    horizon = len(matrices[0])
    if any(len(matrix) != horizon for matrix in matrices):
        raise ValueError("relative_action modality statistics have inconsistent horizon")
    return tuple(
        tuple(value for matrix in matrices for value in matrix[timestep])
        for timestep in range(horizon)
    )


def _load_feature_statistics(raw: object, *, name: str) -> FeatureStatistics:
    """读取一个 offset/scale/clip 统计对象。"""
    payload = _string_object_mapping(raw, name=name)
    offset = _float_tuple(payload.get("offset"), name=f"{name}.offset")
    scale = _float_tuple(payload.get("scale"), name=f"{name}.scale")
    clip = payload.get("clip", True)
    if not isinstance(clip, bool):
        raise ValueError(f"{name}.clip must be bool")
    del clip
    return _r3_mean_std(offset, scale, order=(name,))


def _r3_mean_std(
    mean: tuple[float, ...],
    std: tuple[float, ...],
    *,
    order: tuple[str, ...],
) -> FeatureStatistics:
    """把官方有序向量转换为 R3 ``[D]`` 统计契约。"""

    names = tuple(
        f"{modality}:{index}"
        for modality in order
        for index in range(len(mean) if len(order) == 1 else 1)
    )
    if len(names) != len(mean):
        names = tuple(f"feature:{index}" for index in range(len(mean)))
    return FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.feature(len(mean)),
        mean=np.asarray(mean, dtype=np.float32),
        std=np.asarray(std, dtype=np.float32),
        names=names,
        constant_feature_policy=ConstantFeaturePolicy.IDENTITY,
        alignment=AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES),
    )


def _load_relative_action_policy(raw: object, *, name: str) -> RelativeActionPolicy:
    """读取一个严格类型化 joint/EEF 相对动作策略。"""
    payload = _string_object_mapping(raw, name=name)
    kind_value = payload.get("kind")
    representation_value = payload.get("representation")
    if not isinstance(kind_value, str):
        raise ValueError(f"{name}.kind must be a string")
    try:
        kind = RelativeActionKind(kind_value)
    except ValueError as exc:
        raise ValueError(f"{name}.kind is unsupported") from exc
    representation = None
    if representation_value is not None:
        if not isinstance(representation_value, str):
            raise ValueError(f"{name}.representation must be a string or null")
        try:
            representation = EndEffectorRepresentation(representation_value)
        except ValueError as exc:
            raise ValueError(f"{name}.representation is unsupported") from exc
    return RelativeActionPolicy(
        kind=kind,
        action_start=_strict_integer(payload.get("action_start"), name=f"{name}.action_start"),
        state_start=_strict_integer(payload.get("state_start"), name=f"{name}.state_start"),
        dimension=_strict_integer(payload.get("dimension"), name=f"{name}.dimension"),
        representation=representation,
    )


def _strict_integer(raw: object, *, name: str) -> int:
    """读取严格整数 JSON 值。"""
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"{name} must be an integer")
    return raw


def _float_tuple(raw: object, *, name: str) -> tuple[float, ...]:
    """读取有限数值 JSON 列表。"""
    if not _is_object_list(raw) or not raw:
        raise ValueError(f"{name} must be a non-empty numeric list")
    result: list[float] = []
    for value in raw:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{name} must contain only numbers")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"{name} must contain finite numbers")
        result.append(numeric)
    return tuple(result)


def _load_embodiment_ids(path: Path) -> Mapping[str, int]:
    """读取并校验可选 checkpoint embodiment ID 映射。"""
    raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
    payload = _string_object_mapping(raw_payload, name="embodiment_id.json")
    result: dict[str, int] = {}
    for name, value in payload.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("embodiment IDs must be integers")
        result[name] = value
    return result


def _object_mapping(raw: object) -> Mapping[object, object] | None:
    """把动态对象收窄为未知键值映射。"""
    if not _is_object_mapping(raw):
        return None
    return raw


def _string_object_mapping(raw: object, *, name: str) -> Mapping[str, object]:
    """校验动态映射的键均为字符串。"""
    mapping = _object_mapping(raw)
    if mapping is None:
        raise ValueError(f"{name} must contain a JSON object")
    result: dict[str, object] = {}
    for key, value in mapping.items():
        if not isinstance(key, str):
            raise ValueError(f"{name} keys must be strings")
        result[key] = value
    return result


def _tensor_mapping(raw: object, *, name: str) -> Mapping[str, torch.Tensor]:
    """校验第三方加载器返回字符串键 tensor 映射。"""
    torch = importlib.import_module("torch")
    mapping = _object_mapping(raw)
    if mapping is None:
        raise TypeError(f"checkpoint {name!r} must contain a tensor state dict")
    result: dict[str, torch.Tensor] = {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, torch.Tensor):
            raise TypeError(f"checkpoint {name!r} must contain a tensor state dict")
        result[key] = value
    return result


def _is_object_list(raw: object) -> TypeGuard[list[object]]:
    """收窄 JSON 列表并保留逐项运行时校验。"""
    return isinstance(raw, list)


def _is_object_mapping(raw: object) -> TypeGuard[Mapping[object, object]]:
    """收窄动态映射并固定未知键值为 object。"""
    return isinstance(raw, Mapping)


__all__ = [
    "CHECKPOINT_KEY_RULES",
    "AutoVLAParameterLayout",
    "CheckpointKeyRule",
    "CheckpointLoadPolicy",
    "Gr00tN1d6CheckpointAdapter",
    "UpstreamCheckpointLayout",
]
