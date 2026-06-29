"""M3 GR00T 模型动物园 readiness 测试。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.core.types import ActionChunk, FrameworkOutput, ModelInput


def test_model_zoo_should_lookup_gr00t_n1d6_metadata() -> None:
    """验证 gr00t-n1d6 注册条目只暴露元数据契约。"""
    from autovla.models import get_model_zoo_entry, list_model_zoo_keys

    entry = get_model_zoo_entry("gr00t-n1d6")

    assert list_model_zoo_keys() == ("gr00t-n1d6",)
    assert entry.model_registry_key == "gr00t-n1d6"
    assert entry.source_family == "GR00T"
    assert entry.release_reference.tag == "n1.6.1-release"
    assert entry.release_reference.short_commit == "5dc80c4"
    assert entry.support_status == "unavailable_missing_assets"
    assert entry.assets.checkpoint_uri is None
    assert entry.assets.checkpoint_checksum is None
    assert not entry.assets.has_runtime_assets()


def test_model_zoo_metadata_should_publish_required_policies() -> None:
    """验证 registry 元数据包含 Model 计划要求的策略字段。"""
    from autovla.models import get_model_zoo_entry

    metadata = get_model_zoo_entry("gr00t-n1d6").to_metadata()

    for field in (
        "model_registry_key",
        "source_family",
        "release_reference",
        "native_chain_policy",
        "checkpoint_policy",
        "tokenizer_policy",
        "action_head_policy",
        "dataset_policy",
        "training_policy",
    ):
        assert field in metadata
    assert "download" in cast(str, metadata["checkpoint_policy"])
    assert "No tokenizer" in cast(str, metadata["tokenizer_policy"])
    assert "No training" in cast(str, metadata["training_policy"])


def test_gr00t_adapter_should_fail_closed_without_checkpoint_or_source() -> None:
    """验证缺少源码/checkpoint 时 skeleton 不会执行模型路径。"""
    from autovla.models import Gr00tN1D6AdapterSkeleton, ModelAssetsUnavailableError

    adapter = Gr00tN1D6AdapterSkeleton()

    with pytest.raises(ModelAssetsUnavailableError, match="source/checkpoint"):
        adapter.require_runtime_assets()
    with pytest.raises(ModelAssetsUnavailableError, match=r"forward.*source/checkpoint"):
        adapter.forward(cast(ModelInput, object()))
    with pytest.raises(ModelAssetsUnavailableError, match=r"predict_action.*source/checkpoint"):
        adapter.predict_action(cast(ModelInput, object()))
    assert isinstance(cast(object, adapter.metadata()), dict)


def test_gr00t_adapter_methods_should_keep_framework_shape() -> None:
    """验证 skeleton 方法签名仍面向 FrameworkProtocol 形状。"""
    from autovla.models import Gr00tN1D6AdapterSkeleton

    annotations = Gr00tN1D6AdapterSkeleton.forward.__annotations__
    predict_annotations = Gr00tN1D6AdapterSkeleton.predict_action.__annotations__

    assert annotations["batch"] == "ModelInput"
    assert annotations["return"] == "FrameworkOutput"
    assert predict_annotations["batch"] == "ModelInput"
    assert predict_annotations["return"] == "ActionChunk"
    assert FrameworkOutput is not None
    assert ActionChunk is not None


def test_model_import_should_not_load_heavy_runtime_modules() -> None:
    """验证模型动物园导入不会引入重型模型、下载或训练运行时。"""
    heavy_roots = {
        "torch",
        "transformers",
        "huggingface_hub",
        "wandb",
        "starVLA",
    }
    before = set(sys.modules)

    from autovla.models import build_gr00t_n1d6_adapter_skeleton

    build_gr00t_n1d6_adapter_skeleton()
    loaded = set(sys.modules) - before

    for root in heavy_roots:
        assert root not in loaded
        assert not any(module.startswith(f"{root}.") for module in loaded)


def test_pi_and_gr00t_candidates_should_be_visible_in_metadata_and_docs() -> None:
    """验证 PI/GR00T 路线图候选存在于元数据和文档中。"""
    from autovla.models import list_model_family_candidates

    candidates = list_model_family_candidates()
    strategy = Path("docs/architecture/MODEL_ZOO_AND_NATIVE_ADAPTER_STRATEGY.md")
    readiness = Path("docs/autovla/m3_zjh_gr00t_pipeline_readiness.md")
    strategy_text = strategy.read_text(encoding="utf-8")
    readiness_text = readiness.read_text(encoding="utf-8")

    assert "gr00t-n1d6" in candidates["gr00t"]
    assert "pi0-roadmap" in candidates["pi"]
    assert "GR00T-series" in strategy_text
    assert "PI-series" in strategy_text
    assert "gr00t-n1d6" in readiness_text
    assert "metadata-only" in readiness_text
