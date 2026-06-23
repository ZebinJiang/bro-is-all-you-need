#!/usr/bin/env python3
"""发现 Slurm 集群环境并在需要时填充项目 Slurm 配置。

功能:
- 读取允许的 Slurm 元数据命令, 例如 sinfo 和 scontrol;
- 生成节点、分区、版本、集群名的 inventory;
- 当配置中仍为 TO_FILL 时, 可写回 approved_cluster 和 partition;
- 不修改任何集群配置, 也不读取其他用户任务细节。

输入:
- --config: 项目内 Slurm JSON 配置;
- --run-id: 发现任务的记录 ID;
- --write-config: 仅当配置仍含 TO_FILL 时写回配置;
- --force-user-authorized-update: 用户显式要求刷新已填配置时使用。

输出:
- runs/slurm_inventory/<run_id>/outputs/slurm_inventory.json;
- 可选更新后的 configs/slurm/*.json。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict, cast

COMMAND_TIMEOUT_SECONDS = 30
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class CommandResult(TypedDict):
    """记录一个只读 Slurm 元数据命令的执行结果。"""

    command: list[str]
    available: bool
    returncode: int | None
    stdout: str
    stderr: str


class PartitionInfo(TypedDict):
    """记录 sinfo 输出中的一个 Slurm 分区。"""

    name: str
    is_default: bool
    available: str
    time_limit: str
    nodes: str
    cpus: str
    memory_mb: str
    gres: str
    nodelist: str


def validate_run_id(run_id: str) -> str:
    """校验 run-id 只包含安全文件名字符。"""
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run-id must match ^[A-Za-z0-9._-]+$")
    return run_id


def resolve_config_path(root: Path, requested: str | Path) -> Path:
    """将配置路径限制在项目 configs/slurm 目录内。"""
    resolved_root = root.resolve()
    slurm_config_root = (resolved_root / "configs" / "slurm").resolve()
    raw_path = Path(requested)
    config_path = (
        raw_path.resolve(strict=False)
        if raw_path.is_absolute()
        else (resolved_root / raw_path).resolve(strict=False)
    )
    try:
        config_path.relative_to(slurm_config_root)
    except ValueError as exc:
        raise ValueError("config must be under configs/slurm/") from exc
    return config_path


def resolve_run_dir(root: Path, run_id: str) -> Path:
    """将 inventory 输出限制在 runs/slurm_inventory/<run_id> 下。"""
    safe_run_id = validate_run_id(run_id)
    inventory_root = (root.resolve() / "runs" / "slurm_inventory").resolve()
    run_dir = (inventory_root / safe_run_id).resolve(strict=False)
    try:
        run_dir.relative_to(inventory_root)
    except ValueError as exc:
        raise ValueError("run output must be under runs/slurm_inventory/") from exc
    return run_dir


def _is_placeholder(value: str) -> bool:
    """判断发现值是否仍是空值或占位符。"""
    return value.strip() in {"", "TO_FILL", "UNKNOWN_CLUSTER"}


def validate_write_config_values(
    cluster_name: str,
    partition: str,
    partitions: Sequence[Mapping[str, object]],
) -> None:
    """写回配置前校验发现值已真实可用。"""
    if _is_placeholder(cluster_name):
        raise ValueError("refusing --write-config with empty, TO_FILL, or UNKNOWN_CLUSTER cluster")
    if partition.strip() in {"", "TO_FILL"}:
        raise ValueError("refusing --write-config with empty or TO_FILL partition")
    known_partitions = {str(item.get("name", "")).strip() for item in partitions}
    if partition not in known_partitions:
        raise ValueError(f"refusing --write-config because partition is missing: {partition}")


def write_json_atomic(path: Path, data: Mapping[str, Any]) -> None:
    """用同目录临时文件和原子替换写入 JSON。"""
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def run_command(command: list[str]) -> CommandResult:
    """运行只读 Slurm 元数据命令, 并返回 stdout/stderr/returncode。"""
    if shutil.which(command[0]) is None:
        return {
            "command": command,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{command[0]} not found",
        }
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "available": True,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timed out after {COMMAND_TIMEOUT_SECONDS}s",
        }
    return {
        "command": command,
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_cluster_name(config_stdout: str) -> str:
    """从 scontrol show config 输出中提取 ClusterName。"""
    match = re.search(r"^\s*ClusterName\s*=\s*(\S+)", config_stdout, re.MULTILINE)
    if match:
        return match.group(1)
    return os.environ.get("SLURM_CLUSTER_NAME", "UNKNOWN_CLUSTER")


def parse_partitions(sinfo_stdout: str) -> list[PartitionInfo]:
    """解析 sinfo 分区列表。"""
    partitions: list[PartitionInfo] = []
    for line in sinfo_stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 8:
            continue
        name_raw, avail, timelimit, nodes, cpus, mem, gres, nodelist = parts
        is_default = name_raw.endswith("*")
        name = name_raw.rstrip("*")
        partitions.append(
            {
                "name": name,
                "is_default": is_default,
                "available": avail,
                "time_limit": timelimit,
                "nodes": nodes,
                "cpus": cpus,
                "memory_mb": mem,
                "gres": gres,
                "nodelist": nodelist,
            }
        )
    return partitions


def choose_partition(partitions: list[PartitionInfo]) -> str:
    """选择一个候选默认分区。优先 Slurm 默认分区, 其次可用分区。"""
    for item in partitions:
        if item.get("is_default") and item.get("available") in {"up", "yes", "avail"}:
            return str(item["name"])
    for item in partitions:
        if item.get("available") in {"up", "yes", "avail"}:
            return str(item["name"])
    return str(partitions[0]["name"]) if partitions else "TO_FILL"


def config_needs_fill(data: Mapping[str, object]) -> bool:
    """判断配置是否仍需要环境发现。"""
    return any(
        str(data.get(key, "")).strip() in {"", "TO_FILL"}
        for key in ["approved_cluster", "partition"]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/slurm/default_sandbox.json")
    default_run_id = "slurm-discovery-" + _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y%m%d%H%M%S"
    )
    parser.add_argument("--run-id", default=default_run_id)
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--force-user-authorized-update", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2].resolve()
    try:
        config_path = resolve_config_path(root, args.config)
        run_dir = resolve_run_dir(root, args.run_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    data = cast(dict[str, Any], json.loads(config_path.read_text(encoding="utf-8")))

    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)

    commands: dict[str, CommandResult] = {
        "sinfo_summary": run_command(["sinfo", "-h", "-o", "%P|%a|%l|%D|%c|%m|%G|%N"]),
        "scontrol_config": run_command(["scontrol", "show", "config"]),
        "scontrol_partition": run_command(["scontrol", "show", "partition"]),
        "sbatch_version": run_command(["sbatch", "--version"]),
        "srun_version": run_command(["srun", "--version"]),
    }
    (run_dir / "logs" / "commands.log").write_text(
        "\n".join(
            "$ "
            + " ".join(v["command"])
            + f"\nreturncode={v['returncode']}\n{v['stdout']}\n{v['stderr']}"
            for v in commands.values()
        ),
        encoding="utf-8",
    )

    partitions = parse_partitions(commands["sinfo_summary"]["stdout"])
    cluster_name = parse_cluster_name(commands["scontrol_config"]["stdout"])
    selected_partition = choose_partition(partitions)

    inventory = {
        "run_id": args.run_id,
        "config": str(config_path),
        "cluster_name": cluster_name,
        "selected_partition": selected_partition,
        "partitions": partitions,
        "commands": commands,
        "write_config_requested": args.write_config,
    }
    (run_dir / "outputs" / "slurm_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    needs_fill = config_needs_fill(data)
    if args.write_config:
        if not needs_fill and not args.force_user_authorized_update:
            raise SystemExit(
                "config is already filled; use --force-user-authorized-update only after "
                "explicit user request"
            )
        try:
            validate_write_config_values(cluster_name, selected_partition, partitions)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if (
            str(data.get("approved_cluster", "")).strip() in {"", "TO_FILL"}
            or args.force_user_authorized_update
        ):
            data["approved_cluster"] = cluster_name
        if (
            str(data.get("partition", "")).strip() in {"", "TO_FILL"}
            or args.force_user_authorized_update
        ):
            data["partition"] = selected_partition
        config_discovery_raw = data.setdefault("config_discovery", {})
        if not isinstance(config_discovery_raw, dict):
            raise SystemExit("config_discovery must be an object when present")
        config_discovery = cast(dict[str, object], config_discovery_raw)
        config_discovery["status"] = "filled" if selected_partition != "TO_FILL" else "incomplete"
        config_discovery["last_discovery_run_id"] = args.run_id
        config_discovery["inventory_path"] = str(
            (run_dir / "outputs" / "slurm_inventory.json").relative_to(root)
        )
        write_json_atomic(config_path, data)

    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "inventory": str(run_dir / "outputs" / "slurm_inventory.json"),
                "selected_partition": selected_partition,
                "cluster_name": cluster_name,
            },
            indent=2,
        )
    )
    return 0 if selected_partition != "TO_FILL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
