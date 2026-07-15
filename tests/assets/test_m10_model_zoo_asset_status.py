"""M10 三家族资产状态与显式 CLI 的聚焦测试。"""

from __future__ import annotations

import json

import pytest

from autovla.assets import (
    DEFAULT_MODEL_ASSET_REGISTRY,
    DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY,
    ModelAssetConfigurationError,
    ModelFamilyAssetState,
)
from autovla.cli.assets import main


def test_asset_status_is_truthful_and_blocked_families_have_no_fetch_spec() -> None:
    """只有 N1.6 已注册固定文件清单,N1.7/Pi0.5 必须失败关闭。"""

    statuses = DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY.list()
    assert tuple(status.family_key for status in statuses) == (
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    )
    by_family = {status.family_key: status for status in statuses}
    assert by_family["gr00t_n1d6"].state is (
        ModelFamilyAssetState.INVENTORY_READY_COMPUTE_VERIFICATION_REQUIRED
    )
    assert by_family["gr00t_n1d6"].runtime_authorized is False
    assert by_family["gr00t_n1d7"].registered_asset_keys == ()
    assert by_family["pi0_5"].registered_asset_keys == ()
    assert {spec.family_key for spec in DEFAULT_MODEL_ASSET_REGISTRY.list()} == {"gr00t_n1d6"}
    for key in ("gr00t_n1d7_checkpoint", "pi0_5_checkpoint"):
        with pytest.raises(ModelAssetConfigurationError, match="unknown model asset key"):
            DEFAULT_MODEL_ASSET_REGISTRY.require(key)


def test_asset_cli_families_and_status_are_metadata_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """families/status 只输出不可变状态,不解析资产目录或网络 provider。"""

    assert main(["--root", "/nonexistent/base_model", "--json", "families"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["family_key"] for item in payload["result"]] == [
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    ]
    assert all(item["runtime_authorized"] is False for item in payload["result"])

    assert (
        main(
            [
                "--root",
                "/nonexistent/base_model",
                "--json",
                "families",
                "--include-deferred",
            ]
        )
        == 0
    )
    all_families = json.loads(capsys.readouterr().out)["result"]
    assert [item["family_key"] for item in all_families] == [
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0",
        "pi0_5",
        "pi0_fast",
    ]

    assert main(["--root", "/nonexistent/base_model", "--json", "status", "pi0_5"]) == 0
    status = json.loads(capsys.readouterr().out)["result"]
    assert status["first_blocker"] == "PI05_CHECKPOINT_AND_GEMMA_TERMS_RECEIPT_MISSING"
