"""GR00T 官方维度、R3 统计和双资产包契约测试。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import pytest

if TYPE_CHECKING:
    from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config

from autovla.assets import (
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
    Gr00tModelAssetBundle,
    ResolvedModelAsset,
)

_LOCAL_ASSET_ROOT = Path("/home/cz-jzb/workspace/vla-flywheel/base_model")
_BASE_REVISION = "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61"
_BASE_SPEC_IDENTITY = "a44b62e1217f603cbf5fc423c7f1b5c204e569ed97670cfb12736b166e9940ed"
_EAGLE_REVISION = "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"
_EAGLE_SPEC_IDENTITY = "cefdb0e85a6745990862fa1a8d1698d273582bfaae389651dc3e503434261496"


class _EagleConfigLike(Protocol):
    """描述测试观察的轻量 Eagle 几何接口。"""

    @property
    def visual_tokens_per_image(self) -> int:
        """返回每图 token 数。"""

        ...

    def with_family_image_size(self, image_size: int) -> "_EagleConfigLike":
        """应用 family 图像尺寸。"""

        ...


class _EagleConfigLoader(Protocol):
    """描述工厂私有 preflight loader 的测试调用形状。"""

    def __call__(
        self,
        path: str | Path,
        *,
        family_image_size: int | None,
    ) -> _EagleConfigLike:
        """解析本地 JSON 配置。"""

        ...


def _eagle_config_loader() -> _EagleConfigLoader:
    """通过模块映射收窄内部 loader,避免把它发布为产品 API。"""
    from autovla.models.families.gr00t_n1d6 import factory

    value: object = vars(factory).get("_load_eagle_config")
    if not callable(value):
        raise TypeError("factory lacks Eagle configuration preflight loader")
    return cast(_EagleConfigLoader, value)


def _write(path: Path, payload: object) -> None:
    """写入小型 JSON fixture。"""

    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_json_object(path: Path) -> Mapping[str, object]:
    """只读解析真实资产 JSON,不加载权重或执行远程代码。"""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return cast("Mapping[str, object]", payload)


def _official_metadata(root: Path) -> Path:
    """构造官方 50/128/128 envelope 与物理 ``[16,3]`` 统计 fixture。"""

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
    _write(root / "embodiment_id.json", {"gr1": 20})
    _write(
        root / "processor_config.json",
        {
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
            }
        },
    )
    relative_right_mean = [[float(step), float(step + 1)] for step in range(16)]
    relative_right_std = [[2.0, 3.0] for _ in range(16)]
    relative_left_mean = [[float(step + 2)] for step in range(16)]
    relative_left_std = [[4.0] for _ in range(16)]
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
                    "left": {"mean": relative_left_mean, "std": relative_left_std},
                    "right": {"mean": relative_right_mean, "std": relative_right_std},
                },
            }
        },
    )
    return root


def test_verified_local_asset_metadata_matches_official_envelope() -> None:
    """只读核对双 receipt 与真实官方 metadata,不访问网络、GPU 或权重。"""

    base_root = _LOCAL_ASSET_ROOT / "gr00t_n1d6" / _BASE_REVISION
    eagle_root = _LOCAL_ASSET_ROOT / "gr00t_n1d6_eagle_support" / _EAGLE_REVISION
    required = (
        base_root / ".autovla-asset.json",
        base_root / "config.json",
        base_root / "processor_config.json",
        eagle_root / ".autovla-asset.json",
    )
    if any(not path.is_file() for path in required):
        pytest.skip("verified pinned local GR00T+Eagle bundle is unavailable")

    base_receipt = _read_json_object(required[0])
    config = _read_json_object(required[1])
    processor = _read_json_object(required[2])
    eagle_receipt = _read_json_object(required[3])
    raw_kwargs = processor.get("processor_kwargs")
    if not isinstance(raw_kwargs, dict):
        raise AssertionError("processor_kwargs must be a JSON object")
    kwargs = cast("Mapping[str, object]", raw_kwargs)

    assert base_receipt.get("revision") == _BASE_REVISION
    assert base_receipt.get("spec_identity") == _BASE_SPEC_IDENTITY
    assert base_receipt.get("verification_state") == "verified"
    assert eagle_receipt.get("revision") == _EAGLE_REVISION
    assert eagle_receipt.get("spec_identity") == _EAGLE_SPEC_IDENTITY
    assert eagle_receipt.get("verification_state") == "verified"
    assert (
        config.get("action_horizon"),
        config.get("max_state_dim"),
        config.get("max_action_dim"),
    ) == (50, 128, 128)
    assert (
        kwargs.get("max_action_horizon"),
        kwargs.get("max_state_dim"),
        kwargs.get("max_action_dim"),
    ) == (50, 128, 128)


def test_official_metadata_converts_to_r3_axis_aware_statistics(tmp_path: Path) -> None:
    """官方顺序保留且 relative 统计不 flatten/首步/均值回退。"""

    pytest.importorskip("torch")
    from autovla.core.semantics import TensorLayout
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    config = Gr00tN1d6CheckpointAdapter().parse_official_metadata(
        _official_metadata(tmp_path / "metadata"),
        eagle_asset_path=tmp_path / "ignored-legacy-path",
    )
    assert (config.action_horizon, config.max_state_dim, config.max_action_dim) == (50, 128, 128)
    statistics = config.statistics["gr1"]
    assert statistics.state_modality_order == ("second", "first")
    assert statistics.action_modality_order == ("right", "left")
    assert statistics.state.layout == TensorLayout.feature(3)
    assert statistics.action.layout == TensorLayout.feature(3)
    assert statistics.relative_action is not None
    assert statistics.relative_action.layout == TensorLayout.time_feature(16, 3)
    assert statistics.relative_action.mean is not None
    np.testing.assert_array_equal(statistics.relative_action.mean[0], [0.0, 1.0, 2.0])
    np.testing.assert_array_equal(statistics.relative_action.mean[-1], [15.0, 16.0, 17.0])
    assert statistics.state_clip and statistics.action_clip and statistics.relative_action_clip
    assert len(statistics.source_fingerprint) == 64


def test_gr00t_factory_fails_closed_before_heavy_side_effect_without_bundle() -> None:
    """缺失完整双资产包时在依赖检查和模型分配前失败。"""

    from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory

    with pytest.raises(ValueError, match="Gr00tModelAssetBundle before heavy side effects"):
        Gr00tN1d6ModelFactory()(
            cast(
                "Gr00tN1d6Config",
                SimpleNamespace(asset_bundle=None, architecture_variant="official_n1d6"),
            )
        )


def test_real_eagle_metadata_geometry_projects_to_256_before_allocation(
    tmp_path: Path,
) -> None:
    """真实 num_patches 形状可独立解析,且 family 投影保持 256 token。"""

    path = tmp_path / "config.json"
    _write(
        path,
        {
            "text_config": {"model_type": "qwen3", "hidden_size": 2048},
            "vision_config": {
                "model_type": "siglip2_vision_model",
                "patch_size": 14,
                "num_patches": 256,
            },
            "image_token_index": 151669,
            "downsample_ratio": 0.5,
            "select_layer": -1,
        },
    )
    config = _eagle_config_loader()(path, family_image_size=None)

    assert config.visual_tokens_per_image == 256
    assert config.with_family_image_size(448).visual_tokens_per_image == 256


def test_eagle_geometry_types_and_conflicts_fail_before_dependency_check(
    tmp_path: Path,
) -> None:
    """错误 scalar、非正值和冲突几何均在 optional dependency/分配前停止。"""

    def payload(num_patches: object, patch_size: object = 14) -> dict[str, object]:
        """构造真实 metadata 形状的局部 JSON fixture。"""
        return {
            "text_config": {"model_type": "qwen3", "hidden_size": 2048},
            "vision_config": {
                "model_type": "siglip2_vision_model",
                "patch_size": patch_size,
                "num_patches": num_patches,
            },
            "image_token_index": 151669,
            "downsample_ratio": 0.5,
            "select_layer": -1,
        }

    invalid_num_patches = tmp_path / "invalid-num-patches.json"
    _write(invalid_num_patches, payload(True))
    with pytest.raises(ValueError, match="num_patches"):
        _eagle_config_loader()(invalid_num_patches, family_image_size=None)

    invalid_patch_size = tmp_path / "invalid-patch-size.json"
    _write(invalid_patch_size, payload(256, 0))
    with pytest.raises(ValueError, match="patch_size"):
        _eagle_config_loader()(invalid_patch_size, family_image_size=None)

    conflict = tmp_path / "conflict.json"
    _write(conflict, payload(255))
    with pytest.raises(ValueError, match="num_patches conflicts"):
        _eagle_config_loader()(conflict, family_image_size=448)

    source = Path("autovla/models/families/gr00t_n1d6/factory.py").read_text(encoding="utf-8")
    assert source.index("eagle_config = _load_eagle_config(") < source.index(
        "self._require_dependencies()"
    )


def test_asset_specs_separate_checkpoint_support_data_and_licenses() -> None:
    """权重与 Eagle 支持数据使用不同 key/revision/许可收据。"""

    assert GR00T_N1D6_ASSET_SPEC.key == "gr00t_n1d6"
    assert GR00T_N1D6_EAGLE_SUPPORT_SPEC.key == "gr00t_n1d6_eagle_support"
    assert GR00T_N1D6_ASSET_SPEC.revision != GR00T_N1D6_EAGLE_SUPPORT_SPEC.revision
    assert all(not item.path.endswith(".py") for item in GR00T_N1D6_EAGLE_SUPPORT_SPEC.files)
    assert {item.role for item in GR00T_N1D6_EAGLE_SUPPORT_SPEC.files} >= {
        "license",
        "eagle_config",
        "tokenizer_vocabulary",
        "tokenizer_merges",
        "generation_config",
    }


def test_valid_factory_source_has_no_unconditional_unresolved_exception() -> None:
    """完整路径构造本地 reviewed 类,不再无条件抛旧 blocker。"""

    source = Path("autovla/models/families/gr00t_n1d6/factory.py").read_text(encoding="utf-8")
    assert "raise UnresolvedEagleAssetError" not in source
    assert "raise UnsupportedOfficialRelativeStatisticsError" not in source
    assert "trust_remote_code" not in source
    assert "config_type.from_local_json" in source
    assert "eagle_config = _load_eagle_config" in source
    assert "local_eagle_processor.from_local_assets" in source
    assert "checkpoint_adapter.load_local" in source


def test_checkpoint_mapping_remains_structured_and_tensor_only() -> None:
    """checkpoint 映射保留 backbone/action_head namespace 且不启用任意 pickle。"""

    torch = pytest.importorskip("torch")
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    adapter = Gr00tN1d6CheckpointAdapter()
    converted = adapter.convert_state_dict(
        {
            "module.backbone.layer.weight": torch.zeros(1),
            "module.action_head.layer.weight": torch.ones(1),
        }
    )
    assert set(converted) == {"backbone.layer.weight", "action_head.layer.weight"}
    source = Path("autovla/models/families/gr00t_n1d6/checkpoint.py").read_text(encoding="utf-8")
    assert "weights_only=True" in source
    config_source = Path("autovla/models/families/gr00t_n1d6/config.py").read_text(encoding="utf-8")
    assert "local_files_only: bool = True" in config_source


def test_typed_bundle_rejects_unverified_objects() -> None:
    """任意路径或对象不能伪装成已验证双收据。"""

    with pytest.raises((TypeError, ValueError)):
        Gr00tModelAssetBundle(
            cast(ResolvedModelAsset, object()),
            cast(ResolvedModelAsset, object()),
        )
