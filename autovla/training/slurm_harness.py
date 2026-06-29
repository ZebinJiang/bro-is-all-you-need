"""AutoVLA Slurm harness 的 render/validate/submit 计划层。"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from autovla.training.config import LocalRunnerDryRunConfig, load_local_runner_dry_run_config

SLURM_HARNESS_MODE = "slurm-harness"
SLURM_HARNESS_PLAN_SCHEMA_VERSION = "m3-slurm-training-harness-plan.v1"
SLURM_HARNESS_MANIFEST_SCHEMA_VERSION = "m3-slurm-training-harness-manifest.v1"
SLURM_HARNESS_PLAN_FILENAME = "slurm_harness_plan.json"
SLURM_HARNESS_MANIFEST_FILENAME = "slurm_harness_manifest.json"
SLURM_HARNESS_BATCH_FILENAME = "autovla_microloop_smoke.sbatch"

_ALLOWED_ACTIONS = frozenset({"render", "validate", "submit"})
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MEM_RE = re.compile(r"^(?P<value>[1-9][0-9]*)(?P<unit>[MGT])$")
_JOB_ID_RE = re.compile(r"\b(?:job|allocation)\s+([0-9]+)\b", re.IGNORECASE)
_WRAPPER_ARGV_HEAD = ("scripts/slurm/submit_autovla_microloop_smoke.sh",)
_SUBMISSION_MODE = "sbatch_for_harness_smoke"
_EXTERNAL_EFFECT_MARKERS = (
    "endpoint",
    "from_pretrained",
    "huggingface",
    "real training",
    "real_training",
    "robot",
    "torch.load",
    "wandb",
)
_EXTERNAL_EFFECTS_FALSE = {
    "checkpoint_weight_load": False,
    "checkpoint_weight_write": False,
    "cuda": False,
    "endpoint": False,
    "external_dataset": False,
    "gpu": False,
    "hf": False,
    "network": False,
    "real_model": False,
    "real_training": False,
    "robot": False,
    "tokenizer": False,
    "wandb": False,
}
_ENVIRONMENT_GUARDS = {
    "AUTOVLA_COMPUTE_NODE_VALIDATION": "1",
    "AUTOVLA_EXPECT_NO_GPU": "1",
    "CUDA_VISIBLE_DEVICES": "",
}
_SUBPROCESS_TIMEOUT_SECONDS = 30


class SlurmHarnessRunner(Protocol):
    """subprocess.run 的最小 list-argv 协议。"""

    def __call__(
        self,
        args: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        """执行一个 shell=False 的 wrapper argv。"""
        ...


@dataclass(frozen=True, slots=True)
class SlurmResources:
    """受控 CPU microloop smoke 所需 Slurm 资源。"""

    approved_cluster: str
    partition: str
    nodes: int
    ntasks: int
    cpus_per_task: int
    memory: str
    gres: str
    max_minutes: int
    account: str | None = None
    qos: str | None = None

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 资源摘要。"""
        return {
            "account": self.account,
            "approved_cluster": self.approved_cluster,
            "cpus_per_task": self.cpus_per_task,
            "gpus_expected_for_test": 0,
            "gres": self.gres,
            "max_minutes": self.max_minutes,
            "mem": self.memory,
            "memory": self.memory,
            "nodes": self.nodes,
            "ntasks": self.ntasks,
            "partition": self.partition,
            "qos": self.qos,
            "time_limit": self.time_limit,
        }

    @property
    def time_limit(self) -> str:
        """返回 Slurm HH:MM:SS 时间限制。"""
        return _minutes_to_time(self.max_minutes)


@dataclass(frozen=True, slots=True)
class DataProvenance:
    """microloop config 中的 Data provenance。"""

    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str

    @classmethod
    def from_config(cls, config: LocalRunnerDryRunConfig) -> "DataProvenance":
        """从已验证 config 复制 Data provenance 字段。"""
        return cls(
            dataset_fingerprint=config.dataset_fingerprint,
            statistics_fingerprint=config.statistics_fingerprint,
            transform_fingerprint=config.transform_fingerprint,
        )

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 Data provenance 字典。"""
        return {
            "dataset_fingerprint": self.dataset_fingerprint,
            "statistics_fingerprint": self.statistics_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SlurmHarnessConfig:
    """Slurm harness CLI 的已解析配置。"""

    action: str
    microloop_config_path: Path
    slurm_config_path: Path
    run_id: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class SlurmHarnessPlan:
    """render/validate/submit 共享的确定性执行计划。"""

    action: str
    run_id: str
    resources: SlurmResources
    data_provenance: DataProvenance
    command_argv: tuple[str, ...]
    microloop_command_argv: tuple[str, ...]
    rendered_command: str
    microloop_config_fingerprint: str
    slurm_config_fingerprint: str
    sbatch_script_path: Path
    output_path: Path
    error_path: Path
    slurm_job_name: str

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定排序可序列化的 plan 字典。"""
        data = self.data_provenance.to_json_dict()
        return {
            "account": self.resources.account,
            "action": self.action,
            "command": shlex.join(self.microloop_command_argv),
            "command_argv": list(self.command_argv),
            "cpus_per_task": self.resources.cpus_per_task,
            "dataset_fingerprint": data["dataset_fingerprint"],
            "environment": dict(_ENVIRONMENT_GUARDS),
            "error_path": str(self.error_path),
            "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
            "gpu_compute": False,
            "gpus_expected_for_test": 0,
            "gres": self.resources.gres,
            "memory": self.resources.memory,
            "microloop_command_argv": list(self.microloop_command_argv),
            "microloop_config_fingerprint": self.microloop_config_fingerprint,
            "mode": SLURM_HARNESS_MODE,
            "nodes": self.resources.nodes,
            "ntasks": self.resources.ntasks,
            "output_path": str(self.output_path),
            "output_paths": {
                "manifest": f"{self.run_id}/{SLURM_HARNESS_MANIFEST_FILENAME}",
                "microloop_output_dir": f"{self.run_id}/microloop",
                "plan": f"{self.run_id}/{SLURM_HARNESS_PLAN_FILENAME}",
                "sbatch_script": f"{self.run_id}/{SLURM_HARNESS_BATCH_FILENAME}",
            },
            "package_name": "autovla",
            "partition": self.resources.partition,
            "qos": self.resources.qos,
            "real_training": False,
            "rendered_command": self.rendered_command,
            "resources": self.resources.to_json_dict(),
            "run_id": self.run_id,
            "sbatch_script_path": str(self.sbatch_script_path),
            "schema_version": SLURM_HARNESS_PLAN_SCHEMA_VERSION,
            "slurm_config_fingerprint": self.slurm_config_fingerprint,
            "slurm_job_name": self.slurm_job_name,
            "statistics_fingerprint": data["statistics_fingerprint"],
            "submission_mode": _SUBMISSION_MODE,
            "time_limit": self.resources.time_limit,
            "transform_fingerprint": data["transform_fingerprint"],
            "wrapper": _WRAPPER_ARGV_HEAD[0],
        }


@dataclass(frozen=True, slots=True)
class SlurmHarnessManifest:
    """记录 harness 操作结果, 不声明真实训练产物。"""

    action: str
    run_id: str
    plan_path: Path
    plan: SlurmHarnessPlan
    submit_attempted: bool
    subprocess_returncode: int | None
    submitted_job_id: str | None

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON manifest 字典。"""
        plan_data = self.plan.to_json_dict()
        return {
            "account": self.plan.resources.account,
            "action": self.action,
            "command": plan_data["command"],
            "cpus_per_task": self.plan.resources.cpus_per_task,
            "dataset_fingerprint": plan_data["dataset_fingerprint"],
            "environment": dict(_ENVIRONMENT_GUARDS),
            "error_path": str(self.plan.error_path),
            "external_effects": dict(_EXTERNAL_EFFECTS_FALSE),
            "gpu_compute": False,
            "gpus_expected_for_test": 0,
            "gres": self.plan.resources.gres,
            "memory": self.plan.resources.memory,
            "microloop_config_fingerprint": self.plan.microloop_config_fingerprint,
            "mode": SLURM_HARNESS_MODE,
            "nodes": self.plan.resources.nodes,
            "ntasks": self.plan.resources.ntasks,
            "output_path": str(self.plan.output_path),
            "package_name": "autovla",
            "partition": self.plan.resources.partition,
            "plan_path": str(self.plan_path),
            "qos": self.plan.resources.qos,
            "real_training": False,
            "run_id": self.run_id,
            "sbatch_script_path": str(self.plan.sbatch_script_path),
            "schema_version": SLURM_HARNESS_MANIFEST_SCHEMA_VERSION,
            "slurm_config_fingerprint": self.plan.slurm_config_fingerprint,
            "slurm_job_name": self.plan.slurm_job_name,
            "slurm_state": None,
            "statistics_fingerprint": plan_data["statistics_fingerprint"],
            "submission_mode": _SUBMISSION_MODE,
            "submit_attempted": self.submit_attempted,
            "submitted_job_id": self.submitted_job_id,
            "subprocess_returncode": self.subprocess_returncode,
            "time_limit": self.plan.resources.time_limit,
            "transform_fingerprint": plan_data["transform_fingerprint"],
            "wrapper": _WRAPPER_ARGV_HEAD[0],
        }


@dataclass(frozen=True, slots=True)
class SlurmHarnessResult:
    """返回 plan/manifest 路径与对象。"""

    plan_path: Path
    manifest_path: Path
    plan: SlurmHarnessPlan
    manifest: SlurmHarnessManifest


def build_slurm_harness_plan(config: SlurmHarnessConfig) -> SlurmHarnessPlan:
    """构造 deterministic Slurm wrapper argv, 不执行 wrapper。"""
    _validate_action(config.action)
    _validate_run_id(config.run_id)
    microloop_config = load_local_runner_dry_run_config(config.microloop_config_path)
    slurm_raw = _read_json_object(config.slurm_config_path)
    _reject_external_effect_strings(slurm_raw)
    resources = _resources_from_mapping(slurm_raw)
    run_dir = config.output_dir / config.run_id
    microloop_output_dir = run_dir / "microloop"
    output_path = run_dir / "logs" / "slurm-%j.out"
    error_path = run_dir / "logs" / "slurm-%j.err"
    sbatch_script_path = run_dir / SLURM_HARNESS_BATCH_FILENAME
    microloop_argv = (
        sys.executable,
        "-m",
        "autovla.training.cli",
        "microloop",
        "--config",
        str(config.microloop_config_path),
        "--output-dir",
        str(microloop_output_dir),
        "--require-compute-node",
    )
    command_argv = (
        *_WRAPPER_ARGV_HEAD,
        "--script",
        str(sbatch_script_path),
    )
    return SlurmHarnessPlan(
        action=config.action,
        command_argv=command_argv,
        data_provenance=DataProvenance.from_config(microloop_config),
        error_path=error_path,
        microloop_command_argv=microloop_argv,
        microloop_config_fingerprint=_sha256_file(config.microloop_config_path),
        output_path=output_path,
        rendered_command=shlex.join(command_argv),
        resources=resources,
        run_id=config.run_id,
        sbatch_script_path=sbatch_script_path,
        slurm_config_fingerprint=_sha256_file(config.slurm_config_path),
        slurm_job_name=f"autovla-{config.run_id}",
    )


def run_slurm_harness(
    config: SlurmHarnessConfig,
    *,
    runner: SlurmHarnessRunner = subprocess.run,
) -> SlurmHarnessResult:
    """执行 harness action; render/validate 不调用子进程。"""
    _validate_output_dir(config.output_dir)
    plan = build_slurm_harness_plan(config)
    run_dir = config.output_dir / config.run_id
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    plan_path = run_dir / SLURM_HARNESS_PLAN_FILENAME
    manifest_path = run_dir / SLURM_HARNESS_MANIFEST_FILENAME
    _write_json(plan_path, plan.to_json_dict())
    _write_sbatch_script(plan.sbatch_script_path, _render_sbatch_script(plan))

    submit_attempted = config.action == "submit"
    returncode: int | None = None
    submitted_job_id: str | None = None
    if submit_attempted:
        completed = runner(
            list(plan.command_argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        returncode = completed.returncode
        submitted_job_id = _parse_submitted_job_id(completed.stdout)
        if completed.returncode != 0:
            raise RuntimeError("Slurm wrapper submit failed")

    manifest = SlurmHarnessManifest(
        action=config.action,
        plan=plan,
        plan_path=plan_path,
        run_id=config.run_id,
        submit_attempted=submit_attempted,
        submitted_job_id=submitted_job_id,
        subprocess_returncode=returncode,
    )
    _write_json(manifest_path, manifest.to_json_dict())
    return SlurmHarnessResult(
        manifest=manifest,
        manifest_path=manifest_path,
        plan=plan,
        plan_path=plan_path,
    )


def _resources_from_mapping(data: Mapping[str, object]) -> SlurmResources:
    """从 sandbox JSON 中读取并收紧 CPU smoke 资源。"""
    resources = SlurmResources(
        account=_optional_safe_string(data, "account"),
        approved_cluster=_required_safe_string(data, "approved_cluster"),
        cpus_per_task=_required_int(data, "cpus_per_task"),
        gres=_required_safe_string(data, "gres"),
        max_minutes=_required_int(data, "max_minutes"),
        memory=_required_mem(data),
        nodes=_required_int(data, "nodes"),
        ntasks=_required_int(data, "ntasks"),
        partition=_required_safe_string(data, "partition"),
        qos=_optional_safe_string(data, "qos"),
    )
    _validate_resource_bounds(resources)
    return resources


def _validate_resource_bounds(resources: SlurmResources) -> None:
    """限制资源为 bounded CPU microloop smoke, 防止 fine-tune scale。"""
    if resources.nodes != 1:
        raise ValueError("nodes must be 1 for slurm harness smoke")
    if resources.ntasks != 1:
        raise ValueError("ntasks must be 1 for slurm harness smoke")
    if not 1 <= resources.cpus_per_task <= 16:
        raise ValueError("cpus_per_task must be between 1 and 16")
    if not 1 <= resources.max_minutes <= 30:
        raise ValueError("max_minutes must be between 1 and 30")
    if resources.gres != "none":
        raise ValueError("gres must be none for CPU-only slurm harness smoke")
    if _mem_to_gib(resources.memory) > 64.0:
        raise ValueError("mem must not exceed 64G")


def _render_sbatch_script(plan: SlurmHarnessPlan) -> str:
    """渲染 deterministic sbatch 脚本, 只运行 CPU microloop smoke。"""
    lines = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name={plan.slurm_job_name}",
        f"#SBATCH --partition={plan.resources.partition}",
        f"#SBATCH --nodes={plan.resources.nodes}",
        f"#SBATCH --ntasks={plan.resources.ntasks}",
        f"#SBATCH --cpus-per-task={plan.resources.cpus_per_task}",
        f"#SBATCH --mem={plan.resources.memory}",
        f"#SBATCH --time={plan.resources.time_limit}",
        f"#SBATCH --output={plan.output_path}",
        f"#SBATCH --error={plan.error_path}",
    ]
    if plan.resources.account is not None:
        lines.append(f"#SBATCH --account={plan.resources.account}")
    if plan.resources.qos is not None:
        lines.append(f"#SBATCH --qos={plan.resources.qos}")
    lines.extend(
        [
            "",
            "set -euo pipefail",
            'export CUDA_VISIBLE_DEVICES=""',
            "export AUTOVLA_EXPECT_NO_GPU=1",
            "export AUTOVLA_COMPUTE_NODE_VALIDATION=1",
            "export PYTHONNOUSERSITE=1",
            "export PYTHONDONTWRITEBYTECODE=1",
            shlex.join(plan.microloop_command_argv),
            "",
        ]
    )
    return "\n".join(lines)


def _read_json_object(path: Path) -> dict[str, object]:
    """读取 JSON object。"""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError("slurm_config must be a JSON object")
    return cast(dict[str, object], raw)


def _reject_external_effect_strings(value: object) -> None:
    """递归拒绝外部服务、真实训练或模型加载标记。"""
    if isinstance(value, str):
        lowered = value.lower()
        for marker in _EXTERNAL_EFFECT_MARKERS:
            if marker in lowered:
                raise ValueError("external-effect string is not allowed")
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_external_effect_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_external_effect_strings(item)


def _required_safe_string(data: Mapping[str, object], field: str) -> str:
    """读取非空安全 token 字符串并拒绝 TO_FILL。"""
    value = data.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return _validate_safe_token(value, field)


def _optional_safe_string(data: Mapping[str, object], field: str) -> str | None:
    """读取可选安全 token 字符串。"""
    if field not in data or data[field] is None:
        return None
    value = data[field]
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return _validate_safe_token(value, field)


def _validate_safe_token(value: str, field: str) -> str:
    """校验 Slurm token 不为空、不是 TO_FILL、无 shell 元字符。"""
    if not value.strip():
        raise ValueError(f"{field} must not be empty")
    if value == "TO_FILL":
        raise ValueError(f"{field} must not be TO_FILL")
    if not _SAFE_TOKEN_RE.fullmatch(value):
        raise ValueError(f"{field} contains unsafe characters")
    return value


def _required_int(data: Mapping[str, object], field: str) -> int:
    """读取 exact int 正数。"""
    value = data.get(field)
    if type(value) is not int:
        raise ValueError(f"{field} must be an int")
    number = value
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def _required_mem(data: Mapping[str, object]) -> str:
    """读取并校验 Slurm mem/memory 字段。"""
    value = data.get("memory", data.get("mem"))
    if not isinstance(value, str):
        raise ValueError("mem must be a string")
    mem = _validate_safe_token(value, "mem")
    if _MEM_RE.fullmatch(mem) is None:
        raise ValueError("mem must use M/G/T suffix")
    return mem


def _mem_to_gib(mem: str) -> float:
    """把 Slurm mem 字段转换为 GiB 上限检查值。"""
    match = _MEM_RE.fullmatch(mem)
    if match is None:
        raise ValueError("mem must use M/G/T suffix")
    value = float(match.group("value"))
    unit = match.group("unit")
    if unit == "M":
        return value / 1024.0
    if unit == "G":
        return value
    return value * 1024.0


def _validate_action(action: str) -> None:
    """确认 action 属于 harness 支持集合。"""
    if action not in _ALLOWED_ACTIONS:
        raise ValueError("action must be render, validate, or submit")


def _validate_run_id(run_id: str) -> None:
    """限制 run_id 为单段安全标识。"""
    if not run_id.strip():
        raise ValueError("run_id must not be empty")
    if run_id in {".", ".."} or not _SAFE_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a safe id")


def _validate_output_dir(output_dir: Path) -> None:
    """避免 output_dir 文件被覆盖。"""
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output_dir must be a directory or not exist")
    output_text = str(output_dir)
    if "\n" in output_text or "\r" in output_text or "\0" in output_text:
        raise ValueError("output_dir contains unsafe characters")


def _minutes_to_time(max_minutes: int) -> str:
    """把分钟转换为 Slurm HH:MM:SS 字符串。"""
    hours, minutes = divmod(max_minutes, 60)
    return f"{hours:02d}:{minutes:02d}:00"


def _sha256_file(path: Path) -> str:
    """计算输入配置 SHA256, 用于 plan/manifest provenance。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_submitted_job_id(stdout: str) -> str | None:
    """从 wrapper stdout 中提取可选 job id。"""
    match = _JOB_ID_RE.search(stdout)
    return match.group(1) if match is not None else None


def _write_json(path: Path, data: Mapping[str, object]) -> None:
    """稳定写出 JSON 文件。"""
    path.write_text(json.dumps(dict(data), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_sbatch_script(path: Path, content: str) -> None:
    """写出 deterministic sbatch 脚本。"""
    path.write_text(content, encoding="utf-8")
