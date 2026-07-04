"""AutoVLA 模型族契约测试。"""

from __future__ import annotations

import sys

import numpy as np
import pytest

from autovla.models import Gr00tN1D6DryRunBatchAdapter, get_model_family_spec
from autovla.models.registry import get, list_model_family_keys
from autovla.training.contracts import TrainingBatch


def _batch(camera_count: int = 3) -> TrainingBatch:
    """构造 GR00T dry-run adapter 使用的通用 TrainingBatch。"""
    actions = np.ones((1, 2, 3), dtype=np.float32)
    return TrainingBatch(
        images={
            f"camera_{index}": np.zeros((1, 4, 4, 3), dtype=np.float32)
            for index in range(camera_count)
        },
        language=("move arm",),
        actions=actions,
        action_mask=np.ones_like(actions, dtype=np.bool_),
        state=np.zeros((1, 7), dtype=np.float32),
        sample_source=({"episode": "e0"},),
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="stats",
    )


def test_model_family_registry_should_return_gr00t_metadata_without_heavy_imports() -> None:
    """验证 registry lookup 不导入重型运行时。"""
    heavy_roots = {"torch", "transformers", "gr00t", "jax", "flax", "wandb", "huggingface_hub"}
    before = set(sys.modules)

    spec = get("gr00t-n1d6")
    spec_via_alias = get_model_family_spec("gr00t-n1d6")
    loaded = set(sys.modules) - before

    assert spec is spec_via_alias
    assert spec.family_key == "gr00t-n1d6"
    assert spec.no_weight_load is True
    assert spec.no_tokenizer_load is True
    assert spec.no_network is True
    assert spec.license.weight_license_status == "requires_model_license_review"
    for root in heavy_roots:
        assert root not in loaded
        assert not any(module.startswith(f"{root}.") for module in loaded)


def test_model_family_registry_should_reject_unknown_key() -> None:
    """验证未知模型族 fail closed。"""
    with pytest.raises(KeyError, match="unknown model family"):
        get("missing-family")


def test_gr00t_dryrun_adapter_should_validate_camera_policy_and_emit_model_input() -> None:
    """验证 GR00T dry-run adapter 只做无 IO 转换。"""
    adapter = Gr00tN1D6DryRunBatchAdapter(expected_camera_count=3)
    model_input = adapter.to_model_input(_batch())

    assert model_input.metadata["family_key"] == "gr00t-n1d6"
    assert model_input.metadata["action_horizon"] == 2
    assert model_input.metadata["action_dim"] == 3
    assert len(model_input.batch.samples) == 1
    assert set(model_input.tensors) == {
        "actions",
        "image.camera_0",
        "image.camera_1",
        "image.camera_2",
        "state",
    }

    with pytest.raises(ValueError, match="camera views"):
        adapter.to_model_input(_batch(camera_count=2))


def test_pi_roadmap_families_should_be_metadata_only_without_jax_import() -> None:
    """验证 π/OpenPI 族保持 roadmap-only 且不导入 JAX/Flax。"""
    before = set(sys.modules)
    keys = list_model_family_keys()

    assert "pi0-roadmap" in keys
    assert "pi0-fast-roadmap" in keys
    assert "pi05-roadmap" in keys
    for key in ("pi0-roadmap", "pi0-fast-roadmap", "pi05-roadmap"):
        spec = get(key)
        assert spec.runtime_status == ("roadmap_only", "no_import")
        assert spec.license.code_license_status == "requires_upstream_verification"
        assert spec.no_weight_load is True
    loaded = set(sys.modules) - before
    assert "jax" not in loaded
    assert "flax" not in loaded
