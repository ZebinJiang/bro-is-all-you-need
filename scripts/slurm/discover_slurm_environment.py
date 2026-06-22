#!/usr/bin/env python3
"""发现 Slurm 集群环境并在需要时填充项目 Slurm 配置。

功能：
- 读取允许的 Slurm 元数据命令，例如 sinfo 和 scontrol；
- 生成节点、分区、版本、集群名的 inventory；
- 当配置中仍为 TO_FILL 时，可写回 approved_cluster 和 partition；
- 不修改任何集群配置，也不读取其他用户任务细节。

输入：
- --config: 项目内 Slurm JSON 配置；
- --run-id: 发现任务的记录 ID；
- --write-config: 仅当配置仍含 TO_FILL 时写回配置；
- --force-user-authorized-update: 用户显式要求刷新已填配置时使用。

输出：
- runs/slurm_inventory/<run_id>/outputs/slurm_inventory.json；
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
from pathlib import Path


def run_command(command: list[str]) -> dict:
    """运行只读 Slurm 元数据命令，并返回 stdout/stderr/returncode。"""
    if shutil.which(command[0]) is None:
        return {"command": command, "available": False, "returncode": None, "stdout": "", "stderr": f"{command[0]} not found"}
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
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


def parse_partitions(sinfo_stdout: str) -> list[dict]:
    """解析 sinfo 分区列表。"""
    partitions = []
    for line in sinfo_stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 8:
            continue
        name_raw, avail, timelimit, nodes, cpus, mem, gres, nodelist = parts
        is_default = name_raw.endswith("*")
        name = name_raw.rstrip("*")
        partitions.append({
            "name": name,
            "is_default": is_default,
            "available": avail,
            "time_limit": timelimit,
            "nodes": nodes,
            "cpus": cpus,
            "memory_mb": mem,
            "gres": gres,
            "nodelist": nodelist,
        })
    return partitions


def choose_partition(partitions: list[dict]) -> str:
    """选择一个候选默认分区。优先 Slurm 默认分区，其次可用分区。"""
    for item in partitions:
        if item.get("is_default") and item.get("available") in {"up", "yes", "avail"}:
            return item["name"]
    for item in partitions:
        if item.get("available") in {"up", "yes", "avail"}:
            return item["name"]
    return partitions[0]["name"] if partitions else "TO_FILL"


def config_needs_fill(data: dict) -> bool:
    """判断配置是否仍需要环境发现。"""
    return any(str(data.get(key, "")).strip() in {"", "TO_FILL"} for key in ["approved_cluster", "partition"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/slurm/default_sandbox.json")
    parser.add_argument("--run-id", default="slurm-discovery-" + _dt.datetime.utcnow().strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--force-user-authorized-update", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    config_path = (root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config).resolve()
    if not str(config_path).startswith(str((root / "configs" / "slurm").resolve())):
        raise SystemExit("config must be under configs/slurm/")
    data = json.loads(config_path.read_text(encoding="utf-8"))

    run_dir = root / "runs" / "slurm_inventory" / args.run_id
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)

    commands = {
        "sinfo_summary": run_command(["sinfo", "-h", "-o", "%P|%a|%l|%D|%c|%m|%G|%N"]),
        "scontrol_config": run_command(["scontrol", "show", "config"]),
        "scontrol_partition": run_command(["scontrol", "show", "partition"]),
        "sbatch_version": run_command(["sbatch", "--version"]),
        "srun_version": run_command(["srun", "--version"]),
    }
    (run_dir / "logs" / "commands.log").write_text(
        "\n".join("$ " + " ".join(v["command"]) + f"\nreturncode={v['returncode']}\n{v['stdout']}\n{v['stderr']}" for v in commands.values()),
        encoding="utf-8",
    )

    partitions = parse_partitions(commands["sinfo_summary"].get("stdout", ""))
    cluster_name = parse_cluster_name(commands["scontrol_config"].get("stdout", ""))
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
    (run_dir / "outputs" / "slurm_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    needs_fill = config_needs_fill(data)
    if args.write_config:
        if not needs_fill and not args.force_user_authorized_update:
            raise SystemExit("config is already filled; use --force-user-authorized-update only after explicit user request")
        if str(data.get("approved_cluster", "")).strip() in {"", "TO_FILL"} or args.force_user_authorized_update:
            data["approved_cluster"] = cluster_name
        if str(data.get("partition", "")).strip() in {"", "TO_FILL"} or args.force_user_authorized_update:
            data["partition"] = selected_partition
        data.setdefault("config_discovery", {})["status"] = "filled" if selected_partition != "TO_FILL" else "incomplete"
        data["config_discovery"]["last_discovery_run_id"] = args.run_id
        data["config_discovery"]["inventory_path"] = str((run_dir / "outputs" / "slurm_inventory.json").relative_to(root))
        config_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({"run_id": args.run_id, "inventory": str(run_dir / "outputs" / "slurm_inventory.json"), "selected_partition": selected_partition, "cluster_name": cluster_name}, indent=2))
    return 0 if selected_partition != "TO_FILL" else 3


if __name__ == "__main__":
    raise SystemExit(main())
