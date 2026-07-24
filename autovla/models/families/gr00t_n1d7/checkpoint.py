"""GR00T N1.7 本地 sharded-safetensors 检查与流式加载。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import product
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, ContextManager, Protocol, TypeGuard, cast

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
_MAX_TENSOR_SLICE_BYTES = 32 * 1024 * 1024
_MAX_LIVE_TENSOR_BYTES = 2 * _MAX_TENSOR_SLICE_BYTES
_SAFETENSORS_DTYPE_BYTES = MappingProxyType(
    {
        "BOOL": 1,
        "U8": 1,
        "I8": 1,
        "F8_E4M3": 1,
        "F8_E5M2": 1,
        "I16": 2,
        "U16": 2,
        "F16": 2,
        "BF16": 2,
        "I32": 4,
        "U32": 4,
        "F32": 4,
        "I64": 8,
        "U64": 8,
        "F64": 8,
        "C64": 8,
        "C128": 16,
    }
)


class _TorchModule(Protocol):
    """描述严格加载所需的最小 Torch 模块表面。"""

    config: object

    def state_dict(self) -> Mapping[str, "torch.Tensor"]:
        """返回命名参数映射。"""
        ...


class _SafeTensorSlice(Protocol):
    """描述 safetensors 零载荷 shape 审计和切片读取表面。"""

    def get_shape(self) -> Sequence[int]:
        """返回 tensor shape,不物化 tensor。"""
        ...

    def get_dtype(self) -> str:
        """返回 safetensors 规范 dtype 名。"""
        ...

    def __getitem__(self, region: tuple[slice, ...]) -> "torch.Tensor":
        """只物化指定区域。"""
        ...


class _SafeTensorHandle(Protocol):
    """描述单个本地 safetensors 文件的最小只读表面。"""

    def keys(self) -> Sequence[str]:
        """返回 shard 内参数键。"""
        ...

    def get_slice(self, key: str) -> _SafeTensorSlice:
        """返回不立即读取载荷的 tensor 切片视图。"""
        ...

    def get_tensor(self, key: str) -> "torch.Tensor":
        """读取标量 tensor。"""
        ...


class _SafeOpen(Protocol):
    """描述 ``safetensors.safe_open`` 的本地调用契约。"""

    def __call__(
        self,
        filename: str,
        *,
        framework: str,
        device: str,
    ) -> ContextManager[_SafeTensorHandle]:
        """在 CPU 上打开一个本地 shard。"""
        ...


class _NoGradFactory(Protocol):
    """描述 ``torch.no_grad`` 的最小上下文工厂表面。"""

    def __call__(self) -> ContextManager[None]:
        """创建禁用梯度记录的上下文。"""
        ...


def _is_no_grad_factory(value: object) -> TypeGuard[_NoGradFactory]:
    """把动态 Torch 属性收窄为上下文工厂。"""

    return callable(value)


@dataclass(frozen=True, slots=True)
class _CheckpointMappingEvidence:
    """保存不读取 tensor 的索引与配置重建证据。"""

    root: Path
    config_fingerprint: str
    index_fingerprint: str
    key_mapping: Mapping[str, str]
    shard_mapping: Mapping[str, str]
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
        object.__setattr__(self, "shard_mapping", MappingProxyType(dict(self.shard_mapping)))


@dataclass(frozen=True, slots=True)
class _CheckpointAudit:
    """保存严格审计结果,确保 mutation 前已检查全部键和 shape。"""

    mapped: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    mismatches: tuple[str, ...]


class _Gr00tN1d7PartitionedLoadSink:
    """以 safetensors metadata 和有界切片实现 ZeRO-3 逐张量加载。"""

    def __init__(
        self,
        adapter: Gr00tN1d7CheckpointAdapter,
        model: object,
        path: str | Path,
        *,
        strictness: str,
        dtype: torch.dtype | None,
        config: Gr00tN1d7Config | None,
    ) -> None:
        """保存轻量输入,不在所有 rank 构造阶段读取 checkpoint。"""

        self._adapter = adapter
        self._model = model
        self._path = path
        self._strictness = strictness
        self._dtype = dtype
        self._config = config
        self._evidence: _CheckpointMappingEvidence | None = None
        self._compatibility: CheckpointCompatibilityReport | None = None
        self._sources: dict[str, str] = {}
        self._shapes: dict[str, tuple[int, ...]] = {}
        self._audited: set[str] = set()
        self._loaded: set[str] = set()
        self._audited_element_count = 0

    def prepare(self) -> None:
        """仅在 rank 0 验证本地资产并建立目标到 shard key 的映射。"""

        if self._strictness != "strict":
            raise ValueError("ZeRO-3 GR00T N1.7 loading requires strict checkpoint semantics")
        config = self._config
        if config is None:
            raw_config = getattr(self._model, "config", None)
            if not isinstance(raw_config, Gr00tN1d7Config):
                raise TypeError("N1.7 model must expose Gr00tN1d7Config")
            config = raw_config
        evidence = self._adapter.inspect(self._path, config=config)
        sources: dict[str, str] = {}
        for source, target in evidence.key_mapping.items():
            if target in sources:
                raise ValueError(f"checkpoint key mapping collision: {target}")
            sources[target] = source
        seen_sources: set[str] = set()
        shapes: dict[str, tuple[int, ...]] = {}
        for shard_name, handle in self._adapter._iter_shard_handles(evidence):
            for source in handle.keys():
                if source in seen_sources:
                    raise ValueError(f"duplicate key across checkpoint shards: {source}")
                seen_sources.add(source)
                target = evidence.key_mapping.get(source)
                if target is None:
                    raise ValueError(f"checkpoint shard contains an unindexed key: {source}")
                if evidence.shard_mapping[source] != shard_name:
                    raise ValueError(f"checkpoint shard/index assignment mismatch: {source}")
                shapes[target] = _logical_shape(
                    tuple(handle.get_slice(source).get_shape())
                )
        indexed_sources = set(evidence.key_mapping)
        if seen_sources != indexed_sources:
            raise ValueError(
                "checkpoint index/physical key mismatch: "
                f"missing_indexed_sources={sorted(indexed_sources - seen_sources)}, "
                f"unindexed_sources={sorted(seen_sources - indexed_sources)}"
            )
        self._evidence = evidence
        self._compatibility = self._adapter._compatibility_from_evidence(evidence)
        self._sources = sources
        self._shapes = shapes

    def audit_tensor(
        self,
        name: str,
        logical_shape: tuple[int, ...],
        /,
    ) -> None:
        """用 safetensors metadata 审计 ZeRO 逻辑 full-shape。"""

        logical_shape = _logical_shape(logical_shape)
        source = self._sources.get(name)
        if source is None:
            raise ValueError(f"checkpoint mapping failed: missing={[name]}")
        if self._shapes[name] != logical_shape:
            raise ValueError(f"checkpoint mapping failed: shapes={[name]}")
        if name in self._audited:
            raise RuntimeError(f"partitioned checkpoint tensor was audited twice: {name}")
        self._audited.add(name)
        self._audited_element_count += math.prod(logical_shape)

    def complete_audit(
        self,
        *,
        parameter_names: tuple[str, ...],
        buffer_names: tuple[str, ...],
    ) -> None:
        """要求 checkpoint、参数和复制 buffer 形成严格全覆盖。"""

        expected = set(parameter_names) | set(buffer_names)
        missing = sorted(expected - set(self._sources))
        unexpected = sorted(set(self._sources) - expected)
        if missing or unexpected or self._audited != expected:
            raise ValueError(
                f"checkpoint mapping failed: missing={missing}, unexpected={unexpected}, shapes=[]"
            )

    def load_tensor(self, name: str, tensor: object, /) -> None:
        """仅在 rank 0 用固定切片上限写入一个已聚合目标。"""

        torch = importlib.import_module("torch")
        if not isinstance(tensor, torch.Tensor):
            raise TypeError("partitioned checkpoint target must be a torch.Tensor")
        if name not in self._audited or name in self._loaded:
            raise RuntimeError(
                f"partitioned checkpoint tensor was not audited exactly once: {name}"
            )
        source = self._sources[name]
        evidence = self._require_evidence()
        expected_shard = evidence.shard_mapping[source]
        no_grad = getattr(torch, "no_grad", None)
        if not _is_no_grad_factory(no_grad):
            raise TypeError("torch.no_grad must be callable")
        with no_grad():
            for shard_name, handle in self._adapter._iter_shard_handles(evidence):
                if shard_name != expected_shard:
                    continue
                tensor_slice = handle.get_slice(source)
                item_bytes = _dtype_bytes(tensor_slice.get_dtype())
                max_slice_bytes = _shard_slice_limit(
                    evidence.root / shard_name,
                    item_bytes=item_bytes,
                )
                for region in _iter_chunk_regions(
                    tuple(tensor_slice.get_shape()),
                    item_bytes=item_bytes,
                    max_slice_bytes=max_slice_bytes,
                ):
                    payload = handle.get_tensor(source) if not region else tensor_slice[region]
                    if self._dtype is not None and payload.is_floating_point():
                        payload = payload.to(device=tensor.device, dtype=self._dtype)
                    else:
                        payload = payload.to(device=tensor.device, dtype=tensor.dtype)
                    destination = tensor if not region else tensor[region]
                    destination.copy_(payload)
                    del destination, payload
                self._loaded.add(name)
                return
        raise RuntimeError(f"checkpoint shard was not opened for source key: {source}")

    def finish(self) -> Mapping[str, object]:
        """确认每个审计张量均已加载并导出无 tensor 报告载荷。"""

        if self._loaded != self._audited:
            raise RuntimeError("partitioned checkpoint load did not consume the audited tensor set")
        compatibility = self._compatibility
        evidence = self._require_evidence()
        if compatibility is None:
            raise RuntimeError("partitioned checkpoint compatibility is unavailable")
        return {
            "compatibility": compatibility,
            "mapped_keys": tuple(sorted(self._loaded)),
            "missing_keys": (),
            "unexpected_keys": (),
            "shape_mismatches": (),
            "strictness": "strict",
            "provenance": {
                "schema_version": "autovla.gr00t_n1d7_checkpoint.v2",
                "index_sha256": hashlib.sha256(
                    (evidence.root / "model.safetensors.index.json").read_bytes()
                ).hexdigest(),
                "local_files_only": True,
                "trust_remote_code": False,
                "strict_audit_before_mutation": True,
                "max_live_tensor_payload_bytes": _MAX_LIVE_TENSOR_BYTES,
                "live_payload_bound": "min(64MiB, shard_file_size-1)",
                "partitioned_parameter_group_bound": 1,
                "loaded_element_count": self._audited_element_count,
            },
        }

    def restore_result(self, payload: Mapping[str, object], /) -> CheckpointLoadReport:
        """由每个 rank 恢复相同的 family 加载报告。"""

        if set(payload) != {
            "compatibility",
            "mapped_keys",
            "missing_keys",
            "unexpected_keys",
            "shape_mismatches",
            "strictness",
            "provenance",
        }:
            raise ValueError("partitioned GR00T N1.7 result payload fields are invalid")
        compatibility = payload["compatibility"]
        provenance = payload["provenance"]
        if not isinstance(compatibility, CheckpointCompatibilityReport):
            raise TypeError("partitioned checkpoint compatibility payload is invalid")
        if not isinstance(provenance, Mapping):
            raise TypeError("partitioned checkpoint provenance payload is invalid")
        return CheckpointLoadReport(
            compatibility,
            _string_tuple(payload["mapped_keys"], name="mapped_keys"),
            _string_tuple(payload["missing_keys"], name="missing_keys"),
            _string_tuple(payload["unexpected_keys"], name="unexpected_keys"),
            _string_tuple(payload["shape_mismatches"], name="shape_mismatches"),
            _required_string(payload["strictness"], name="strictness"),
            _string_object_mapping(provenance, name="provenance"),
        )

    def _require_evidence(self) -> _CheckpointMappingEvidence:
        """返回仅 rank 0 准备的 checkpoint 映射证据。"""

        if self._evidence is None:
            raise RuntimeError("partitioned checkpoint sink is not prepared on rank 0")
        return self._evidence


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
        shard_mapping: dict[str, str] = {}
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
            shard_mapping[raw_source] = raw_shard
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
            shard_mapping,
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
        evidence = self.inspect(path, config=config)
        compatibility = self._compatibility_from_evidence(evidence)
        expected = typed_model.state_dict()
        audit = self._audit_shapes(evidence, expected)
        if strictness == "strict" and (audit.missing or audit.unexpected or audit.mismatches):
            raise ValueError(
                "checkpoint mapping failed: "
                f"missing={list(audit.missing)}, unexpected={list(audit.unexpected)}, "
                f"shapes={list(audit.mismatches)}"
            )
        if strictness == "strict":
            # 严格审计全部 shard 成功后才按固定字节上限切片 mutation。
            self._mutate_streaming(
                evidence,
                expected,
                device=device,
                dtype=dtype,
                torch_module=torch,
            )
        return CheckpointLoadReport(
            compatibility,
            audit.mapped,
            audit.missing,
            audit.unexpected,
            audit.mismatches,
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
                "strict_audit_before_mutation": True,
                "max_live_tensor_payload_bytes": _MAX_LIVE_TENSOR_BYTES,
                "live_payload_bound": "min(64MiB, shard_file_size-1)",
                "loaded_element_count": sum(
                    expected[key].numel() for key in audit.mapped
                ),
            },
        )

    def partitioned_load(
        self,
        model: object,
        path: str | Path,
        *,
        strictness: str = "strict",
        dtype: torch.dtype | None = None,
        config: Gr00tN1d7Config | None = None,
    ) -> _Gr00tN1d7PartitionedLoadSink:
        """构造延迟 I/O 的 ZeRO-3 严格流式 sink。"""

        return _Gr00tN1d7PartitionedLoadSink(
            self,
            model,
            path,
            strictness=strictness,
            dtype=dtype,
            config=config,
        )

    def _compatibility_from_evidence(
        self,
        evidence: _CheckpointMappingEvidence,
    ) -> CheckpointCompatibilityReport:
        """把已完成的 metadata 检查投影为共享报告,避免重复扫描。"""

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

    def _audit_shapes(
        self,
        evidence: _CheckpointMappingEvidence,
        expected: Mapping[str, "torch.Tensor"],
    ) -> _CheckpointAudit:
        """仅在 CPU metadata 视图上完成全部键、归属和 shape 审计。"""

        seen_sources: set[str] = set()
        seen_targets: set[str] = set()
        mapped: list[str] = []
        unexpected: list[str] = []
        mismatches: list[str] = []
        for shard_name, handle in self._iter_shard_handles(evidence):
            for source in handle.keys():
                if source in seen_sources:
                    raise ValueError(f"duplicate key across checkpoint shards: {source}")
                seen_sources.add(source)
                target = evidence.key_mapping.get(source)
                if target is None:
                    target = self._map_key(source)
                    unexpected.append(target)
                elif evidence.shard_mapping[source] != shard_name:
                    raise ValueError(f"checkpoint shard/index assignment mismatch: {source}")
                if target in seen_targets:
                    raise ValueError(f"checkpoint key mapping collision: {target}")
                seen_targets.add(target)
                if target not in expected:
                    if target not in unexpected:
                        unexpected.append(target)
                    continue
                shape = tuple(handle.get_slice(source).get_shape())
                if tuple(expected[target].shape) != shape:
                    mismatches.append(target)
                else:
                    mapped.append(target)
        indexed_sources = set(evidence.key_mapping)
        if seen_sources != indexed_sources:
            missing_indexed_sources = sorted(indexed_sources - seen_sources)
            unindexed_sources = sorted(seen_sources - indexed_sources)
            raise ValueError(
                "checkpoint index/physical key mismatch: "
                f"missing_indexed_sources={missing_indexed_sources}, "
                f"unindexed_sources={unindexed_sources}"
            )
        missing = sorted(set(expected) - seen_targets)
        return _CheckpointAudit(
            tuple(sorted(mapped)),
            tuple(missing),
            tuple(sorted(unexpected)),
            tuple(sorted(mismatches)),
        )

    def _mutate_streaming(
        self,
        evidence: _CheckpointMappingEvidence,
        expected: Mapping[str, "torch.Tensor"],
        *,
        device: "torch.device | str",
        dtype: "torch.dtype | None",
        torch_module: object,
    ) -> None:
        """逐 tensor 切片复制,峰值 checkpoint 载荷显式限制为 64 MiB。"""

        no_grad = getattr(torch_module, "no_grad", None)
        if not _is_no_grad_factory(no_grad):
            raise TypeError("torch.no_grad must be callable")
        with no_grad():
            for shard_name, handle in self._iter_shard_handles(evidence):
                for source in handle.keys():
                    target = evidence.key_mapping[source]
                    destination = expected[target]
                    tensor_slice = handle.get_slice(source)
                    shape = tuple(tensor_slice.get_shape())
                    item_bytes = _dtype_bytes(tensor_slice.get_dtype())
                    max_slice_bytes = _shard_slice_limit(
                        evidence.root / shard_name,
                        item_bytes=item_bytes,
                    )
                    for region in _iter_chunk_regions(
                        shape,
                        item_bytes=item_bytes,
                        max_slice_bytes=max_slice_bytes,
                    ):
                        payload = handle.get_tensor(source) if not region else tensor_slice[region]
                        if dtype is not None and payload.is_floating_point():
                            payload = payload.to(device=device, dtype=dtype)
                        else:
                            payload = payload.to(device=device)
                        destination_region = destination if not region else destination[region]
                        destination_region.copy_(payload)
                        del destination_region, payload

    def _iter_shard_handles(
        self,
        evidence: _CheckpointMappingEvidence,
    ) -> Iterator[tuple[str, _SafeTensorHandle]]:
        """以只读 CPU 映射逐个打开本地 shard,退出迭代即关闭句柄。"""

        if importlib.util.find_spec("safetensors") is None:
            raise OptionalDependencyError(
                "local N1.7 checkpoint requires the model-gr00t-n1d7 profile"
            )
        module = importlib.import_module("safetensors")
        opener = cast(_SafeOpen, getattr(module, "safe_open", None))
        if not callable(opener):
            raise TypeError("safetensors.safe_open must be callable")
        for shard_name in evidence.shard_files:
            with opener(
                str(evidence.root / shard_name),
                framework="pt",
                device="cpu",
            ) as handle:
                yield shard_name, handle

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


def _dtype_bytes(dtype: str) -> int:
    """把 safetensors dtype 映射为单元素字节数,未知值失败关闭。"""

    try:
        return _SAFETENSORS_DTYPE_BYTES[dtype]
    except KeyError as exc:
        raise ValueError(f"unsupported safetensors dtype: {dtype}") from exc


def _iter_chunk_regions(
    shape: tuple[int, ...],
    *,
    item_bytes: int,
    max_slice_bytes: int = _MAX_TENSOR_SLICE_BYTES,
) -> Iterator[tuple[slice, ...]]:
    """生成不超过固定载荷上限的多维切片区域。"""

    if any(type(dimension) is not int or dimension < 0 for dimension in shape):
        raise ValueError("safetensors shape must contain non-negative integers")
    if not shape:
        yield ()
        return
    if 0 in shape:
        return
    max_elements = max(1, max_slice_bytes // item_bytes)
    chunk_shape = [1] * len(shape)
    remaining = max_elements
    for index in range(len(shape) - 1, -1, -1):
        width = min(shape[index], remaining)
        chunk_shape[index] = max(1, width)
        remaining = max(1, remaining // chunk_shape[index])
    if math.prod(chunk_shape) > max_elements:
        raise AssertionError("checkpoint chunk planner exceeded its byte budget")
    starts = [
        range(0, dimension, chunk) for dimension, chunk in zip(shape, chunk_shape, strict=True)
    ]
    for offsets in product(*starts):
        yield tuple(
            slice(offset, min(offset + chunk, dimension))
            for offset, chunk, dimension in zip(offsets, chunk_shape, shape, strict=True)
        )


def _shard_slice_limit(path: Path, *, item_bytes: int) -> int:
    """把同时存活的源/目标载荷限制在单个 shard 文件大小以下。"""

    shard_bytes = path.stat().st_size
    if shard_bytes <= 2 * item_bytes:
        raise ValueError("safetensors shard is too small to contain a valid local payload")
    return min(_MAX_TENSOR_SLICE_BYTES, max(1, (shard_bytes - 1) // 2))


def _string_tuple(raw: object, *, name: str) -> tuple[str, ...]:
    """校验 collective 载荷中的字符串元组。"""

    if type(raw) is not tuple or any(not isinstance(item, str) for item in raw):
        raise TypeError(f"{name} must be a tuple of strings")
    return cast(tuple[str, ...], raw)


def _logical_shape(raw: object) -> tuple[int, ...]:
    """校验策略传入的参数或 buffer 逻辑 shape。"""

    if type(raw) is not tuple:
        raise TypeError("partitioned checkpoint logical shape must be a tuple")
    dimensions = cast(tuple[object, ...], raw)
    if any(type(value) is not int or value < 0 for value in dimensions):
        raise ValueError(
            "partitioned checkpoint logical shape must contain non-negative integers"
        )
    return cast(tuple[int, ...], raw)


def _required_string(raw: object, *, name: str) -> str:
    """校验 collective 载荷中的非空字符串。"""

    if not isinstance(raw, str) or not raw:
        raise TypeError(f"{name} must be a non-empty string")
    return raw


def _string_object_mapping(raw: object, *, name: str) -> Mapping[str, object]:
    """校验 collective 载荷中的字符串键映射。"""

    if not isinstance(raw, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, object] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if not isinstance(key, str) or not key:
            raise TypeError(f"{name} keys must be non-empty strings")
        result[key] = value
    return result


__all__ = ["Gr00tN1d7CheckpointAdapter"]
