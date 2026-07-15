"""M10 状态、生命周期门与懒导出的聚焦回归测试。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.assets import (
    DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY,
    ModelFamilyAssetState,
)
from autovla.models.assembly import (
    CheckpointLoadEvidence,
    ModelAssemblyRequest,
    ModelRuntimeSupportError,
    TuningFreezeEvidence,
)
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
from autovla.models.families.gr00t_n1d7.family import GR00T_N1D7_FAMILY
from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.assets import Pi05AssetBundle
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.checkpoint import Pi05CheckpointAdapter
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.factory import Pi05ModelFactory
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.families.pi0_5.model import Pi05Model
from autovla.models.families.pi0_5.processor import Pi05Processor


def test_public_status_serialization_separates_source_assembly_and_runtime() -> None:
    """来源完整、可装配与运行就绪必须是三个独立公共事实。"""

    n1d6 = GR00T_N1D6_SPEC.to_json_dict()
    evidence = n1d6["assembly_requirements"]
    assert isinstance(evidence, dict)
    runtime = cast(dict[str, object], evidence["evidence"])
    assert runtime["source_architecture_complete"] is True
    assert n1d6["assembly_eligible"] is True
    assert n1d6["runtime_ready"] is False
    assert runtime["official_checkpoint_loaded_tensor_count"] == 1010
    assert runtime["official_checkpoint_missing_key_count"] == 0
    assert runtime["official_checkpoint_unexpected_key_count"] == 0
    assert runtime["official_checkpoint_shape_mismatch_count"] == 0
    assert runtime["accepted_evidence"] == [
        "C1_ASSET_RECEIPT_ACCEPTED",
        "C2R7_ONE_A100_STRICT_CHECKPOINT_LOAD_ACCEPTED",
    ]
    for definition in (GR00T_N1D7_FAMILY, PI05_SPEC):
        payload = definition.to_json_dict()
        assert payload["assembly_eligible"] is False
        assert payload["runtime_ready"] is False


def test_asset_lifecycle_uses_exact_fail_closed_states() -> None:
    """N1.6 停在 C3 数据门,N1.7/Pi0.5 停在资产许可门。"""

    statuses = {item.family_key: item for item in DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY.list()}
    assert statuses["gr00t_n1d6"].state is ModelFamilyAssetState.BLOCKED_C3_DATA
    assert statuses["gr00t_n1d6"].state.value == "BLOCKED_C3_DATA"
    for family_key in ("gr00t_n1d7", "pi0_5"):
        assert statuses[family_key].state is ModelFamilyAssetState.BLOCKED_ASSET_LICENSE
        assert statuses[family_key].state.value == "BLOCKED_ASSET_LICENSE"


def test_pi05_complete_cannot_bypass_shared_asset_license_gate() -> None:
    """即使调用方伪造完整组件,共享生命周期门也必须最先拒绝 Pi0.5。"""

    request = object.__new__(ModelAssemblyRequest)
    object.__setattr__(request, "family_key", "pi0_5")
    object.__setattr__(request, "config", Pi05Config())
    object.__setattr__(request, "asset_bundle", object.__new__(Pi05AssetBundle))
    placeholder = object()
    with pytest.raises(ModelRuntimeSupportError, match="asset_required"):
        Pi05ModelFactory().complete(
            request,
            processor=cast(Pi05Processor, placeholder),
            backbone=cast(Pi05VisionLanguageBackbone, placeholder),
            action_expert=cast(Pi05ActionExpert, placeholder),
            model=cast(Pi05Model, placeholder),
            checkpoint_adapter=cast(Pi05CheckpointAdapter, placeholder),
            checkpoint_load=cast(CheckpointLoadEvidence, placeholder),
            tuning_freeze=cast(TuningFreezeEvidence, placeholder),
        )


def test_family_roots_are_typed_lazy_cached_and_have_stable_dir() -> None:
    """新进程导入保持轻量,具体类型按需缓存且目录与导出一致。"""

    script = """
import sys
import autovla.models.families.gr00t_n1d7 as n1d7
import autovla.models.families.pi0_5 as pi05
assert not {'torch', 'transformers', 'jax', 'flax', 'orbax'} & set(sys.modules)
for package, name in ((n1d7, 'Gr00tN1d7FamilyDefinition'), (pi05, 'Pi05FamilyDefinition')):
    assert name in package.__all__
    assert name in dir(package)
    value = getattr(package, name)
    assert package.__dict__[name] is value
    assert getattr(package, name) is value
    assert set(package.__all__).issubset(dir(package))
assert not {'torch', 'transformers', 'jax', 'flax', 'orbax'} & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
