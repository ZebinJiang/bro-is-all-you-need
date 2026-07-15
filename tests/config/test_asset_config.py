"""模型资产配置严格性测试。"""

from __future__ import annotations

from typing import cast

import pytest

from autovla.config.loader.validate import build_experiment_config
from autovla.config.schema import (
    AssetConfig,
    ExperimentConfig,
    ModelAssetStoreConfig,
    ModelConfig,
)


def test_asset_config_is_frozen_and_requires_absolute_root() -> None:
    """资产根只接受绝对路径且验证不能关闭。"""

    assert AssetConfig(store=ModelAssetStoreConfig(root="/models")).verify_on_resolve
    with pytest.raises(ValueError, match="absolute"):
        ModelAssetStoreConfig(root="relative")
    with pytest.raises(ValueError, match="remain true"):
        AssetConfig(verify_on_resolve=False)
    with pytest.raises(ValueError, match="remote_code"):
        AssetConfig(allow_remote_code=True)
    with pytest.raises(ValueError, match="pickle"):
        AssetConfig(allow_pickle=True)


def test_asset_reference_and_legacy_checkpoint_are_mutually_exclusive() -> None:
    """规范资产引用与旧 checkpoint 路径不能同时出现。"""

    with pytest.raises(ValueError, match="mutually exclusive"):
        ModelConfig(asset_key="gr00t_n1d6", checkpoint_path="/legacy")


def test_official_model_requires_asset_or_bounded_legacy_path() -> None:
    """官方模型缺失资产引用时在配置阶段 fail closed。"""

    with pytest.raises(ValueError, match=r"requires model\.asset_key"):
        build_experiment_config(
            {
                "model": {
                    "name": "gr00t",
                    "registry_key": "gr00t_n1d6",
                    "architecture_variant": "official_n1d6",
                    "eagle_asset_path": "/explicit/eagle",
                }
            }
        )


def test_experiment_fingerprint_excludes_local_asset_store_root() -> None:
    """不同机器的本地资产根保留在 resolved export,但语义指纹一致。"""

    first = ExperimentConfig(
        assets=AssetConfig(store=ModelAssetStoreConfig(root="/machine-a/models"))
    )
    second = ExperimentConfig(
        assets=AssetConfig(store=ModelAssetStoreConfig(root="/worktree-b/base_model"))
    )
    first_resolved = first.to_resolved_dict()
    second_resolved = second.to_resolved_dict()
    assert first_resolved["assets"] != second_resolved["assets"]
    assert first.fingerprint == second.fingerprint
    semantic_assets = first.to_semantic_dict()["assets"]
    assert isinstance(semantic_assets, dict)
    semantic_store = cast(dict[str, object], semantic_assets)["store"]
    assert isinstance(semantic_store, dict)
    assert "root" not in semantic_store


def test_assets_store_root_is_the_only_asset_root_owner() -> None:
    """旧 environment.model_home 必须作为未知冲突字段被拒绝。"""

    with pytest.raises(ValueError, match=r"unknown config key: environment\.model_home"):
        build_experiment_config(
            {
                "environment": {
                    "model_home": "/conflicting/models",
                },
                "assets": {"store": {"root": "/canonical/models"}},
            }
        )

    config = build_experiment_config({"assets": {"store": {"root": "/canonical/models"}}})
    assert config.to_resolved_dict()["assets"] == {
        "schema_version": "1.0",
        "store": {"root": "/canonical/models"},
        "verify_on_resolve": True,
    }
    assert "model_home" not in str(config.to_resolved_dict())
