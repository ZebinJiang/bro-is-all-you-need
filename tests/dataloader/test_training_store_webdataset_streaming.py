"""WebDataset streaming PR18 backend 准备测试。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from autovla.dataloader.perf.webdataset_streaming_store import (
    WEBDATASET_STREAMING_FORMAT,
    TrainingStoreBackendRegistry,
    WebDatasetStreamingTrainingStoreBackend,
    describe_webdataset_dependency_status,
)


def test_webdataset_dependency_should_be_perf_scoped_and_quality_pinned() -> None:
    """验证 PR18 只加入批准的 perf/quality WebDataset 依赖。"""
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    quality_requirements = Path("requirements/quality/quality-requirements.txt").read_text(
        encoding="utf-8"
    )
    quality_constraints = Path("requirements/quality/quality-constraints.txt").read_text(
        encoding="utf-8"
    )

    assert 'perf = ["webdataset==1.0.2"]' in pyproject
    assert "webdataset\n" in quality_requirements
    assert "webdataset==1.0.2" in quality_constraints
    assert "braceexpand==0.1.7" in quality_constraints
    assert "torch" not in pyproject.lower()
    assert "torch" not in quality_requirements.lower()


def test_webdataset_backend_registry_should_hide_raw_api() -> None:
    """验证 WebDataset backend 通过 AutoVLA registry 暴露。"""
    registry = TrainingStoreBackendRegistry.with_default_backends()
    backend = registry.get(WEBDATASET_STREAMING_FORMAT)
    description = backend.describe()

    assert backend.backend_name == "webdataset_streaming_v1"
    assert description["dependency_mode"] == "webdataset_package"
    assert description["raw_webdataset_api_exposed"] is False
    assert description["action_state_mask_only_supported"] is True
    assert description["full_training_window_supported"] is False


def test_webdataset_dependency_status_should_be_fail_closed() -> None:
    """验证 WebDataset dependency 状态 JSON-safe 且缺失时可阻塞。"""
    status = describe_webdataset_dependency_status()

    assert status["backend"] == "webdataset_streaming_v1"
    assert status["dependency_mode"] == "webdataset_package"
    packages = cast(dict[str, object], status["packages"])
    assert isinstance(packages, dict)
    assert set(packages) == {"braceexpand", "webdataset"}
    assert status["classification"] in {"AVAILABLE", "DEPENDENCY_BLOCKED"}


def test_webdataset_backend_should_reject_external_or_source_root_outputs(
    tmp_path: Path,
) -> None:
    """验证 URL、pipe 和 source root 内输出 fail-closed。"""
    backend = WebDatasetStreamingTrainingStoreBackend()
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    with pytest.raises(ValueError, match="local filesystem"):
        backend.validate_source("https://example.invalid/dataset")
    with pytest.raises(ValueError, match="local filesystem"):
        backend.validate_source("pipe:curl https://example.invalid/data.tar")
    with pytest.raises(ValueError, match="dataset root"):
        backend.validate_store_target(source=dataset, output=dataset / "store")
