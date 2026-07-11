"""GR00T N1.6.1 本地 checkpoint 发现、转换和加载。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import torch

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.components.relative_actions import (
    EndEffectorRepresentation,
    RelativeActionKind,
    RelativeActionPolicy,
)
from autovla.models.families.gr00t_n1d6.config import (
    EmbodimentStatistics,
    FeatureStatistics,
    Gr00tN1d6Config,
)
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.models.outputs import (
    CheckpointCompatibilityReport,
    CheckpointLoadReport,
    CompatibilityIssue,
)

UPSTREAM_REPOSITORY = "https://github.com/NVIDIA/Isaac-GR00T"
UPSTREAM_PIN = "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"
SOURCE_LICENSE = "NVIDIA License (n1.6.1-release root)"

_PROCESSOR_FILES = ("processor_config.json", "statistics.json")
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


class Gr00tN1d6CheckpointAdapter(ModelCheckpointAdapter):
    """只接受现有本地目录并拒绝歧义权重、碰撞和静默 reshape。"""

    def inspect(self, path: str | Path) -> CheckpointCompatibilityReport:
        """发现配置、processor、Eagle 资产和唯一权重表示。"""
        root = _local_directory(path)
        issues: list[CompatibilityIssue] = []
        config_path = root / "config.json"
        processor_paths = tuple(root / name for name in _PROCESSOR_FILES)
        eagle_root = root / "eagle"
        missing = [str(config_path)] if not config_path.is_file() else []
        missing.extend(str(item) for item in processor_paths if not item.is_file())
        missing.extend(
            str(eagle_root / name) for name in _EAGLE_FILES if not (eagle_root / name).is_file()
        )
        formats = self._discover_weight_formats(root)
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
        provenance = root / "provenance.json"
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
                "config.json",
                *_PROCESSOR_FILES,
                *(f"eagle/{name}" for name in _EAGLE_FILES),
                "provenance.json",
            ),
            missing_files=tuple(missing),
            config_file=str(config_path) if config_path.is_file() else None,
            processor_files=tuple(str(item) for item in processor_paths if item.is_file()),
            provenance_file=str(provenance) if provenance.is_file() else None,
            compatible=not issues,
            issues=tuple(issues),
        )

    def _discover_weight_formats(self, root: Path) -> dict[str, tuple[Path, ...]]:
        """返回完整且互斥的本地权重表示。"""
        formats: dict[str, tuple[Path, ...]] = {}
        single = root / "model.safetensors"
        if single.is_file():
            formats["safetensors"] = (single,)
        index = root / "model.safetensors.index.json"
        if index.is_file():
            payload = json.loads(index.read_text(encoding="utf-8"))
            weight_map = payload.get("weight_map") if isinstance(payload, dict) else None
            if not isinstance(weight_map, dict) or not weight_map:
                raise ValueError("safetensors index must contain non-empty weight_map")
            shards = tuple(sorted({root / str(name) for name in weight_map.values()}))
            if not all(shard.is_file() for shard in shards):
                raise FileNotFoundError("safetensors index references a missing local shard")
            formats["sharded_safetensors"] = shards
        pytorch = tuple(
            path for path in (root / "pytorch_model.bin", root / "model.pt") if path.is_file()
        )
        if pytorch:
            if len(pytorch) != 1:
                raise ValueError("multiple PyTorch state-dict candidates are ambiguous")
            formats["pytorch_state_dict"] = pytorch
        return formats

    def convert_state_dict(
        self,
        state_dict: Mapping[str, torch.Tensor],
    ) -> Mapping[str, torch.Tensor]:
        """移除已知 wrapper 前缀并显式映射 embodiment 容器键。"""
        converted: dict[str, torch.Tensor] = {}
        for source_key, tensor in state_dict.items():
            if not isinstance(tensor, torch.Tensor):
                raise TypeError(f"checkpoint value for {source_key!r} is not a tensor")
            key = source_key
            changed = True
            while changed:
                changed = False
                for prefix in _WRAPPER_PREFIXES:
                    if key.startswith(prefix):
                        key = key[len(prefix) :]
                        changed = True
            key = _map_family_key(key)
            if key in converted:
                raise ValueError(f"checkpoint key collision after mapping: {key!r}")
            converted[key] = tensor
        return converted

    def load_local(
        self,
        model: torch.nn.Module,
        path: str | Path,
        *,
        strictness: str = "strict",
        device: torch.device | str = "cpu",
        dtype: torch.dtype | None = None,
    ) -> CheckpointLoadReport:
        """安全加载本地张量并在写入前完成键/形状审计。"""
        if strictness not in {"strict", "allow_known_optional", "diagnostic"}:
            raise ValueError("strictness must be strict, allow_known_optional, or diagnostic")
        compatibility = self.inspect(path)
        if not compatibility.compatible:
            raise ValueError("local checkpoint layout is incomplete or ambiguous")
        source = self._load_state_dict(compatibility, device=device)
        converted = dict(self.convert_state_dict(source))
        expected = model.state_dict()
        missing = sorted(set(expected) - set(converted))
        unexpected = sorted(set(converted) - set(expected))
        shape_mismatches = sorted(
            key
            for key in set(expected) & set(converted)
            if expected[key].shape != converted[key].shape
        )
        known_optional = {"action_head.mask_token"}
        fatal_missing = [key for key in missing if key not in known_optional]
        if strictness == "strict":
            fatal_missing = missing
        fatal = bool(fatal_missing or unexpected or shape_mismatches)
        if fatal and strictness != "diagnostic":
            raise ValueError(
                "checkpoint mapping failed: "
                f"missing={fatal_missing}, unexpected={unexpected}, shapes={shape_mismatches}"
            )
        loadable: dict[str, torch.Tensor] = {}
        for key, tensor in converted.items():
            if key not in expected or key in shape_mismatches:
                continue
            if dtype is not None and tensor.is_floating_point():
                tensor = tensor.to(dtype=dtype)
            loadable[key] = tensor.to(device=device)
        if strictness != "diagnostic":
            model.load_state_dict(loadable, strict=False)
        return CheckpointLoadReport(
            compatibility=compatibility,
            mapped_keys=tuple(sorted(loadable)),
            missing_keys=tuple(missing),
            unexpected_keys=tuple(unexpected),
            shape_mismatches=tuple(shape_mismatches),
            strictness=strictness,
            provenance=self.provenance_manifest(compatibility),
        )

    def _load_state_dict(
        self,
        report: CheckpointCompatibilityReport,
        *,
        device: torch.device | str,
    ) -> Mapping[str, torch.Tensor]:
        """按已审计格式读取 tensor-only 权重。"""
        if report.weight_format in {"safetensors", "sharded_safetensors"}:
            if importlib.util.find_spec("safetensors") is None:
                raise OptionalDependencyError(
                    "local safetensors checkpoint requires the 'model-gr00t-n1d6' extra"
                )
            from safetensors.torch import load_file

            merged: dict[str, torch.Tensor] = {}
            for filename in report.weight_files:
                shard = load_file(filename, device=str(device))
                overlap = set(merged) & set(shard)
                if overlap:
                    raise ValueError(f"duplicate keys across safetensors shards: {sorted(overlap)}")
                merged.update(shard)
            return merged
        if report.weight_format == "pytorch_state_dict":
            payload = torch.load(report.weight_files[0], map_location=device, weights_only=True)
            if isinstance(payload, dict) and isinstance(payload.get("state_dict"), dict):
                payload = payload["state_dict"]
            if not isinstance(payload, dict):
                raise TypeError("PyTorch checkpoint must contain a tensor state dict")
            return cast(Mapping[str, torch.Tensor], payload)
        raise ValueError("checkpoint report does not select a supported weight format")

    def load_family_config(self, path: str | Path) -> Gr00tN1d6Config:
        """从静态 JSON 重建 AutoVLA 配置,不执行 checkpoint Python。"""
        root = _local_directory(path)
        raw_payload: object = json.loads((root / "config.json").read_text(encoding="utf-8"))
        if not isinstance(raw_payload, dict):
            raise ValueError("family config must contain a JSON object")
        payload = cast(dict[str, object], raw_payload)
        embodiment_path = root / "embodiment_id.json"
        embodiment_ids = (
            _load_embodiment_ids(embodiment_path) if embodiment_path.is_file() else None
        )
        return Gr00tN1d6Config.from_mapping(
            payload,
            statistics=_load_statistics(root / "statistics.json"),
            embodiment_ids=embodiment_ids,
            eagle_asset_path=str(root / "eagle"),
            checkpoint_path=str(root),
        )

    def provenance_manifest(
        self,
        report: CheckpointCompatibilityReport,
    ) -> Mapping[str, object]:
        """生成包含来源 pin、许可和权重 SHA256 的内存 manifest。"""
        return {
            "schema_version": "autovla.gr00t_n1d6_checkpoint_provenance.v1",
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_pin": UPSTREAM_PIN,
            "source_license": SOURCE_LICENSE,
            "checkpoint_root": report.root,
            "weight_format": report.weight_format,
            "weight_files": {
                Path(filename).name: _sha256(Path(filename)) for filename in report.weight_files
            },
            "key_rules": {
                "strip_prefixes": _WRAPPER_PREFIXES,
                "embodiment_container": (
                    "action_head.{state,action}_{encoder,decoder} -> action_head.conditioner.*"
                ),
            },
            "local_files_only": True,
        }


def _local_directory(path: str | Path) -> Path:
    """解析现有本地目录并显式拒绝 URL/repository ID。"""
    text = str(path)
    if "://" in text:
        raise ValueError("checkpoint path must be local, not a URL")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("checkpoint path must be absolute")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("checkpoint path must be an existing local directory")
    return resolved


def _map_family_key(key: str) -> str:
    """把 upstream 分散 projector 键映射到本地 conditioner 容器。"""
    mappings = {
        "action_head.state_encoder.": "action_head.conditioner.state_encoder.",
        "action_head.action_encoder.": "action_head.conditioner.action_encoder.",
        "action_head.action_decoder.": "action_head.conditioner.action_decoder.",
    }
    for source, destination in mappings.items():
        if key.startswith(source):
            return destination + key[len(source) :]
    return key


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
    if not isinstance(raw_payload, dict):
        raise ValueError("statistics.json must contain a JSON object")
    payload = cast(dict[str, object], raw_payload)
    raw_embodiments = payload.get("embodiments")
    if not isinstance(raw_embodiments, dict) or not raw_embodiments:
        raise ValueError("statistics.json must contain non-empty embodiments")
    embodiments = cast(dict[str, object], raw_embodiments)
    result: dict[str, EmbodimentStatistics] = {}
    for name, raw_record in embodiments.items():
        if not isinstance(raw_record, dict):
            raise ValueError(f"statistics for {name!r} must be an object")
        record = cast(dict[str, object], raw_record)
        state = _load_feature_statistics(record.get("state"), name=f"{name}.state")
        action = _load_feature_statistics(record.get("action"), name=f"{name}.action")
        raw_policies = record.get("relative_action_policies", [])
        if not isinstance(raw_policies, list):
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


def _load_feature_statistics(raw: object, *, name: str) -> FeatureStatistics:
    """读取一个 offset/scale/clip 统计对象。"""
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    payload = cast(dict[str, object], raw)
    offset = _float_tuple(payload.get("offset"), name=f"{name}.offset")
    scale = _float_tuple(payload.get("scale"), name=f"{name}.scale")
    clip = payload.get("clip", True)
    if not isinstance(clip, bool):
        raise ValueError(f"{name}.clip must be bool")
    return FeatureStatistics(offset=offset, scale=scale, clip=clip)


def _load_relative_action_policy(raw: object, *, name: str) -> RelativeActionPolicy:
    """读取一个严格类型化 joint/EEF 相对动作策略。"""
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must be an object")
    payload = cast(dict[str, object], raw)
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
    if not isinstance(raw, list) or not raw:
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
    if not isinstance(raw_payload, dict):
        raise ValueError("embodiment_id.json must contain a JSON object")
    payload = cast(dict[str, object], raw_payload)
    result: dict[str, int] = {}
    for name, value in payload.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("embodiment IDs must be integers")
        result[name] = value
    return result


__all__ = ["Gr00tN1d6CheckpointAdapter"]
