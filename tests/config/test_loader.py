"""GenesisVLA 配置加载器契约测试。"""

from pathlib import Path

import pytest


def _preset_path() -> Path:
    return Path("genesisvla/config/presets/local_debug.yaml")


def test_should_load_yaml_into_experiment_config() -> None:
    """验证本地调试 YAML 能加载为实验配置。"""
    from genesisvla.config.loader import load_yaml
    from genesisvla.config.schema import ExperimentConfig, RunnerBackend

    config = load_yaml(_preset_path())

    assert isinstance(config, ExperimentConfig)
    assert config.runner.backend is RunnerBackend.LOCAL


def test_should_apply_cli_dotlist_override() -> None:
    """验证 CLI dotlist 覆盖会返回新的后端枚举值。"""
    from genesisvla.config.loader import load_yaml
    from genesisvla.config.schema import RunnerBackend

    config = load_yaml(_preset_path(), overrides=("runner.backend=ddp",))

    assert config.runner.backend is RunnerBackend.DDP


def test_should_emit_clear_error_on_invalid_backend() -> None:
    """验证无效后端错误包含字段名和允许值。"""
    from genesisvla.config.loader import load_yaml

    with pytest.raises(
        ValueError,
        match=r"runner.backend.*local.*accelerate.*ddp.*fsdp.*deepspeed",
    ):
        load_yaml(_preset_path(), overrides=("runner.backend=invalid",))


def test_should_export_resolved_yaml(tmp_path: Path) -> None:
    """验证解析后的配置能导出并再次加载。"""
    from genesisvla.config.loader import export_resolved_yaml, load_yaml

    output_path = tmp_path / "resolved.yaml"
    config = load_yaml(_preset_path())
    export_resolved_yaml(config, output_path)
    reloaded = load_yaml(output_path)

    assert reloaded.schema_version == "1.0"
    assert reloaded.name == "local_debug"
    assert reloaded.runner.backend.value == "local"
