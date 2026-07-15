"""R5 local-only inference 和部署相邻契约。"""

from pathlib import Path

import numpy as np
import pytest

from autovla.core.types.training import TrainingBatch
from autovla.deployment import DeploymentSpec, ExportManifest, RuntimeCompatibilityReport
from autovla.inference import InferenceRequest, PolicyBundle, PolicyBundleManifest


def _batch() -> TrainingBatch:
    """构造最小 canonical batch。"""
    return TrainingBatch(
        images={"front": np.zeros((1, 2, 2, 3), dtype=np.float32)},
        language=("pick",),
        actions=np.zeros((1, 2, 2), dtype=np.float32),
        action_mask=np.ones((1, 2, 2), dtype=np.bool_),
        sample_source=({"dataset": "local"},),
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="stats",
    )


def test_policy_bundle_references_assets_without_copying() -> None:
    """bundle 仅持有本地 manifest/asset 引用且请求复用 canonical batch。"""
    manifest = PolicyBundleManifest(
        family_key="gr00t_n1d6",
        family_config_fingerprint="family",
        asset_manifest_fingerprint="assets",
        checkpoint_manifest_fingerprint="checkpoint",
        processor_fingerprint="processor",
        transform_fingerprint="transform",
        capability_fingerprint="capability",
        action_decode_fingerprint="decode",
        device="cuda",
        precision="bfloat16",
        provenance={"source": "local"},
    )
    bundle = PolicyBundle(
        manifest,
        Path("/project/runs/checkpoint/manifest.json"),
        Path("/project/base_model"),
    )
    request = InferenceRequest("request", _batch(), "processor", "transform")
    assert bundle.fingerprint == manifest.fingerprint
    assert request.batch.transform_fingerprint == "transform"


def test_deployment_contracts_reject_remote_targets() -> None:
    """部署相邻契约不接受 server/robot/endpoint。"""
    spec = DeploymentSpec("local_cuda_bundle_check")
    export = ExportManifest("bundle", spec.fingerprint, "manifest_only", "runs/export.json")
    report = RuntimeCompatibilityReport(True, "bundle", spec.fingerprint)
    assert export.artifact_reference.startswith("runs/") and report.compatible
    with pytest.raises(ValueError):
        DeploymentSpec("robot_server")
    with pytest.raises(ValueError):
        ExportManifest("bundle", "spec", "format", "https://example.invalid/model")
