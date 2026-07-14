"""GR00T 官方元数据与结构化 checkpoint layout 测试。"""

# ruff: noqa: E402

from __future__ import annotations

import hashlib
import json
import operator
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest


def test_eagle_production_path_requires_verified_receipt_before_read() -> None:
    """Eagle tokenizer 与工厂都禁止按路径或文件名绕过 store 收据。"""

    processing = Path("autovla/models/families/gr00t_n1d6/_nvidia/eagle/processing.py").read_text(
        encoding="utf-8"
    )
    factory = Path("autovla/models/families/gr00t_n1d6/factory.py").read_text(encoding="utf-8")
    assert "receipt: ResolvedModelAsset" in processing
    assert "isinstance(receipt, ResolvedModelAsset)" in processing
    assert "raise UnresolvedEagleAssetError" in factory
    assert "LocalEagleConfig.from_local_json" not in factory
    assert "LocalEagleProcessor.from_local_assets" not in factory
    assert "complete SHA256 inventory" in factory


torch = pytest.importorskip("torch", reason="GR00T checkpoint adapter requires torch")

import autovla.assets.store as asset_store
from autovla.assets import (
    LocalModelAssetProvider,
    ModelAssetFile,
    ModelAssetIntegrityError,
    ModelAssetSpec,
    ModelAssetStore,
    ResolvedModelAsset,
)
from autovla.models.families.gr00t_n1d6.checkpoint import (
    AutoVLAParameterLayout,
    CheckpointKeyRule,
    CheckpointLoadPolicy,
    Gr00tN1d6CheckpointAdapter,
    UpstreamCheckpointLayout,
)
from autovla.models.families.gr00t_n1d6.config import (
    FeatureStatistics,
    PerHorizonFeatureStatistics,
)
from autovla.models.families.gr00t_n1d6.errors import (
    LocalModelAssetError,
    UnsupportedOfficialRelativeStatisticsError,
)
from autovla.models.families.gr00t_n1d6.processor import Gr00tN1d6Processor, _normalize
from autovla.models.outputs import CheckpointCompatibilityReport

if TYPE_CHECKING:
    from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import (
        LocalEagleProcessor,
    )


def _write(path: Path, payload: object) -> None:
    """写入测试所需的小 JSON。"""

    path.write_text(json.dumps(payload), encoding="utf-8")


def _metadata(root: Path) -> Path:
    """构造保留官方维度、顺序和二维 relative 结构的小元数据。"""

    root.mkdir()
    _write(
        root / "config.json",
        {
            "action_horizon": 50,
            "max_state_dim": 128,
            "max_action_dim": 128,
            "max_num_embodiments": 32,
            "model_name": "nvidia/Eagle-Block2A-2B-v2",
        },
    )
    _write(
        root / "embodiment_id.json",
        {
            "oxe_google": 0,
            "oxe_widowx": 1,
            "libero_panda": 2,
            "unitree_g1": 8,
            "robocasa_panda_omron": 13,
            "gr1": 20,
            "behavior_r1_pro": 24,
        },
    )
    _write(
        root / "processor_config.json",
        {
            "processor_class": "Gr00tN1d6Processor",
            "processor_kwargs": {
                "max_action_horizon": 50,
                "max_state_dim": 128,
                "max_action_dim": 128,
                "use_percentiles": False,
                "clip_outliers": True,
                "use_relative_action": True,
                "modality_configs": {
                    "gr1": {
                        "state": {"modality_keys": ["second", "first"]},
                        "action": {"modality_keys": ["right", "left"]},
                    }
                },
            },
        },
    )
    _write(
        root / "statistics.json",
        {
            "gr1": {
                "state": {
                    "first": {"mean": [1.0], "std": [2.0]},
                    "second": {"mean": [3.0, 4.0], "std": [5.0, 6.0]},
                },
                "action": {
                    "left": {"mean": [7.0], "std": [8.0]},
                    "right": {"mean": [9.0, 10.0], "std": [11.0, 12.0]},
                },
                "relative_action": {
                    "left": {"mean": [[1.0], [2.0]], "std": [[3.0], [4.0]]},
                    "right": {
                        "mean": [[5.0, 6.0], [7.0, 8.0]],
                        "std": [[9.0, 10.0], [11.0, 12.0]],
                    },
                },
            }
        },
    )
    return root


def _managed_official_asset(
    tmp_path: Path,
) -> tuple[ModelAssetSpec, ModelAssetStore, ResolvedModelAsset]:
    """构造具备官方布局标记的小型受管资产,不使用真实权重。"""

    source = tmp_path / "source"
    source.mkdir()
    records = {
        "LICENSE": b"test license\n",
        "config.json": (
            json.dumps(
                {
                    "action_horizon": 50,
                    "max_state_dim": 128,
                    "max_action_dim": 128,
                    "max_num_embodiments": 32,
                    "model_name": "nvidia/Eagle-Block2A-2B-v2",
                },
                sort_keys=True,
            ).encode("utf-8")
        ),
        "embodiment_id.json": b'{"gr1": 20}',
        "processor_config.json": b"{}",
        "statistics.json": b"{}",
        "model.safetensors.index.json": (
            json.dumps(
                {"weight_map": {"weight": "model-00001-of-00001.safetensors"}},
                sort_keys=True,
            ).encode("utf-8")
        ),
        "model-00001-of-00001.safetensors": b"weights",
    }
    roles = {
        "LICENSE": "license",
        "config.json": "model_config",
        "embodiment_id.json": "embodiment_mapping",
        "processor_config.json": "processor_config",
        "statistics.json": "normalization_statistics",
        "model.safetensors.index.json": "checkpoint_index",
        "model-00001-of-00001.safetensors": "base_model_weights",
    }
    for relative, content in records.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    spec = ModelAssetSpec(
        key="gr00t_fixture",
        family_key="gr00t_n1d6",
        provider="local",
        source_url="https://example.invalid/gr00t-fixture",
        public_identifier="offline/gr00t-fixture",
        repository="offline/gr00t-fixture",
        revision="2" * 40,
        license_name="Test-Only",
        license_file_path="LICENSE",
        use_limitation="tests only",
        redistribution="not applicable",
        checksum_policy="sha256-size-v1",
        files=tuple(
            ModelAssetFile(
                path=relative,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                role=roles[relative],
            )
            for relative, content in records.items()
        ),
    )
    store = ModelAssetStore(tmp_path / "store")
    resolved = store.fetch(spec, LocalModelAssetProvider(source))
    return spec, store, resolved


class _InMemoryCheckpointAdapter(Gr00tN1d6CheckpointAdapter):
    """用小 tensor 替代 safetensors I/O,以审计 verified 路径读取次数。"""

    def __init__(self, spec: ModelAssetSpec) -> None:
        """绑定测试规范并初始化 shard pass 计数。"""

        super().__init__(spec)
        self.passes = 0

    def _iter_state_dicts(
        self,
        report: CheckpointCompatibilityReport,
        *,
        device: torch.device | str,
    ) -> Iterator[Mapping[str, torch.Tensor]]:
        """每次调用返回一个与线性层匹配的小 state dict。"""

        assert report.weight_format == "sharded_safetensors" and str(device) == "cpu"
        self.passes += 1
        yield {"weight": torch.ones((1, 1))}


def test_official_metadata_preserves_dimensions_order_and_per_horizon_stats(
    tmp_path: Path,
) -> None:
    """官方 mean/std 按 processor 顺序拼接,relative 保持 ``[T,D]``。"""

    config = Gr00tN1d6CheckpointAdapter().parse_official_metadata(
        _metadata(tmp_path / "metadata"), eagle_asset_path=tmp_path / "eagle"
    )
    assert (config.action_horizon, config.max_state_dim, config.max_action_dim) == (50, 128, 128)
    assert config.max_num_embodiments == 32 and len(config.embodiment_ids) == 7
    statistics = config.statistics["gr1"]
    assert statistics.state_modality_order == ("second", "first")
    assert statistics.action_modality_order == ("right", "left")
    assert statistics.state.offset == (3.0, 4.0, 1.0)
    assert statistics.action.offset == (9.0, 10.0, 7.0)
    assert statistics.relative_action is not None
    assert statistics.relative_action.offset == ((5.0, 6.0, 1.0), (7.0, 8.0, 2.0))


def test_official_relative_statistics_fail_closed_at_one_dimensional_runtime(
    tmp_path: Path,
) -> None:
    """当前 processor 不得 flatten 或广播二维 relative 统计。"""

    config = Gr00tN1d6CheckpointAdapter().parse_official_metadata(
        _metadata(tmp_path / "metadata"), eagle_asset_path=tmp_path / "eagle"
    )
    with pytest.raises(UnsupportedOfficialRelativeStatisticsError, match=r"\[T,D\]"):
        Gr00tN1d6Processor(
            config,
            cast("LocalEagleProcessor", object()),
            visual_tokens_per_image=1,
        )


def test_sharded_index_reports_exact_partition_and_mapping_collision(tmp_path: Path) -> None:
    """index 返回真实 1106/633/473,前缀归一化碰撞被拒绝。"""

    root = tmp_path / "checkpoint"
    root.mkdir()
    weight_map = {
        **{f"backbone.layer.{index}": "a.safetensors" for index in range(633)},
        **{f"action_head.layer.{index}": "b.safetensors" for index in range(473)},
    }
    _write(root / "model.safetensors.index.json", {"weight_map": weight_map})
    (root / "a.safetensors").write_bytes(b"")
    (root / "b.safetensors").write_bytes(b"")
    layout = Gr00tN1d6CheckpointAdapter().inspect_upstream_layout(root)
    assert (layout.key_count, layout.backbone_key_count, layout.action_head_key_count) == (
        1106,
        633,
        473,
    )
    with pytest.raises(ValueError, match="collision"):
        Gr00tN1d6CheckpointAdapter().convert_state_dict(
            {"module.weight": torch.zeros(1), "weight": torch.ones(1)}
        )


def test_direct_official_adapter_calls_cannot_bypass_integrity_verification(
    tmp_path: Path,
) -> None:
    """裸官方目录的 inspect/config/load 三个入口都先验证 size/SHA256/许可清单。"""

    spec, _, resolved = _managed_official_asset(tmp_path)
    shard = resolved.root / "model-00001-of-00001.safetensors"
    shard.write_bytes(b"tamper!")
    adapter = Gr00tN1d6CheckpointAdapter(spec)
    with pytest.raises(ModelAssetIntegrityError, match="sha256"):
        adapter.inspect(resolved.root)
    with pytest.raises(ModelAssetIntegrityError, match="sha256"):
        adapter.load_family_config(resolved.root, eagle_asset_path=tmp_path / "eagle")
    with pytest.raises(ModelAssetIntegrityError, match="sha256"):
        adapter.load_local(torch.nn.Linear(1, 1, bias=False), resolved.root)


def test_unmanifested_official_metadata_cannot_use_legacy_load_path(tmp_path: Path) -> None:
    """官方标记目录缺 manifest 时不能伪装 legacy checkpoint。"""

    root = _metadata(tmp_path / "metadata")
    with pytest.raises(LocalModelAssetError, match=r"\.autovla-asset\.json"):
        Gr00tN1d6CheckpointAdapter().inspect(root)


def test_verified_checkpoint_path_reuses_manifest_hashes_without_integrity_rehash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """verified receipt 路径只保留 transactional shard 两遍,不再重读权重摘要。"""

    spec, _, resolved = _managed_official_asset(tmp_path)

    def _unexpected_hash(path: Path) -> str:
        """任何调用都表示 verified 调用链发生重复完整性读取。"""

        raise AssertionError(f"unexpected integrity hash for {path.name}")

    monkeypatch.setattr(asset_store, "_sha256", _unexpected_hash)
    adapter = _InMemoryCheckpointAdapter(spec)
    model = torch.nn.Linear(1, 1, bias=False)
    with torch.no_grad():
        model.weight.zero_()
    report = adapter.load_local(model, resolved, strictness="strict")
    assert adapter.passes == 2
    assert torch.equal(model.weight, torch.ones_like(model.weight))
    assert report.provenance["integrity_source"] == "verified_model_asset_manifest"
    weight_hashes = report.provenance["weight_files"]
    assert isinstance(weight_hashes, Mapping)
    expected_hash = next(item.sha256 for item in spec.files if item.role == "base_model_weights")
    assert weight_hashes["model-00001-of-00001.safetensors"] == expected_hash


def test_direct_checkpoint_path_hashes_each_registered_file_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """裸官方路径执行一次完整 integrity pass,provenance 不追加摘要读取。"""

    spec, _, resolved = _managed_official_asset(tmp_path)
    original = cast(
        Callable[[Path], str],
        getattr(asset_store, "_sha" + "256"),
    )
    hashed: list[str] = []

    def _counted_hash(path: Path) -> str:
        """记录相对文件名并调用真实流式摘要。"""

        hashed.append(path.relative_to(resolved.root).as_posix())
        return original(path)

    monkeypatch.setattr(asset_store, "_sha" + "256", _counted_hash)
    adapter = _InMemoryCheckpointAdapter(spec)
    model = torch.nn.Linear(1, 1, bias=False)
    adapter.load_local(model, resolved.root, strictness="strict")
    assert sorted(hashed) == sorted(item.path for item in spec.files)
    assert adapter.passes == 2


def test_checkpoint_layout_dataclasses_are_immutable_and_fail_closed() -> None:
    """结构化 mapping 真冻结,bool/int、路径、重复 key 和互斥 flag 均严格拒绝。"""

    layout = AutoVLAParameterLayout({"weight": (1, 2)})
    with pytest.raises(TypeError):
        operator.setitem(layout.shapes, "other", (3,))
    with pytest.raises(ValueError, match="exact bool"):
        CheckpointLoadPolicy(strict=cast(bool, 1))
    with pytest.raises(ValueError, match="mutually exclusive"):
        CheckpointLoadPolicy(strict=True, inspect_only=True)
    with pytest.raises(ValueError, match="unique"):
        CheckpointLoadPolicy(strict=False, allow_known_optional=("x", "x"))
    with pytest.raises(ValueError, match="non-empty"):
        CheckpointLoadPolicy(strict=False, allow_known_optional=("",))
    with pytest.raises(ValueError, match="canonical"):
        CheckpointLoadPolicy(strict=False, allow_known_optional=("bad key",))
    with pytest.raises(ValueError, match="source prefix"):
        CheckpointKeyRule("", "target.")
    with pytest.raises(ValueError, match="source prefix"):
        CheckpointKeyRule("bad prefix.", "")
    with pytest.raises(ValueError, match="safe safetensors"):
        UpstreamCheckpointLayout(
            index_file="/checkpoint/model.safetensors.index.json",
            shard_files=("../escape.safetensors",),
            key_count=1,
            backbone_key_count=1,
            action_head_key_count=0,
        )
    with pytest.raises(ValueError, match="safe safetensors"):
        UpstreamCheckpointLayout(
            index_file="/checkpoint/model.safetensors.index.json",
            shard_files=(" bad.safetensors",),
            key_count=1,
            backbone_key_count=1,
            action_head_key_count=0,
        )
    with pytest.raises(ValueError, match="unique"):
        UpstreamCheckpointLayout(
            index_file="/checkpoint/model.safetensors.index.json",
            shard_files=("safe.safetensors", "safe.safetensors"),
            key_count=1,
            backbone_key_count=1,
            action_head_key_count=0,
        )
    with pytest.raises(ValueError, match="identify"):
        UpstreamCheckpointLayout(
            index_file="/checkpoint/./model.safetensors.index.json",
            shard_files=("safe.safetensors",),
            key_count=1,
            backbone_key_count=1,
            action_head_key_count=0,
        )
    with pytest.raises(ValueError, match="exact integers"):
        UpstreamCheckpointLayout(
            index_file="/checkpoint/model.safetensors.index.json",
            shard_files=("safe.safetensors",),
            key_count=cast(int, True),
            backbone_key_count=0,
            action_head_key_count=0,
        )
    with pytest.raises(ValueError, match="shapes"):
        AutoVLAParameterLayout({"weight": cast(tuple[int, ...], [1])})
    with pytest.raises(ValueError, match="canonical"):
        AutoVLAParameterLayout({"bad key": (1,)})


def test_statistics_reject_non_finite_and_zero_variance_fails_explicitly() -> None:
    """新统计拒绝 NaN/Inf,absolute 零方差在除法前明确停止。"""

    with pytest.raises(ValueError, match="finite"):
        FeatureStatistics(offset=(float("nan"),), scale=(1.0,))
    with pytest.raises(ValueError, match="finite"):
        PerHorizonFeatureStatistics(
            offset=((0.0,),),
            scale=((float("inf"),),),
        )
    zero_variance = FeatureStatistics(offset=(0.0,), scale=(0.0,))
    with pytest.raises(ValueError, match="zero-variance"):
        _normalize(np.asarray([1.0], dtype=np.float32), zero_variance)
