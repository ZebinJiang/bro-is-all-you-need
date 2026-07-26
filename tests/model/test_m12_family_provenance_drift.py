"""M12 N1.7/Pi0.5 来源复用声明的无 Torch 漂移测试。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from autovla.models.families.gr00t_n1d7.family import GR00T_N1D7_FAMILY
from autovla.models.families.gr00t_n1d7.source_map import (
    GR00T_N1D7_SOURCE_RECEIPTS,
    NVIDIA_GR00T_REPOSITORY,
)
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.source_map import (
    OPENPI_REVISION,
    PI05_SOURCE_TO_LOCAL,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_TO_LOCAL_REUSE = ROOT / "docs/references/source_to_local_reuse.yaml"
UPSTREAM_SOURCE_TO_LOCAL = ROOT / "docs/references/upstream_source_to_local_map.yaml"
UPSTREAM_SOURCES = ROOT / "docs/references/upstream_sources.yaml"
NOTICE = ROOT / "THIRD_PARTY_NOTICES.md"


def _load_yaml(path: Path) -> dict[str, Any]:
    """读取 canonical YAML 并要求顶层为映射。"""

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _identity_rows(rows: object) -> list[dict[str, object]]:
    """仅投影跨文件必须完全一致的来源身份和采用分类。"""

    assert isinstance(rows, list)
    return [
        {
            "upstream_path": row["upstream_path"],
            "git_blob": row["git_blob"],
            "local_paths": row["local_paths"],
            "reuse_class": row["reuse_class"],
        }
        for row in rows
    ]


def _source_map_rows() -> dict[str, list[dict[str, object]]]:
    """从两个 family source map 构造唯一预期身份表。"""

    return {
        "gr00t_n1d7": [
            {
                "upstream_path": receipt.upstream_path,
                "git_blob": receipt.git_blob,
                "local_paths": [receipt.local_path],
                "reuse_class": receipt.reuse_class,
            }
            for receipt in GR00T_N1D7_SOURCE_RECEIPTS
        ],
        "pi0_5": [
            {
                "upstream_path": row["upstream_path"],
                "git_blob": row["git_blob"],
                "local_paths": row["local_paths"],
                "reuse_class": row["reuse_class"],
            }
            for row in PI05_SOURCE_TO_LOCAL
        ],
    }


def test_family_metadata_imports_without_torch_or_site_packages() -> None:
    """family/source map 元数据导入不得触发 Torch 或第三方运行依赖。"""

    script = """
import sys
from autovla.models.families.gr00t_n1d7.family import GR00T_N1D7_FAMILY
from autovla.models.families.gr00t_n1d7.source_map import SOURCE_MAP
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.source_map import PI05_SOURCE_TO_LOCAL
assert GR00T_N1D7_FAMILY.reuse[0].reuse_mode == "adapted"
assert PI05_SPEC.reuse[0].reuse_mode == "adapted"
assert SOURCE_MAP["code"]["copied_or_adapted_code"] is True
assert PI05_SOURCE_TO_LOCAL
assert "torch" not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_canonical_yaml_maps_match_family_source_maps() -> None:
    """两份 canonical source-to-local YAML 必须逐行匹配 family 事实源。"""

    expected = _source_map_rows()
    reuse = _load_yaml(SOURCE_TO_LOCAL_REUSE)["families"]
    upstream = _load_yaml(UPSTREAM_SOURCE_TO_LOCAL)["families"]
    for family_key, rows in expected.items():
        assert _identity_rows(reuse[family_key]["source_to_local"]) == rows
        assert _identity_rows(upstream[family_key]["source_to_local"]) == rows

    assert reuse["gr00t_n1d7"]["upstream"] == NVIDIA_GR00T_REPOSITORY
    assert reuse["pi0_5"]["revision"] == OPENPI_REVISION
    assert reuse["gr00t_n1d7"]["copied_or_adapted_code"] is True
    assert reuse["pi0_5"]["copied_or_adapted_code"] is True
    assert {row["reuse_class"] for row in expected["gr00t_n1d7"]} == {"adapted"}
    assert {row["reuse_class"] for row in expected["pi0_5"]} == {
        "adapted",
        "inspired",
        "license_reference",
    }


def test_family_specs_notices_and_source_registry_preserve_legal_boundaries() -> None:
    """外层声明必须承认适配代码并把模型资产条款独立失败关闭。"""

    n1d7_reuse = GR00T_N1D7_FAMILY.reuse[0]
    pi05_reuse = PI05_SPEC.reuse[0]
    assert (n1d7_reuse.reuse_mode, n1d7_reuse.copied_or_adapted_code) == (
        "adapted",
        True,
    )
    assert (pi05_reuse.reuse_mode, pi05_reuse.copied_or_adapted_code) == (
        "adapted",
        True,
    )
    assert "checkpoint and Cosmos terms separate" in n1d7_reuse.license
    assert "Gemma, tokenizer, checkpoint" in pi05_reuse.license

    registry = _load_yaml(UPSTREAM_SOURCES)
    by_name = {row["name"]: row for row in registry["sources"]}
    n1d7 = by_name["NVIDIA-Isaac-GR00T-N1.7-GA"]
    pi05 = by_name["Physical-Intelligence-OpenPI"]
    assert n1d7["reuse_class"] == "ADAPTED_SOURCE"
    assert pi05["reuse_class"] == "MIXED_MINIMAL_ADAPTATION_AND_CLEAN_REIMPLEMENTATION"
    assert "checkpoint_terms_conflict" in n1d7["license_status"]
    assert "Gemma_tokenizer_checkpoint" in pi05["license_status"]

    notice = NOTICE.read_text(encoding="utf-8")
    assert "three family-private files are attributed adaptations" in notice
    adapted_pi05_regions = [row for row in PI05_SOURCE_TO_LOCAL if row["reuse_class"] == "adapted"]
    assert len(adapted_pi05_regions) == 8
    assert (
        "observation/tokenizer/image preprocessing, transforms and checkpoint\n"
        "  conversion are minimally adapted into family-local AutoVLA contracts." in notice
    )
    assert "checkpoint terms conflict" in notice
    assert (
        "Gemma/checkpoint authorization and a\n"
        "  converted safetensors receipt remain separate and unresolved." in notice
    )


def test_adapted_local_headers_preserve_spdx_source_path_and_blob() -> None:
    """适配文件必须保留 Apache-2.0、版权/来源及精确 source identity。"""

    for receipt in GR00T_N1D7_SOURCE_RECEIPTS:
        text = (ROOT / receipt.local_path).read_text(encoding="utf-8")
        assert "SPDX-FileCopyrightText" in text
        assert "NVIDIA CORPORATION & AFFILIATES" in text
        assert "SPDX-License-Identifier: Apache-2.0" in text
        assert receipt.upstream_path in text
        assert receipt.git_blob in text
        assert "9c7e746b2cd37a810070a98ef41d290a07e806c2" in text

    adapted_pi05_paths = {
        local_path
        for row in PI05_SOURCE_TO_LOCAL
        if row["reuse_class"] == "adapted"
        for local_path in row["local_paths"]
    }
    for local_path in adapted_pi05_paths:
        text = (ROOT / local_path).read_text(encoding="utf-8")
        assert "SPDX-License-Identifier: Apache-2.0" in text
        assert "Physical-Intelligence/openpi" in text
        assert OPENPI_REVISION in text
