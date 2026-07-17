"""M10 三家族资产状态与显式 CLI 的聚焦测试。"""

from __future__ import annotations

import json

import pytest

from autovla.assets import (
    DEFAULT_MODEL_ASSET_REGISTRY,
    DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY,
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
    assert by_family["gr00t_n1d6"].state is ModelFamilyAssetState.BLOCKED_C3_DATA
    assert by_family["gr00t_n1d7"].state is ModelFamilyAssetState.BLOCKED_ASSET_LICENSE
    assert by_family["pi0_5"].state is ModelFamilyAssetState.BLOCKED_ASSET_LICENSE
    assert by_family["gr00t_n1d6"].runtime_authorized is False
    assert by_family["gr00t_n1d7"].state.value == "BLOCKED_LICENSE"
    assert by_family["pi0_5"].state.value == "BLOCKED_LICENSE"
    assert by_family["gr00t_n1d7"].registered_asset_keys
    assert by_family["pi0_5"].registered_asset_keys
    assert {spec.family_key for spec in DEFAULT_MODEL_ASSET_REGISTRY.list()} == {"gr00t_n1d6"}
    for key in ("gr00t_n1d7_checkpoint", "pi0_5_checkpoint"):
        with pytest.raises(ModelAssetConfigurationError, match="unknown model asset key"):
            DEFAULT_MODEL_ASSET_REGISTRY.require(key)


def test_family_bundle_registry_exposes_exact_receipts_and_missing_identities() -> None:
    """包注册必须区分已验证 receipt 与许可或不可变身份缺口。"""

    registrations = DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY.list()
    assert tuple(item.family_key for item in registrations) == (
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    )
    by_family = {item.family_key: item for item in registrations}
    assert {item.state.value for item in by_family["gr00t_n1d6"].components} == {"verified_receipt"}
    assert by_family["gr00t_n1d7"].lifecycle_state.value == "BLOCKED_LICENSE"
    assert by_family["pi0_5"].components[0].revision is None
    assert all(item.runtime_authorized is False for item in registrations)


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

    assert main(["--root", "/nonexistent/base_model", "--json", "bundles"]) == 0
    bundles = json.loads(capsys.readouterr().out)["result"]
    assert [item["family_key"] for item in bundles] == [
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    ]
