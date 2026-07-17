"""AutoVLA 分发版本、许可证和包内资源测试。"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import pickle
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypeGuard

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from autovla.config.schema import TemporalQueryConfig


def test_package_metadata_matches_distribution_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证版本、PEP 639、构建后端和依赖元数据。"""
    import autovla
    from autovla._version import __version__

    payload = _toml_table(tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8")))
    project = _toml_table(payload["project"])
    build_system = _toml_table(payload["build-system"])
    optional = _toml_table(project["optional-dependencies"])
    assert project["name"] == "autovla"
    assert "authors" not in project
    assert project["license"] == ("MIT AND Apache-2.0 AND LicenseRef-NVIDIA-Isaac-GR00T-N1D6")
    assert build_system["requires"] == ["setuptools==77.0.3"]
    assert "diffusers>=0.30,<0.36" not in _object_list(optional["model-gr00t-n1d6"])
    assert "pillow>=10,<12" in _object_list(optional["data-lerobot"])
    assert "av>=16,<17" in _object_list(optional["data-lerobot"])
    assert _object_list(optional["asset-acquisition"]) == ["huggingface_hub==0.30.2"]
    assert _object_list(optional["training-deepspeed"]) == [
        "deepspeed==0.19.2",
        "torch>=2.5,<2.7",
    ]
    scripts = _toml_table(project["scripts"])
    assert scripts["autovla-assets"] == "autovla.cli.assets:main"
    assert autovla.__version__ == __version__ == "0.1.0.dev0"

    def fixed_version(_name: str) -> str:
        """返回测试分发版本。"""
        return "9.8.7"

    monkeypatch.setattr(importlib.metadata, "version", fixed_version)
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

assert config_resource("experiments", "m9_gr00t_gpu_architecture").is_file()
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
        ("models", "gr00t_n1d7"),
        ("models", "pi0_5"),
        ("environments", "a100"),
        ("training", "single_gpu"),
        ("optimization", "adamw_cosine"),
        ("experiments", "gr00t_n1d6_webdataset"),
        ("experiments", "m9_gr00t_gpu_architecture"),
    ):
        assert config_resource(group, name).is_file()

    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        config = load_yaml("pkg://experiments/m9_gr00t_gpu_architecture")
        gr00t = load_yaml("pkg://experiments/gr00t_n1d6_webdataset")
    finally:
        os.chdir(previous)
    assert config.name == "m9_gr00t_gpu_architecture"
    assert config.model.registry_key == "gr00t_n1d6"
    assert config.model.action_horizon == 50
    assert config.model.max_state_dim == 128
    assert config.model.max_action_dim == 128
    assert config.topology.distributed.strategy_key == "single_gpu"
    assert config.topology.distributed.device == "cuda"
    assert gr00t.data.datasets[0].backend == "webdataset"
    assert gr00t.data.datasets[0].access_mode == "streaming"
    assert gr00t.data.datasets[0].stream_mode == "finite_epoch"
    assert gr00t.data.datasets[0].nominal_epoch_size == 1
    assert gr00t.data.datasets[0].root == "datasets/working/webdataset"
    assert gr00t.model.registry_key == "gr00t_n1d6"
    assert gr00t.environment.gpu_architecture == "a100"
    assert gr00t.environment.slurm_partition == "a100"
    assert gr00t.environment.environment_fingerprint_schema.endswith(".v1")


def test_root_and_packaged_a100_environment_mirrors_match() -> None:
    """验证 checkout 与 wheel 资源声明同一 A100 约束和待采集指纹。"""

    from autovla.config import compose_mapping

    packaged = compose_mapping("pkg://environments/a100")["environment"]
    local = compose_mapping("configs/environments/a100.yaml")["environment"]

    assert packaged == local
    assert packaged["runtime_fingerprint_status"] == (
        "locks_and_fingerprints_collected_runtime_deferred"
    )
    assert packaged["declared_environment_status"] == (
        "locked_profiles_bounded_pre_cuda_validation_only"
    )


def test_packaged_data_presets_declare_mode_and_local_root() -> None:
    """验证每个数据 preset 显式声明模式且只指向项目本地根。"""
    from autovla.config import load_yaml

    expected_modes = {
        "lerobot_local": "map",
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
    rebuilt_config = TemporalQueryConfig(
        feature_key=query.feature_key,
        feature_family=query.feature_family,
        frame_offsets=query.frame_offsets,
        timestamp_deltas=query.timestamp_deltas,
        anchor_semantics=query.anchor_semantics,
        fps=query.fps,
        tolerance=query.tolerance,
        boundary_policy=query.boundary_policy,
        output_mask_semantics=query.output_mask_semantics,
        action_horizon=query.action_horizon,
    )
    rebuilt_query = TemporalQuery(
        feature_key=query.feature_key,
        feature_family=query.feature_family,
        frame_offsets=query.frame_offsets,
        timestamp_deltas=query.timestamp_deltas,
        anchor_semantics=query.anchor_semantics,
        fps=query.fps,
        tolerance=query.tolerance,
        boundary_policy=query.boundary_policy,
        output_mask_semantics=query.output_mask_semantics,
        action_horizon=query.action_horizon,
    )
    assert rebuilt_config.fingerprint == query.fingerprint
    assert rebuilt_query.fingerprint == query.fingerprint


@pytest.mark.parametrize(
    ("factory", "message"),
    (
        (
            lambda: TemporalQueryConfig(feature_key="state", feature_family="state"),
            "requires frame_offsets or timestamp_deltas",
        ),
        (
            lambda: TemporalQueryConfig(
                feature_key="state",
                feature_family="state",
                frame_offsets=(0,),
                timestamp_deltas=(0.1,),
                anchor_semantics="frame",
            ),
            "mixed temporal coordinates require sample anchor semantics",
        ),
        (
            lambda: TemporalQueryConfig(
                feature_key="action",
                feature_family="action",
                frame_offsets=(-1, 0, 1),
                action_horizon=2,
            ),
            "size must equal action_horizon",
        ),
        (
            lambda: TemporalQueryConfig(
                feature_key="state",
                feature_family="state",
                frame_offsets=(0,),
                tolerance=0.1,
            ),
            "cannot set timestamp tolerance",
        ),
    ),
)
def test_temporal_query_config_rejects_ambiguous_combinations(
    factory: Callable[[], TemporalQueryConfig], message: str
) -> None:
    """验证空查询、混合 anchor 和未消费参数均 fail closed。"""
    with pytest.raises(ValueError, match=message):
        factory()


def test_default_inspection_uses_professional_gpu_architecture_preset() -> None:
    """验证默认检查入口稳定解析 M9 GPU-only 规范资源。"""
    from autovla.cli.inspect_config import build_parser
    from autovla.config import load_yaml
    from autovla.config.resources import DEFAULT_EXPERIMENT

    assert DEFAULT_EXPERIMENT == "pkg://experiments/m9_gr00t_gpu_architecture"
    assert build_parser().parse_args([]).config == DEFAULT_EXPERIMENT
    config = load_yaml(DEFAULT_EXPERIMENT)
    assert config.name == "m9_gr00t_gpu_architecture"
    assert config.topology.distributed.device == "cuda"


def test_train_cli_resolves_packaged_config_outside_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 train CLI 在组合运行时前已从安装包解析命名实验。"""
    from autovla.cli import train

    observed: dict[str, object] = {}

    class Engine:
        def fit(self) -> None:
            observed["fit"] = True

    from autovla.config import ExperimentConfig

    def compose(config: ExperimentConfig) -> Engine:
        observed["name"] = config.name
        return Engine()

    monkeypatch.setattr(train, "compose_training_engine", compose)
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert train.main(["pkg://experiments/m9_gr00t_gpu_architecture"]) == 0
    finally:
        os.chdir(previous)
    assert observed == {"name": "m9_gr00t_gpu_architecture", "fit": True}


def test_train_cli_requires_explicit_config() -> None:
    """生产训练入口不把检查 preset 暴露为训练默认值。"""

    from autovla.cli.train import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args([])
    action = next(item for item in build_parser()._actions if item.dest == "config")
    assert action.required is True
    assert action.default is None


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄 TOML 动态映射。"""
    return isinstance(value, Mapping)


def _toml_table(value: object) -> dict[str, object]:
    """验证 TOML table 使用字符串键。"""
    if not _is_object_mapping(value):
        raise TypeError("expected TOML table")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("TOML table keys must be strings")
        result[key] = item
    return result


def _object_list(value: object) -> list[object]:
    """验证 TOML array 并固定元素边界。"""
    if not _is_object_list(value):
        raise TypeError("expected TOML array")
    return value


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """收窄 TOML 动态数组。"""
    return isinstance(value, list)
