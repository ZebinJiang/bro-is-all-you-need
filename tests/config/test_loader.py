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


def test_should_load_deployment_and_acceleration_sections() -> None:
    """验证 M1-lite 顶层配置接受 deployment 与 acceleration 段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    config = build_experiment_config(
        {
            "deployment": {"enabled": False, "timeout": 30.0},
            "acceleration": {"enabled": False, "mixed_precision": "none"},
        }
    )

    assert config.deployment.enabled is False
    assert config.deployment.timeout == 30.0
    assert config.acceleration.enabled is False
    assert config.acceleration.mixed_precision == "none"


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


def test_should_reject_non_string_name() -> None:
    """验证实验名称拒绝非字符串值,不做静默转换。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"name.*string"):
        build_experiment_config({"name": 123})


def test_should_reject_non_string_schema_version() -> None:
    """验证 schema_version 拒绝非字符串值,不做静默转换。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"schema_version.*string"):
        build_experiment_config({"schema_version": 1.0})


def test_should_reject_float_batch_size() -> None:
    """验证 batch_size 拒绝浮点数。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"runner.batch_size.*integer"):
        build_experiment_config({"runner": {"batch_size": 1.5}})


def test_should_reject_bool_batch_size() -> None:
    """验证 batch_size 拒绝 bool,避免 bool 被当作 int。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"runner.batch_size.*integer"):
        build_experiment_config({"runner": {"batch_size": True}})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("batch_size", 0, "runner.batch_size.*positive"),
        ("learning_rate", 0.0, "runner.learning_rate.*positive"),
        ("grad_accumulation_steps", 0, "runner.grad_accumulation_steps.*positive"),
        ("action_horizon", 0, "runner.action_horizon.*positive"),
        ("action_dim", 0, "runner.action_dim.*positive"),
        ("timeout", 0.0, "runner.timeout.*positive"),
    ),
)
def test_should_reject_invalid_runner_invariants(
    field: str,
    value: object,
    message: str,
) -> None:
    """验证 runner dataclass 不变量拒绝非正值。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=message):
        build_experiment_config({"runner": {field: value}})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("learning_rate", "fast", "runner.learning_rate.*number"),
        ("grad_accumulation_steps", 1.5, "runner.grad_accumulation_steps.*integer"),
        ("action_horizon", True, "runner.action_horizon.*integer"),
        ("action_dim", 1.5, "runner.action_dim.*integer"),
        ("timeout", "slow", "runner.timeout.*number"),
    ),
)
def test_should_reject_invalid_runner_invariant_types(
    field: str,
    value: object,
    message: str,
) -> None:
    """验证 runner dataclass 不变量拒绝错误类型。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=message):
        build_experiment_config({"runner": {field: value}})


def test_public_config_constructors_should_enforce_top_level_invariants() -> None:
    """验证 public dataclass 构造器不能绕过顶层不变量。"""
    from genesisvla.config.schema import DataConfig, ExperimentConfig, ModelConfig

    with pytest.raises(ValueError, match=r"name.*empty"):
        ExperimentConfig(name="")
    with pytest.raises(ValueError, match=r"seed.*integer"):
        ExperimentConfig(seed=True)
    with pytest.raises(ValueError, match=r"seed.*non-negative"):
        ExperimentConfig(seed=-1)
    with pytest.raises(ValueError, match=r"model.*ModelConfig"):
        ExperimentConfig(model=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"data.*DataConfig"):
        ExperimentConfig(data=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"model.name.*empty"):
        ModelConfig(name="")
    with pytest.raises(ValueError, match=r"data.required_modalities.*empty"):
        DataConfig(required_modalities=())


def test_public_config_constructors_should_enforce_runner_invariants() -> None:
    """验证 runner public dataclass 构造器执行同等不变量。"""
    from genesisvla.config.schema import RunnerConfig

    with pytest.raises(ValueError, match=r"runner.backend.*RunnerBackend"):
        RunnerConfig(backend="local")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"runner.batch_size.*positive"):
        RunnerConfig(batch_size=0)
    with pytest.raises(ValueError, match=r"runner.max_steps.*positive"):
        RunnerConfig(max_steps=0)
    with pytest.raises(ValueError, match=r"runner.learning_rate.*positive"):
        RunnerConfig(learning_rate=0.0)
    with pytest.raises(ValueError, match=r"runner.grad_accumulation_steps.*integer"):
        RunnerConfig(grad_accumulation_steps=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"runner.action_horizon.*positive"):
        RunnerConfig(action_horizon=0)
    with pytest.raises(ValueError, match=r"runner.action_dim.*positive"):
        RunnerConfig(action_dim=0)
    with pytest.raises(ValueError, match=r"runner.timeout.*number"):
        RunnerConfig(timeout="slow")  # type: ignore[arg-type]


def test_public_config_constructors_should_enforce_placeholder_invariants() -> None:
    """验证 deployment 与 acceleration 占位配置构造器不变量。"""
    from genesisvla.config.schema import AccelerationConfig, DeploymentConfig

    with pytest.raises(ValueError, match=r"deployment.enabled.*boolean"):
        DeploymentConfig(enabled="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"deployment.timeout.*positive"):
        DeploymentConfig(timeout=0.0)
    with pytest.raises(ValueError, match=r"acceleration.enabled.*boolean"):
        AccelerationConfig(enabled="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"acceleration.mixed_precision.*empty"):
        AccelerationConfig(mixed_precision="")


def test_should_reject_null_required_modality() -> None:
    """验证必需模态列表拒绝 null 条目。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"required_modalities\[1\].*string"):
        build_experiment_config({"data": {"required_modalities": ["front", None]}})


def test_should_reject_empty_required_modality_name() -> None:
    """验证必需模态列表拒绝空字符串名称。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"required_modalities\[0\].*empty"):
        build_experiment_config({"data": {"required_modalities": [""]}})


def test_should_reject_non_list_required_modalities() -> None:
    """验证必需模态字段拒绝非列表值。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match="list of strings"):
        build_experiment_config({"data": {"required_modalities": "front"}})


def test_should_reject_unknown_top_level_key() -> None:
    """验证顶层 YAML 拼写错误不会被静默忽略。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*typo"):
        build_experiment_config({"typo": True})


def test_should_reject_unknown_model_key() -> None:
    """验证模型段拒绝未知字段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*model.unknown"):
        build_experiment_config({"model": {"unknown": True}})


def test_should_reject_unknown_data_key() -> None:
    """验证数据段拒绝未知字段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*data.unknown"):
        build_experiment_config({"data": {"unknown": True}})


def test_should_reject_unknown_runner_key() -> None:
    """验证运行器段拒绝未知字段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*runner.unknown"):
        build_experiment_config({"runner": {"unknown": True}})


def test_should_reject_unknown_deployment_key() -> None:
    """验证 deployment 段拒绝未知字段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*deployment.unknown"):
        build_experiment_config({"deployment": {"unknown": True}})


def test_should_reject_unknown_acceleration_key() -> None:
    """验证 acceleration 段拒绝未知字段。"""
    from genesisvla.config.loader.validate import build_experiment_config

    with pytest.raises(ValueError, match=r"unknown config key.*acceleration.unknown"):
        build_experiment_config({"acceleration": {"unknown": True}})


def test_should_reject_typo_from_cli_override() -> None:
    """验证 CLI dotlist 覆盖拼写错误不会被静默合并。"""
    from genesisvla.config.loader import load_yaml

    with pytest.raises(
        ValueError,
        match=r"unknown config key.*runner.bach_size.*did you mean runner.batch_size",
    ):
        load_yaml(_preset_path(), overrides=("runner.bach_size=2",))
