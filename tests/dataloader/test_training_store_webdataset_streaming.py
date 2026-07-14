"""WebDataset streaming PR18 backend 准备测试。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import pytest
import tomli

from autovla.dataloader.perf.webdataset_streaming_store import (
    WEBDATASET_STREAMING_FORMAT,
    TrainingStoreBackendRegistry,
    WebDatasetStreamingTrainingStoreBackend,
    describe_webdataset_dependency_status,
)


def test_webdataset_dependency_should_be_perf_scoped_and_quality_pinned() -> None:
    """验证质量工具与已批准 CPU 运行时 overlay 保持分层。"""
    pyproject = _string_mapping(tomli.loads(Path("pyproject.toml").read_text(encoding="utf-8")))
    project = _string_mapping(pyproject["project"])
    extras = _string_mapping(project["optional-dependencies"])
    quality_requirements = Path("requirements/quality/quality-requirements.txt").read_text(
        encoding="utf-8"
    )
    quality_constraints = Path("requirements/quality/quality-constraints.txt").read_text(
        encoding="utf-8"
    )
    runtime_overlay = Path("requirements/ci/m7-quality-runtime-overlay.txt").read_text(
        encoding="utf-8"
    )
    workflow = Path(".github/workflows/autovla.yml").read_text(encoding="utf-8")
    perf_dependencies = _string_list(extras["perf"])
    webdataset_dependencies = _string_list(extras["data-webdataset"])

    assert perf_dependencies == ["webdataset==1.0.2"]
    assert webdataset_dependencies == ["webdataset==1.0.2"]
    assert project["dependencies"] == ["numpy", "omegaconf"]
    assert extras["training"] == ["torch>=2.5,<2.7"]
    assert "webdataset\n" in quality_requirements
    assert "webdataset==1.0.2" in quality_constraints
    assert "braceexpand==0.1.7" in quality_constraints
    assert all("torch" not in dependency.lower() for dependency in perf_dependencies)
    assert all("torch" not in dependency.lower() for dependency in webdataset_dependencies)
    assert "torch" not in quality_requirements.lower()
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in runtime_overlay
    for dependency in (
        "pillow>=10,<12",
        "av>=16,<17",
        "safetensors>=0.4,<0.6",
        "torch==2.6.0+cpu",
        "torchvision==0.21.0+cpu",
        "transformers>=4.51.3,<4.52",
    ):
        assert dependency in runtime_overlay.splitlines()
    assert "192.168." not in runtime_overlay
    assert "m7-quality-runtime-overlay.txt" in workflow


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
    packages = _string_mapping(status["packages"])
    assert set(packages) == {"braceexpand", "webdataset"}
    assert status["classification"] in {"AVAILABLE", "DEPENDENCY_BLOCKED"}


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄 TOML 和状态动态映射。"""
    return isinstance(value, Mapping)


def _string_mapping(value: object) -> Mapping[str, object]:
    """校验映射键为字符串。"""
    if not _is_object_mapping(value):
        raise TypeError("expected string-key mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("mapping keys must be strings")
        result[key] = item
    return result


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """收窄 TOML 动态数组。"""
    return isinstance(value, list)


def _string_list(value: object) -> list[str]:
    """校验 TOML 依赖数组仅含字符串。"""
    if not _is_object_list(value) or not all(isinstance(item, str) for item in value):
        raise TypeError("expected dependency string list")
    return [item for item in value if isinstance(item, str)]


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
