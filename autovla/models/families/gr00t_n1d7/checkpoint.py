"""GR00T N1.7 本地 sharded-safetensors 检查与流式加载。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, TypeGuard, cast

if TYPE_CHECKING:
    import torch

from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.outputs import (
    CheckpointCompatibilityReport,
    CheckpointLoadReport,
)

_SAFE_SHARD = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.safetensors")
_SAFE_KEY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.]*")
_FORBIDDEN_SUFFIXES = (".bin", ".pt", ".pth", ".pkl", ".pickle")
_REQUIRED_METADATA = (
    "LICENSE",
    "config.json",
    "embodiment_id.json",
    "model.safetensors.index.json",
    "processor_config.json",
    "statistics.json",
)


class _TorchModule(Protocol):
    """描述严格加载所需的最小 Torch 模块表面。"""

    config: object

    def state_dict(self) -> Mapping[str, "torch.Tensor"]:
        """返回命名参数映射。"""
        ...

    def load_state_dict(self, state_dict: Mapping[str, "torch.Tensor"], *, strict: bool) -> object:
        """加载一个已校验 shard 的参数子集。"""
        ...


@dataclass(frozen=True, slots=True)
class _CheckpointMappingEvidence:
    """保存不读取 tensor 的索引与配置重建证据。"""

    root: Path
    config_fingerprint: str
    index_fingerprint: str
    key_mapping: Mapping[str, str]
    shard_files: tuple[str, ...]
    executable_ready: bool = False
    blockers: tuple[str, ...] = (
        "checkpoint_tensor_shapes_not_validated",
        "cuda_runtime_not_validated",
    )

    def __post_init__(self) -> None:
        """冻结映射且不把静态检查升级为运行证据。"""

        if self.executable_ready:
            raise ValueError("metadata inspection cannot claim executable readiness")
        object.__setattr__(self, "key_mapping", MappingProxyType(dict(self.key_mapping)))


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """把动态 JSON 对象收窄为未知键值映射。"""
    return isinstance(value, Mapping)


def _read_json(path: Path) -> Mapping[str, object]:
    """有界读取本地 JSON, 拒绝符号链接和超大 metadata。"""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required local metadata is missing or symlinked: {path.name}")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"local metadata is unexpectedly large: {path.name}")
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not _is_object_mapping(payload):
        raise ValueError(f"local metadata must be a string-keyed object: {path.name}")
    result: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"local metadata must be a string-keyed object: {path.name}")
        result[key] = value
    return result


class Gr00tN1d7CheckpointAdapter:
    """只接受本地 safetensors, 逐 shard 验证 shape 后加载。

    适配器不调用 ``torch.load``、pickle、网络或远端 Python。严格模式在任何
    missing/unexpected/shape mismatch 上失败, 诊断模式仅返回完整分类。
    """

    adapter_identity = "gr00t_n1d7:safetensors_strict_streaming:v2"

    def inspect(
        self,
        path: str | Path,
        *,
        config: Gr00tN1d7Config,
    ) -> _CheckpointMappingEvidence:
        """验证 metadata、artifact 优先配置与完整 shard 命名空间。"""

        root = _local_root(path)
        for item in root.iterdir():
            if item.is_file() and item.name.endswith(_FORBIDDEN_SUFFIXES):
                raise ValueError("arbitrary pickle checkpoint formats are forbidden")
        for name in _REQUIRED_METADATA:
            candidate = root / name
            if candidate.resolve().parent != root or not candidate.is_file():
                raise ValueError(f"required checkpoint metadata is missing: {name}")
        realized = self.load_family_config(root, cosmos_revision=config.cosmos_revision)
        if realized != config:
            raise ValueError("requested config must exactly equal artifact-realized config")
        index_path = root / "model.safetensors.index.json"
        index = _read_json(index_path)
        raw_weight_map = index.get("weight_map")
        if not _is_object_mapping(raw_weight_map) or not raw_weight_map:
            raise ValueError("safetensors index weight_map must be non-empty")
        mapping: dict[str, str] = {}
        shards: set[str] = set()
        for raw_source, raw_shard in raw_weight_map.items():
            if not isinstance(raw_source, str) or not _SAFE_KEY.fullmatch(raw_source):
                raise ValueError("checkpoint keys must be canonical parameter names")
            if not isinstance(raw_shard, str) or not _SAFE_SHARD.fullmatch(raw_shard):
                raise ValueError("checkpoint shards must be safe safetensors basenames")
            shard_path = root / raw_shard
            if shard_path.is_symlink() or not shard_path.is_file():
                raise ValueError(f"checkpoint shard is missing or symlinked: {raw_shard}")
            target = self._map_key(raw_source)
            if target in mapping.values():
                raise ValueError(f"checkpoint key mapping collision: {target}")
            mapping[raw_source] = target
            shards.add(raw_shard)
        targets = tuple(mapping.values())
        if not any(key.startswith("backbone.") for key in targets) or not any(
            key.startswith("action_head.") for key in targets
        ):
            raise ValueError("checkpoint must contain backbone and action_head namespaces")
        return _CheckpointMappingEvidence(
            root,
            hashlib.sha256((root / "config.json").read_bytes()).hexdigest(),
            hashlib.sha256(index_path.read_bytes()).hexdigest(),
            mapping,
            tuple(sorted(shards)),
        )

    def compatibility_report(
        self,
        path: str | Path,
        *,
        config: Gr00tN1d7Config,
    ) -> CheckpointCompatibilityReport:
        """把静态检查投影为共享 checkpoint compatibility 报告。"""

        evidence = self.inspect(path, config=config)
        return CheckpointCompatibilityReport(
            root=str(evidence.root),
            weight_format="sharded_safetensors",
            weight_files=tuple(str(evidence.root / name) for name in evidence.shard_files),
            required_files=_REQUIRED_METADATA,
            missing_files=(),
            config_file=str(evidence.root / "config.json"),
            processor_files=tuple(
                str(evidence.root / name) for name in ("processor_config.json", "statistics.json")
            ),
            provenance_file=str(evidence.root / ".autovla-asset.json"),
            compatible=True,
        )

    def load_family_config(
        self,
        path: str | Path,
        *,
        cosmos_revision: str,
    ) -> Gr00tN1d7Config:
        """从 config 和 embodiment JSON 重建不可变家族配置。"""

        root = _local_root(path)
        payload = dict(_read_json(root / "config.json"))
        embodiment_payload = _read_json(root / "embodiment_id.json")
        embodiment_ids: dict[str, int] = {}
        for name, raw_id in embodiment_payload.items():
            if type(raw_id) is not int:
                raise ValueError("embodiment_id.json values must be exact integers")
            embodiment_ids[name] = raw_id
        payload["embodiment_ids"] = embodiment_ids
        config = Gr00tN1d7Config.from_artifact_mapping(payload, cosmos_revision=cosmos_revision)
        return replace(config, embodiment_ids=embodiment_ids)

    def convert_state_dict(
        self,
        state_dict: Mapping[str, "torch.Tensor"],
    ) -> Mapping[str, "torch.Tensor"]:
        """确定性转换容器前缀并拒绝目标键碰撞。"""

        output: dict[str, torch.Tensor] = {}
        for source, tensor in state_dict.items():
            target = self._map_key(source)
            if target in output:
                raise ValueError(f"checkpoint key mapping collision: {target}")
            output[target] = tensor
        return output

    def load_local(
        self,
        model: object,
        path: str | Path | None = None,
        *,
        strictness: str = "strict",
        device: "torch.device | str" = "cpu",
        dtype: "torch.dtype | None" = None,
        config: Gr00tN1d7Config | None = None,
    ) -> CheckpointLoadReport:
        """逐 shard 加载 shape 相符参数并返回完整分类。"""

        if path is None:
            raise RuntimeError("N1.7 tensor loading requires both a model and local path")
        torch = importlib.import_module("torch")
        module_type = torch.nn.Module
        if not isinstance(model, module_type):
            raise TypeError("checkpoint loading requires a torch.nn.Module")
        typed_model = cast(_TorchModule, model)
        if strictness not in {"strict", "diagnostic"}:
            raise ValueError("strictness must be strict or diagnostic")
        if config is None:
            model_config = typed_model.config
            if not isinstance(model_config, Gr00tN1d7Config):
                raise TypeError("N1.7 model must expose Gr00tN1d7Config")
            config = model_config
        compatibility = self.compatibility_report(path, config=config)
        expected = typed_model.state_dict()
        seen: set[str] = set()
        mapped: list[str] = []
        unexpected: list[str] = []
        mismatches: list[str] = []
        for shard in self._iter_shards(compatibility, device=device):
            converted = self.convert_state_dict(shard)
            for key, tensor in converted.items():
                if key in seen:
                    raise ValueError(f"duplicate key across checkpoint shards: {key}")
                seen.add(key)
                if key not in expected:
                    unexpected.append(key)
                elif tuple(expected[key].shape) != tuple(tensor.shape):
                    mismatches.append(key)
                else:
                    mapped.append(key)
            del converted, shard
        missing = sorted(set(expected) - seen)
        unexpected.sort()
        mismatches.sort()
        if strictness == "strict" and (missing or unexpected or mismatches):
            raise ValueError(
                "checkpoint mapping failed: "
                f"missing={missing}, unexpected={unexpected}, shapes={mismatches}"
            )
        if strictness == "strict":
            # 严格审计全部 shard 成功后才开始第二遍加载, 避免半更新模型。
            expected_keys = set(expected)
            for shard in self._iter_shards(compatibility, device=device):
                converted = self.convert_state_dict(shard)
                loadable: dict[str, torch.Tensor] = {}
                for key, tensor in converted.items():
                    if key not in expected_keys:
                        continue
                    if dtype is not None and tensor.is_floating_point():
                        tensor = tensor.to(dtype=dtype)
                    loadable[key] = tensor.to(device=device)
                typed_model.load_state_dict(loadable, strict=False)
                del converted, loadable, shard
        return CheckpointLoadReport(
            compatibility,
            tuple(sorted(mapped)),
            tuple(missing),
            tuple(unexpected),
            tuple(mismatches),
            strictness,
            {
                "schema_version": "autovla.gr00t_n1d7_checkpoint.v2",
                "index_sha256": (
                    hashlib.sha256(
                        (Path(compatibility.root) / "model.safetensors.index.json").read_bytes()
                    ).hexdigest()
                ),
                "local_files_only": True,
                "trust_remote_code": False,
            },
        )

    def _iter_shards(
        self,
        report: CheckpointCompatibilityReport,
        *,
        device: "torch.device | str",
    ) -> Iterator[Mapping[str, "torch.Tensor"]]:
        """通过 safetensors 公共 API 逐 shard 读取, 限制峰值主机/设备内存。"""

        if importlib.util.find_spec("safetensors") is None:
            raise OptionalDependencyError(
                "local N1.7 checkpoint requires the model-gr00t-n1d7 profile"
            )
        module = importlib.import_module("safetensors.torch")
        loader = getattr(module, "load_file", None)
        if not callable(loader):
            raise TypeError("safetensors.torch.load_file must be callable")
        for filename in report.weight_files:
            raw = loader(filename, device=str(device))
            if not isinstance(raw, Mapping):
                raise TypeError("safetensors loader must return a tensor mapping")
            yield cast(Mapping[str, "torch.Tensor"], raw)

    @staticmethod
    def _map_key(source: str) -> str:
        """剥离允许的外层 ``model.``, 保留官方 backbone/action_head 键。"""

        key = source.removeprefix("module.").removeprefix("_orig_mod.")
        key = key.removeprefix("model.")
        if key.startswith(("backbone.", "action_head.")) and _SAFE_KEY.fullmatch(key):
            return key
        raise ValueError(f"unsupported checkpoint namespace: {source}")


def _local_root(path: str | Path) -> Path:
    """解析绝对本地目录并拒绝 URL 与不存在路径。"""

    text = str(path)
    if "://" in text:
        raise ValueError("checkpoint path must be local")
    root = Path(path).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("checkpoint root must be an existing absolute local directory")
    return root.resolve()


__all__ = ["Gr00tN1d7CheckpointAdapter"]
