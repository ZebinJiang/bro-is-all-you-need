"""AutoVLA 分发版本、许可证和包内资源测试。"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


def test_package_metadata_matches_distribution_contract(monkeypatch) -> None:
    """验证版本、PEP 639、构建后端和依赖元数据。"""
    import autovla
    from autovla._version import __version__

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["name"] == "autovla"
    assert "authors" not in project["project"]
    assert project["project"]["license"] == (
        "MIT AND Apache-2.0 AND LicenseRef-NVIDIA-Isaac-GR00T-N1D6"
    )
    assert project["build-system"]["requires"] == ["setuptools==77.0.3"]
    assert (
        "diffusers>=0.30,<0.36"
        not in project["project"]["optional-dependencies"]["model-gr00t-n1d6"]
    )
    assert "pillow>=10,<12" in project["project"]["optional-dependencies"]["data-lerobot"]
    assert autovla.__version__ == __version__ == "0.1.0.dev0"
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "9.8.7")
    assert importlib.reload(autovla).__version__ == "9.8.7"
    monkeypatch.undo()
    assert importlib.reload(autovla).__version__ == __version__


def test_package_config_and_registry_imports_remain_torch_lazy_in_fresh_process() -> None:
    """在全新解释器中证明包、配置资源和注册表检查不加载 Torch。"""
    script = """
import sys
import autovla
from autovla.config.resources import config_resource
from autovla.models.registry import get_model_family_registration

assert config_resource("experiments", "local_debug").is_file()
assert get_model_family_registration("gr00t_n1d6").spec.family_key == "gr00t_n1d6"
assert "torch" not in sys.modules, sorted(name for name in sys.modules if name.startswith("torch"))
print(autovla.__version__)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0.dev0"


def test_gr00t_registry_capabilities_match_production_runtime_imports() -> None:
    """验证 GR00T 工厂能力声明不要求产品路径未导入的 diffusers。"""
    from autovla.models.registry import get_model_family_registration

    registration = get_model_family_registration("gr00t_n1d6")
    assert registration.factory is not None
    assert registration.factory.required_modules == (
        "PIL",
        "safetensors",
        "torch",
        "torchvision",
        "transformers",
    )
    assert "diffusers" not in registration.factory.required_modules


def test_packaged_resource_tree_and_named_composition_work_outside_cwd(
    tmp_path: Path,
) -> None:
    """验证五类包资源和命名实验组合不依赖 checkout cwd。"""
    from autovla.config import load_yaml
    from autovla.config.resources import config_resource

    for group, name in (
        ("data", "webdataset"),
        ("models", "gr00t_n1d6"),
        ("training", "single_device"),
        ("optimization", "adamw_cosine"),
        ("experiments", "gr00t_n1d6_webdataset"),
    ):
        assert config_resource(group, name).is_file()

    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        config = load_yaml("pkg://experiments/local_debug")
        gr00t = load_yaml("pkg://experiments/gr00t_n1d6_webdataset")
    finally:
        os.chdir(previous)
    assert config.name == "local_debug"
    assert gr00t.data.datasets[0].backend == "webdataset"
    assert gr00t.data.datasets[0].access_mode == "streaming"
    assert gr00t.data.datasets[0].stream_mode == "finite_epoch"
    assert gr00t.data.datasets[0].nominal_epoch_size == 1
    assert gr00t.data.datasets[0].root == "datasets/working/webdataset"
    assert gr00t.model.registry_key == "gr00t_n1d6"


def test_packaged_data_presets_declare_mode_and_local_root() -> None:
    """验证每个数据 preset 显式声明模式且只指向项目本地根。"""
    from autovla.config import load_yaml

    expected_modes = {
        "lerobot_local": "map",
        "local_debug": "map",
        "robodm_container": "map",
        "webdataset": "streaming",
    }
    for name, mode in expected_modes.items():
        resolved = load_yaml(f"pkg://data/{name}")
        dataset = resolved.data.datasets[0]
        assert dataset.access_mode == mode
        assert dataset.root.startswith("datasets/working/")
        if mode == "map":
            assert dataset.stream_mode is None
            assert dataset.nominal_epoch_size is None
        else:
            assert dataset.stream_mode == "finite_epoch"
            assert dataset.nominal_epoch_size == 1


def test_temporal_query_config_strict_parse_fingerprint_and_pickle() -> None:
    """验证时间查询从严格配置构造为不可变可 pickle 值。"""
    from autovla.config import TemporalQueryConfig, build_experiment_config
    from autovla.data.contracts import TemporalQuery

    payload = {
        "feature_key": "action",
        "feature_family": "action",
        "frame_offsets": [-1, 0],
        "timestamp_deltas": [0.1, 0.2],
        "anchor_semantics": "sample",
        "fps": 30.0,
        "tolerance": 0.02,
        "boundary_policy": "pad",
        "output_mask_semantics": "true_is_observed",
        "action_horizon": 4,
    }
    config = build_experiment_config(
        {
            "data": {
                "datasets": [
                    {
                        "name": "temporal-source",
                        "backend": "lerobot_local",
                        "root": "datasets/working/lerobot_local",
                        "sample_count": 4,
                        "temporal_query": payload,
                    }
                ]
            }
        }
    )
    query = config.data.datasets[0].temporal_query

    assert isinstance(query, TemporalQueryConfig)
    assert query.frame_offsets == (-1, 0)
    assert query.timestamp_deltas == (0.1, 0.2)
    assert query.to_dict() == payload
    assert pickle.loads(pickle.dumps(query)) == query
    assert pickle.loads(pickle.dumps(config.data.datasets[0])).temporal_query == query
    assert TemporalQueryConfig(**query.to_dict()).fingerprint == query.fingerprint
    assert TemporalQuery(**query.to_dict()).fingerprint == query.fingerprint


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        (
            {"feature_key": "state", "feature_family": "state"},
            "requires frame_offsets or timestamp_deltas",
        ),
        (
            {
                "feature_key": "state",
                "feature_family": "state",
                "frame_offsets": (0,),
                "timestamp_deltas": (0.1,),
                "anchor_semantics": "frame",
            },
            "mixed temporal coordinates require sample anchor semantics",
        ),
        (
            {
                "feature_key": "action",
                "feature_family": "action",
                "frame_offsets": (-1, 0, 1),
                "action_horizon": 2,
            },
            "size must equal action_horizon",
        ),
        (
            {
                "feature_key": "state",
                "feature_family": "state",
                "frame_offsets": (0,),
                "tolerance": 0.1,
            },
            "cannot set timestamp tolerance",
        ),
    ),
)
def test_temporal_query_config_rejects_ambiguous_combinations(
    kwargs: dict[str, object], message: str
) -> None:
    """验证空查询、混合 anchor 和未消费参数均 fail closed。"""
    from autovla.config import TemporalQueryConfig

    with pytest.raises(ValueError, match=message):
        TemporalQueryConfig(**kwargs)  # type: ignore[arg-type]


def test_root_local_debug_mirror_matches_packaged_authority() -> None:
    """验证开发 checkout 的兼容 preset 不偏离包内权威值。"""
    from autovla.config import load_yaml, to_resolved_dict

    packaged = to_resolved_dict(load_yaml("pkg://experiments/local_debug"))
    local = to_resolved_dict(load_yaml("autovla/config/presets/local_debug.yaml"))

    assert packaged == local


def test_train_cli_resolves_packaged_config_outside_cwd(tmp_path: Path, monkeypatch) -> None:
    """验证 train CLI 在组合运行时前已从安装包解析命名实验。"""
    from autovla.cli import train

    observed: dict[str, object] = {}

    class Engine:
        def fit(self) -> None:
            observed["fit"] = True

    def compose(config):
        observed["name"] = config.name
        return Engine()

    monkeypatch.setattr(train, "compose_training_engine", compose)
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert train.main(["pkg://experiments/local_debug"]) == 0
    finally:
        os.chdir(previous)
    assert observed == {"name": "local_debug", "fit": True}
