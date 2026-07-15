"""GR00T N1.7 本地 safetensors 索引映射与只检查证据。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config

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


@dataclass(frozen=True, slots=True)
class _CheckpointMappingEvidence:
    """保存不读取 tensor 的严格键映射证据。"""

    root: Path
    config_fingerprint: str
    index_fingerprint: str
    key_mapping: Mapping[str, str]
    shard_files: tuple[str, ...]
    executable_ready: bool = False
    blockers: tuple[str, ...] = (
        "checkpoint_license_conflict_unresolved",
        "gated_cosmos_receipt_required",
        "checkpoint_tensor_shapes_not_validated",
        "cuda_runtime_not_validated",
    )

    def __post_init__(self) -> None:
        """冻结映射并禁止 metadata 伪装执行就绪。"""

        if self.executable_ready:
            raise ValueError("metadata inspection cannot claim executable readiness")
        object.__setattr__(self, "key_mapping", MappingProxyType(dict(self.key_mapping)))


def _read_json(path: Path) -> Mapping[str, object]:
    """有界读取本地 JSON 对象。拒绝符号链接和超大 metadata。"""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"required local metadata is missing or symlinked: {path.name}")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"local metadata is unexpectedly large: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
        raise ValueError(f"local metadata must be a string-keyed object: {path.name}")
    return cast(Mapping[str, object], payload)


class Gr00tN1d7CheckpointAdapter:
    """严格检查本地索引并映射 backbone/action_head 命名空间。

    仅接受 sharded safetensors。类中没有 ``torch.load``、pickle、网络或
    ``trust_remote_code`` 路径。真实 tensor load 留给许可和资产门解除后的
    独立 CUDA 验证波次。
    """

    adapter_identity = "gr00t_n1d7:safetensors_index_strict:v1"

    def inspect(
        self,
        path: str | Path,
        *,
        config: Gr00tN1d7Config,
    ) -> _CheckpointMappingEvidence:
        """验证 metadata、artifact 配置优先级和完整 shard 命名空间。"""

        root = Path(path).expanduser().resolve()
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("checkpoint root must be an existing local directory")
        for item in root.rglob("*"):
            if item.is_file() and item.name.endswith(_FORBIDDEN_SUFFIXES):
                raise ValueError("arbitrary pickle checkpoint formats are forbidden")
        for name in _REQUIRED_METADATA:
            candidate = root / name
            if candidate.resolve().parent != root or not candidate.is_file():
                raise ValueError(f"required checkpoint metadata is missing: {name}")
        artifact_payload = _read_json(root / "config.json")
        realized = Gr00tN1d7Config.from_artifact_mapping(
            artifact_payload,
            cosmos_revision=config.cosmos_revision,
        )
        if realized != config:
            raise ValueError("requested config must exactly equal artifact-realized config")
        index_path = root / "model.safetensors.index.json"
        index = _read_json(index_path)
        raw_weight_map = index.get("weight_map")
        if not isinstance(raw_weight_map, dict) or not raw_weight_map:
            raise ValueError("safetensors index weight_map must be non-empty")
        mapping: dict[str, str] = {}
        shards: set[str] = set()
        for source, raw_shard in raw_weight_map.items():
            if not isinstance(source, str) or not _SAFE_KEY.fullmatch(source):
                raise ValueError("checkpoint keys must be canonical parameter names")
            if not isinstance(raw_shard, str) or not _SAFE_SHARD.fullmatch(raw_shard):
                raise ValueError("checkpoint shards must be safe safetensors basenames")
            shard_path = root / raw_shard
            if shard_path.is_symlink() or not shard_path.is_file():
                raise ValueError(f"checkpoint shard is missing or symlinked: {raw_shard}")
            target = self._map_key(source)
            if target in mapping.values():
                raise ValueError(f"checkpoint key mapping collision: {target}")
            mapping[source] = target
            shards.add(raw_shard)
        targets = tuple(mapping.values())
        if not any(key.startswith("backbone.") for key in targets) or not any(
            key.startswith("action_head.") for key in targets
        ):
            raise ValueError("checkpoint must contain backbone and action_head namespaces")
        config_fingerprint = hashlib.sha256((root / "config.json").read_bytes()).hexdigest()
        index_fingerprint = hashlib.sha256(index_path.read_bytes()).hexdigest()
        return _CheckpointMappingEvidence(
            root=root,
            config_fingerprint=config_fingerprint,
            index_fingerprint=index_fingerprint,
            key_mapping=mapping,
            shard_files=tuple(sorted(shards)),
        )

    def load_local(self, *_: object, **__: object) -> None:
        """在当前许可/资产/运行时证据状态下禁止任何 tensor load。"""

        raise RuntimeError(
            "N1.7 tensor loading is blocked by license, Cosmos receipt, shape, and CUDA evidence"
        )

    @staticmethod
    def _map_key(source: str) -> str:
        """执行无通配符、无静默丢键的规范命名空间映射。"""

        for prefix, target in (
            ("model.backbone.", "backbone."),
            ("backbone.", "backbone."),
            ("model.action_head.", "action_head."),
            ("action_head.", "action_head."),
        ):
            if source.startswith(prefix):
                suffix = source.removeprefix(prefix)
                if not suffix:
                    break
                return target + suffix
        raise ValueError(f"unsupported checkpoint namespace: {source}")


def _build_checkpoint_adapter(request: ModelAssemblyRequest) -> Gr00tN1d7CheckpointAdapter:
    """实现共享 checkpoint 组件工厂输入面。"""

    if request.family_key != "gr00t_n1d7":
        raise TypeError("request must belong to gr00t_n1d7")
    return Gr00tN1d7CheckpointAdapter()


__all__ = ["Gr00tN1d7CheckpointAdapter"]
