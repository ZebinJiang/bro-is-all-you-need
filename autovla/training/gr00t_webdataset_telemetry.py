"""GR00T N1.6 WebDataset telemetry dry-run 的 fail-closed scaffold。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

GR00T_TELEMETRY_CONFIG_SCHEMA_VERSION = "autovla.gr00t_webdataset_telemetry_dryrun.v1"
GR00T_TELEMETRY_REPORT_SCHEMA_VERSION = "autovla.gr00t_webdataset_telemetry_report.v1"
GR00T_TELEMETRY_MODE = "gr00t-n1d6-webdataset-telemetry-dryrun"
GR00T_MODEL_REGISTRY_KEY = "gr00t-n1d6"
GR00T_REQUIRED_PROFILE = "model-gr00t-n1d6"
GR00T_TELEMETRY_REPORT_FILENAME = "gr00t_webdataset_telemetry_report.json"
MAX_TELEMETRY_STEPS = 20
_COMPUTE_NODE_ENV = "AUTOVLA_COMPUTE_NODE_VALIDATION"
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REQUIRED_OFFLINE_ENV = {
    "AUTOVLA_NO_NETWORK": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}
_WANDB_DISABLED_VALUES = {"1", "true", "disabled"}
_EXTERNAL_EFFECTS_FALSE = {
    "checkpoint_write": False,
    "checkpoint_weight_read": False,
    "endpoint": False,
    "hf_network": False,
    "model_load": False,
    "real_training": False,
    "robot": False,
    "slurm_submit": False,
    "source_dataset_mutation": False,
    "tokenizer_load": False,
    "wandb_network": False,
}
_MISSING_RUNTIME_METRICS = [
    "model_runtime_import",
    "gpu_memory",
    "forward_latency_ms",
    "backward_latency_ms",
    "optimizer_step_latency_ms",
]
_YAML_LIST_FIELDS = {
    "allowed_commands",
    "config_files",
    "expected_assets",
    "forbidden_commands",
    "missing_files",
    "tokenizer_or_processor_files",
}


class Gr00tTelemetryConfigError(ValueError):
    """表示 GR00T telemetry scaffold 输入不满足 fail-closed 契约。"""


@dataclass(frozen=True, slots=True)
class Gr00tWebDatasetTelemetryConfig:
    """GR00T N1.6 WebDataset telemetry dry-run 的严格配置。"""

    schema_version: str
    run_id: str
    mode: str
    max_steps: int
    environment_profile: str
    uv_project: str
    offline: bool
    dataset_root: Path
    webdataset_store: Path
    gr00t_source_root: Path
    checkpoint_path: Path
    output_root: Path
    checkpoint_write: bool
    hf_network: bool
    wandb_network: bool
    compute_node_model_load_only: bool

    def __post_init__(self) -> None:
        """校验配置对象构造入口, 避免测试绕过 YAML loader。"""
        if self.schema_version != GR00T_TELEMETRY_CONFIG_SCHEMA_VERSION:
            raise Gr00tTelemetryConfigError("schema_version is unsupported")
        _validate_run_id(self.run_id)
        if self.mode != GR00T_TELEMETRY_MODE:
            raise Gr00tTelemetryConfigError("mode must be gr00t-n1d6-webdataset-telemetry-dryrun")
        _require_exact_int(self.max_steps, "max_steps")
        if self.max_steps > MAX_TELEMETRY_STEPS:
            raise Gr00tTelemetryConfigError("max_steps must be <= 20")
        if self.environment_profile != GR00T_REQUIRED_PROFILE:
            raise Gr00tTelemetryConfigError("environment.profile must be model-gr00t-n1d6")
        if self.uv_project != "envs/model-gr00t-n1d6":
            raise Gr00tTelemetryConfigError("environment.uv_project must be envs/model-gr00t-n1d6")
        if self.offline is not True:
            raise Gr00tTelemetryConfigError("environment.offline must be true")
        for field, path in (
            ("dataset_root", self.dataset_root),
            ("webdataset_store", self.webdataset_store),
            ("gr00t_source_root", self.gr00t_source_root),
            ("checkpoint", self.checkpoint_path),
            ("output_root", self.output_root),
        ):
            _validate_local_path(path, field)
        if self.checkpoint_write is not False:
            raise Gr00tTelemetryConfigError("checkpoint_write must be false")
        if self.hf_network is not False:
            raise Gr00tTelemetryConfigError("hf_network must be false")
        if self.wandb_network is not False:
            raise Gr00tTelemetryConfigError("wandb_network must be false")
        if self.compute_node_model_load_only is not True:
            raise Gr00tTelemetryConfigError("compute_node_model_load_only must be true")

    def with_output_root(self, output_root: str | Path) -> "Gr00tWebDatasetTelemetryConfig":
        """返回带 CLI output root 覆盖的新配置。"""
        return replace(self, output_root=_path_from_string(str(output_root), "output_root"))


def load_gr00t_telemetry_config(path: str | Path) -> Gr00tWebDatasetTelemetryConfig:
    """加载受控 YAML 子集 telemetry 配置。"""
    data = _parse_simple_yaml(Path(path))
    environment = _required_mapping(data, "environment")
    paths = _required_mapping(data, "paths")
    policy = _required_mapping(data, "policy")
    return Gr00tWebDatasetTelemetryConfig(
        schema_version=_required_string(data, "schema_version"),
        run_id=_required_string(data, "run_id"),
        mode=_required_string(data, "mode"),
        max_steps=_required_int(data, "max_steps"),
        environment_profile=_required_string(environment, "profile"),
        uv_project=_required_string(environment, "uv_project"),
        offline=_required_bool(environment, "offline"),
        dataset_root=_path_from_string(_required_string(paths, "dataset_root"), "dataset_root"),
        webdataset_store=_path_from_string(
            _required_string(paths, "webdataset_store"),
            "webdataset_store",
        ),
        gr00t_source_root=_path_from_string(
            _required_string(paths, "gr00t_source_root"),
            "gr00t_source_root",
        ),
        checkpoint_path=_path_from_string(_required_string(paths, "checkpoint"), "checkpoint"),
        output_root=_path_from_string(_required_string(paths, "output_root"), "output_root"),
        checkpoint_write=_required_bool(policy, "checkpoint_write"),
        hf_network=_required_bool(policy, "hf_network"),
        wandb_network=_required_bool(policy, "wandb_network"),
        compute_node_model_load_only=_required_bool(policy, "compute_node_model_load_only"),
    )


def check_env_gate(
    config: Gr00tWebDatasetTelemetryConfig,
    *,
    profile_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """校验离线环境变量和 model-special profile 治理。"""
    env = os.environ if environ is None else environ
    _validate_offline_environment(env)
    root = _repo_root() / "configs/env/profiles" if profile_root is None else profile_root
    profile_path = root / f"{config.environment_profile}.yaml"
    profile = _parse_simple_yaml(profile_path)
    if _required_string(profile, "profile_id") != GR00T_REQUIRED_PROFILE:
        raise Gr00tTelemetryConfigError("env profile must be model-gr00t-n1d6")
    if _required_string(profile, "uv_project") != config.uv_project:
        raise Gr00tTelemetryConfigError("env profile uv_project mismatch")
    if _required_string(profile, "dependency_tier") != "model":
        raise Gr00tTelemetryConfigError("env profile dependency_tier must be model")
    if _required_bool(profile, "requires_manual_authorization") is not True:
        raise Gr00tTelemetryConfigError("model profile must require manual authorization")
    forbidden = _required_string_list(profile, "forbidden_commands")
    if "sync-profile" not in forbidden:
        raise Gr00tTelemetryConfigError("model profile must forbid sync-profile")
    return {
        "dependency_tier": "model",
        "install_status": _required_string(profile, "install_status"),
        "offline_environment": True,
        "profile": GR00T_REQUIRED_PROFILE,
        "requires_manual_authorization": True,
        "sync_profile_allowed": False,
        "uv_project": config.uv_project,
    }


def check_data_gate(config: Gr00tWebDatasetTelemetryConfig) -> dict[str, object]:
    """校验 WebDataset store manifest, 不读取 shard payload。"""
    manifest_path = config.webdataset_store / "webdataset_store_manifest.json"
    manifest = _read_json_object(manifest_path)
    if manifest.get("schema_version") != "autovla.data_format_pipeline.v1":
        raise Gr00tTelemetryConfigError("webdataset manifest schema_version is unsupported")
    if manifest.get("format_name") != "webdataset_native":
        raise Gr00tTelemetryConfigError("webdataset manifest format_name must be webdataset_native")
    if manifest.get("build_status") != "PASS":
        raise Gr00tTelemetryConfigError("webdataset manifest build_status must be PASS")
    effects = manifest.get("external_effects")
    if isinstance(effects, Mapping):
        effect_map = cast(Mapping[str, object], effects)
        for key in (
            "checkpoint_load",
            "hf_network",
            "model_load",
            "real_training",
            "source_dataset_mutation",
            "tokenizer_load",
            "wandb_network",
        ):
            if effect_map.get(key) is not False:
                raise Gr00tTelemetryConfigError(f"webdataset external effect must be false: {key}")
    sample_count = _manifest_positive_int(manifest, "sample_count")
    worker_count = _manifest_positive_int(manifest, "worker_count")
    action_dim = _manifest_positive_int(manifest, "action_dim")
    state_dim = _manifest_positive_int(manifest, "state_dim")
    return {
        "action_dim": action_dim,
        "action_mask_policy": str(manifest.get("action_mask_policy", "missing")),
        "format_name": "webdataset_native",
        "manifest_path": manifest_path.as_posix(),
        "sample_count": sample_count,
        "source_dataset_fingerprint": str(manifest.get("source_dataset_fingerprint", "missing")),
        "state_dim": state_dim,
        "worker_count": worker_count,
    }


def check_checkpoint_manifest(
    config: Gr00tWebDatasetTelemetryConfig,
    manifest_path: str | Path,
) -> dict[str, object]:
    """校验 GR00T checkpoint candidate manifest, 不读取权重或 tokenizer。"""
    path = Path(manifest_path)
    manifest = _read_json_object(path)
    if manifest.get("model_registry_key") != GR00T_MODEL_REGISTRY_KEY:
        raise Gr00tTelemetryConfigError("checkpoint model_registry_key must be gr00t-n1d6")
    if manifest.get("completeness_status") != "complete":
        raise Gr00tTelemetryConfigError("checkpoint completeness_status must be complete")
    if manifest.get("local_only") is not True:
        raise Gr00tTelemetryConfigError("checkpoint manifest local_only must be true")
    if manifest.get("no_download") is not True:
        raise Gr00tTelemetryConfigError("checkpoint manifest no_download must be true")
    if manifest.get("no_network") is not True:
        raise Gr00tTelemetryConfigError("checkpoint manifest no_network must be true")
    missing = manifest.get("missing_files")
    if missing != []:
        raise Gr00tTelemetryConfigError("checkpoint manifest missing_files must be empty")
    checkpoint_path = _required_string(manifest, "checkpoint_path")
    if Path(checkpoint_path) != config.checkpoint_path:
        raise Gr00tTelemetryConfigError("checkpoint manifest path does not match config")
    tokenizer_files = manifest.get("tokenizer_or_processor_files")
    tokenizer_or_processor_present = False
    if isinstance(tokenizer_files, list):
        tokenizer_or_processor_present = len(cast(list[object], tokenizer_files)) > 0
    return {
        "checkpoint_manifest_path": path.as_posix(),
        "checkpoint_path": checkpoint_path,
        "completeness_status": "complete",
        "local_only": True,
        "model_registry_key": GR00T_MODEL_REGISTRY_KEY,
        "no_download": True,
        "no_network": True,
        "source_project_path": str(manifest.get("source_project_path", "missing")),
        "tokenizer_or_processor_present": tokenizer_or_processor_present,
    }


def build_telemetry_report(
    config: Gr00tWebDatasetTelemetryConfig,
    *,
    env_gate: Mapping[str, object],
    data_gate: Mapping[str, object],
    checkpoint_gate: Mapping[str, object],
    compute_node: bool,
) -> dict[str, object]:
    """构造 deterministic telemetry gate report, 不触发真实 runtime。"""
    classification = (
        "READY_FOR_COMPUTE_MODEL_RUNTIME_GATE"
        if compute_node
        else "BLOCKED_MODEL_RUNTIME_LOGIN_NODE"
    )
    return {
        "checkpoint_manifest": dict(checkpoint_gate),
        "checkpoint_weight_read_attempted": False,
        "checkpoint_write": False,
        "classification": classification,
        "compute_node": compute_node,
        "data_gate": dict(data_gate),
        "env_gate": dict(env_gate),
        "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
        "fine_tune_readiness": False,
        "max_steps": config.max_steps,
        "metrics": {
            "completion_ratio": "missing",
            "data_wait_proxy_ms": "not_observed",
            "forward_latency_ms": "not_observed",
            "gpu_memory": "not_observed",
            "observed_completed_steps": "not_observed",
            "planned_max_steps": config.max_steps,
        },
        "missing_metrics": list(_MISSING_RUNTIME_METRICS),
        "mode": GR00T_TELEMETRY_MODE,
        "model_load_attempted": False,
        "model_registry_key": GR00T_MODEL_REGISTRY_KEY,
        "network_policy": {
            "autovla_no_network": True,
            "hf_hub_offline": True,
            "transformers_offline": True,
            "wandb_disabled": True,
        },
        "output_root": config.output_root.as_posix(),
        "package_name": "autovla",
        "real_training": False,
        "run_id": config.run_id,
        "schema_version": GR00T_TELEMETRY_REPORT_SCHEMA_VERSION,
        "tokenizer_load_attempted": False,
        "webdataset_store": config.webdataset_store.as_posix(),
    }


def write_telemetry_report(report: Mapping[str, object], output_path: Path) -> Path:
    """写入稳定 JSON report 并执行 roundtrip 校验。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output_path.write_text(text, encoding="utf-8")
    loaded: object = json.loads(output_path.read_text(encoding="utf-8"))
    if loaded != dict(report):
        raise RuntimeError("telemetry report roundtrip failed")
    return output_path


def render_slurm_command(
    config: Gr00tWebDatasetTelemetryConfig,
    *,
    config_path: Path,
    checkpoint_manifest_path: Path,
) -> dict[str, object]:
    """渲染 compute-node 运行命令, 不提交 Slurm。"""
    return {
        "argv": [
            sys.executable,
            "-m",
            "autovla.training.gr00t_webdataset_telemetry",
            "run-dryrun",
            "--config",
            config_path.as_posix(),
            "--checkpoint-manifest",
            checkpoint_manifest_path.as_posix(),
            "--require-compute-node",
        ],
        "checkpoint_write": False,
        "environment": {
            "AUTOVLA_NO_NETWORK": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "WANDB_DISABLED": "true",
        },
        "max_steps": config.max_steps,
        "mode": GR00T_TELEMETRY_MODE,
        "real_training": False,
    }


def run_dryrun(
    config: Gr00tWebDatasetTelemetryConfig,
    *,
    checkpoint_manifest_path: Path,
    require_compute_node: bool,
) -> Path:
    """执行 metadata-only dry-run gate, 不加载 GR00T runtime。"""
    compute_node = _is_compute_node()
    if require_compute_node and not compute_node:
        raise Gr00tTelemetryConfigError("model runtime load is compute-node-only")
    env_gate = check_env_gate(config)
    data_gate = check_data_gate(config)
    checkpoint_gate = check_checkpoint_manifest(config, checkpoint_manifest_path)
    report = build_telemetry_report(
        config,
        env_gate=env_gate,
        data_gate=data_gate,
        checkpoint_gate=checkpoint_gate,
        compute_node=compute_node,
    )
    return write_telemetry_report(
        report,
        config.output_root / config.run_id / GR00T_TELEMETRY_REPORT_FILENAME,
    )


def build_parser() -> argparse.ArgumentParser:
    """构造 GR00T telemetry scaffold CLI。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.gr00t_webdataset_telemetry",
        description="Fail-closed GR00T N1.6 WebDataset telemetry dry-run scaffold.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "validate-config",
        "check-env",
        "check-data",
        "check-checkpoint",
        "render-slurm-command",
        "run-dryrun",
    ):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True)
        subparser.add_argument("--output-root")
        if command in {"check-checkpoint", "render-slurm-command", "run-dryrun"}:
            subparser.add_argument("--checkpoint-manifest", required=True)
        if command == "run-dryrun":
            subparser.add_argument("--require-compute-node", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行 GR00T telemetry scaffold CLI。"""
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        config_path = Path(cast(str, args.config))
        config = load_gr00t_telemetry_config(config_path)
        output_root = cast(str | None, getattr(args, "output_root", None))
        if output_root is not None:
            config = config.with_output_root(output_root)
        command = cast(str, args.command)
        if command == "validate-config":
            payload: Mapping[str, object] = {"max_steps": config.max_steps, "status": "ok"}
        elif command == "check-env":
            payload = check_env_gate(config)
        elif command == "check-data":
            payload = check_data_gate(config)
        elif command == "check-checkpoint":
            payload = check_checkpoint_manifest(config, Path(cast(str, args.checkpoint_manifest)))
        elif command == "render-slurm-command":
            payload = render_slurm_command(
                config,
                config_path=config_path,
                checkpoint_manifest_path=Path(cast(str, args.checkpoint_manifest)),
            )
        elif command == "run-dryrun":
            report_path = run_dryrun(
                config,
                checkpoint_manifest_path=Path(cast(str, args.checkpoint_manifest)),
                require_compute_node=bool(cast(bool, args.require_compute_node)),
            )
            payload = {
                "classification": json.loads(report_path.read_text(encoding="utf-8"))[
                    "classification"
                ],
                "telemetry_report_path": report_path.as_posix(),
            }
        else:
            raise Gr00tTelemetryConfigError("unknown command")
    except (Gr00tTelemetryConfigError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))
    return 0


def _parse_simple_yaml(path: Path) -> dict[str, object]:
    """解析本任务受控 YAML 子集, 避免引入运行时 YAML 依赖。"""
    result: dict[str, object] = {}
    current_mapping: dict[str, object] = result
    current_list_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line.startswith("- "):
            if current_list_key is None:
                raise Gr00tTelemetryConfigError(f"list item without key in {path}")
            values = current_mapping.setdefault(current_list_key, [])
            if not isinstance(values, list):
                raise Gr00tTelemetryConfigError(f"{current_list_key} is not a list in {path}")
            typed_values = cast(list[str | bool | int], values)
            typed_values.append(_parse_scalar(line[2:]))
            continue
        if ":" not in line:
            raise Gr00tTelemetryConfigError(f"unsupported YAML line in {path}: {line}")
        key, raw_value = line.split(":", 1)
        if indent == 0:
            if raw_value.strip() == "":
                if key in _YAML_LIST_FIELDS:
                    result[key] = []
                    current_mapping = result
                    current_list_key = key
                else:
                    nested: dict[str, object] = {}
                    result[key] = nested
                    current_mapping = nested
                    current_list_key = None
            else:
                result[key] = _parse_scalar(raw_value)
                current_mapping = result
                current_list_key = key if raw_value.strip() == "[]" else None
        elif indent == 2:
            if current_mapping is result:
                raise Gr00tTelemetryConfigError(f"nested YAML line without section in {path}")
            if raw_value.strip() == "":
                current_mapping[key] = []
                current_list_key = key
            else:
                current_mapping[key] = _parse_scalar(raw_value)
                current_list_key = key if raw_value.strip() == "[]" else None
        else:
            raise Gr00tTelemetryConfigError(f"unsupported indentation in {path}: {raw_line}")
    return result


def _parse_scalar(raw: str) -> str | bool | int:
    """解析受控 YAML scalar。"""
    text = raw.strip()
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "[]":
        return ""
    if text.isdecimal():
        return int(text)
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    return _expand_env_placeholder(text)


def _repo_root() -> Path:
    """返回 AutoVLA 仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def _expand_env_placeholder(text: str) -> str:
    """展开完整形态的 ${VAR} 占位符。"""
    if text.startswith("${") and text.endswith("}"):
        name = text[2:-1]
        value = os.environ.get(name)
        if value is None or not value.strip():
            raise Gr00tTelemetryConfigError(f"missing environment variable: {name}")
        return value
    if "${" in text:
        raise Gr00tTelemetryConfigError("partial environment placeholders are unsupported")
    return text


def _required_mapping(data: Mapping[str, object], field: str) -> Mapping[str, object]:
    """读取必需 mapping 字段。"""
    value = data.get(field)
    if not isinstance(value, Mapping):
        raise Gr00tTelemetryConfigError(f"{field} must be a mapping")
    return cast(Mapping[str, object], value)


def _required_string(data: Mapping[str, object], field: str) -> str:
    """读取非空字符串字段。"""
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise Gr00tTelemetryConfigError(f"{field} must be a non-empty string")
    return value


def _required_bool(data: Mapping[str, object], field: str) -> bool:
    """读取 bool 字段。"""
    value = data.get(field)
    if not isinstance(value, bool):
        raise Gr00tTelemetryConfigError(f"{field} must be a boolean")
    return value


def _required_int(data: Mapping[str, object], field: str) -> int:
    """读取 exact int 字段。"""
    value = data.get(field)
    return _require_exact_int(value, field)


def _require_exact_int(value: object, field: str) -> int:
    """校验 exact int, 拒绝 bool/float/string。"""
    if type(value) is not int:
        raise Gr00tTelemetryConfigError(f"{field} must be an int")
    number = value
    if number <= 0:
        raise Gr00tTelemetryConfigError(f"{field} must be positive")
    return number


def _required_string_list(data: Mapping[str, object], field: str) -> tuple[str, ...]:
    """读取字符串列表字段。"""
    value = data.get(field)
    if not isinstance(value, list):
        raise Gr00tTelemetryConfigError(f"{field} must be a string list")
    items: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise Gr00tTelemetryConfigError(f"{field} must be a string list")
        items.append(item)
    return tuple(items)


def _validate_run_id(value: str) -> None:
    """限制 run_id 为单段安全路径名。"""
    if not _SAFE_RUN_ID.fullmatch(value) or value in {".", ".."}:
        raise Gr00tTelemetryConfigError("run_id must be path-safe")


def _path_from_string(value: str, field: str) -> Path:
    """从字符串构造本地 Path。"""
    if "://" in value or value.startswith(("pipe:", "s3:", "gs:", "hf://")):
        raise Gr00tTelemetryConfigError(f"{field} must be a local path")
    return Path(value)


def _validate_local_path(path: Path, field: str) -> None:
    """拒绝 URL/pipe 形态路径。"""
    _path_from_string(path.as_posix(), field)


def _validate_offline_environment(env: Mapping[str, str]) -> None:
    """确认网络相关环境变量处于 fail-closed 状态。"""
    for name, expected in _REQUIRED_OFFLINE_ENV.items():
        if env.get(name) != expected:
            raise Gr00tTelemetryConfigError(f"offline environment variable required: {name}")
    wandb_disabled = env.get("WANDB_DISABLED", "").lower()
    wandb_mode = env.get("WANDB_MODE", "").lower()
    if wandb_disabled not in _WANDB_DISABLED_VALUES and wandb_mode != "disabled":
        raise Gr00tTelemetryConfigError("offline W&B environment variable required")


def _read_json_object(path: Path) -> dict[str, object]:
    """读取 JSON object。"""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Gr00tTelemetryConfigError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Gr00tTelemetryConfigError(f"invalid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise Gr00tTelemetryConfigError(f"JSON payload must be an object: {path}")
    return cast(dict[str, object], raw)


def _manifest_positive_int(manifest: Mapping[str, object], field: str) -> int:
    """读取 manifest 中的正整数字段。"""
    value = manifest.get(field)
    if type(value) is not int or value <= 0:
        raise Gr00tTelemetryConfigError(f"manifest field must be positive int: {field}")
    return value


def _is_compute_node() -> bool:
    """判断当前进程是否带有计算节点验证标记。"""
    return os.environ.get(_COMPUTE_NODE_ENV) == "1"


if __name__ == "__main__":
    raise SystemExit(main())
