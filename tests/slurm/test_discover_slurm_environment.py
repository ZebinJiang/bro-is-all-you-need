"""Slurm 环境发现脚本的本地安全契约测试。"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.slurm import discover_slurm_environment as discovery


def test_should_reject_unsafe_run_id() -> None:
    """验证 run-id 只能包含文件名安全字符。"""
    with pytest.raises(ValueError, match="run-id"):
        discovery.validate_run_id("../escape")


def test_should_reject_absolute_run_id() -> None:
    """验证 run-id 不能是绝对路径。"""
    with pytest.raises(ValueError, match="run-id"):
        discovery.validate_run_id("/tmp/escape")


def test_should_reject_path_separator_run_id() -> None:
    """验证 run-id 不能包含路径分隔符。"""
    with pytest.raises(ValueError, match="run-id"):
        discovery.validate_run_id("nested/escape")


def test_should_bound_config_path_to_slurm_config_dir(tmp_path: Path) -> None:
    """验证配置路径必须位于 configs/slurm 内。"""
    root = tmp_path / "repo"
    (root / "configs" / "slurm").mkdir(parents=True)
    outside = root / "configs" / "slurm-extra" / "default.json"

    with pytest.raises(ValueError, match="configs/slurm"):
        discovery.resolve_config_path(root, outside)


def test_should_reject_parent_escape_config_path(tmp_path: Path) -> None:
    """验证配置路径不能通过上级目录逃逸 configs/slurm。"""
    root = tmp_path / "repo"
    (root / "configs" / "slurm").mkdir(parents=True)

    with pytest.raises(ValueError, match="configs/slurm"):
        discovery.resolve_config_path(root, "configs/slurm/../other/default.json")


def test_should_bound_run_output_to_inventory_dir(tmp_path: Path) -> None:
    """验证运行输出目录不能通过 run-id 逃逸。"""
    root = tmp_path / "repo"
    (root / "runs" / "slurm_inventory").mkdir(parents=True)

    with pytest.raises(ValueError, match="run-id"):
        discovery.resolve_run_dir(root, "../escape")


def test_should_reject_absolute_output_escape(tmp_path: Path) -> None:
    """验证输出目录不能通过绝对路径 run-id 逃逸。"""
    root = tmp_path / "repo"
    (root / "runs" / "slurm_inventory").mkdir(parents=True)

    with pytest.raises(ValueError, match="run-id"):
        discovery.resolve_run_dir(root, "/tmp/escape")


def test_run_command_should_use_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证外部 Slurm 命令调用带超时限制。"""
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    def fake_which(_name: str) -> str:
        return "/usr/bin/mock"

    monkeypatch.setattr(discovery.shutil, "which", fake_which)
    monkeypatch.setattr(discovery.subprocess, "run", fake_run)

    result = discovery.run_command(["sinfo"])

    assert result["returncode"] == 0
    assert captured["timeout"] == discovery.COMMAND_TIMEOUT_SECONDS


def test_run_command_timeout_should_return_text_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证超时分支会把 subprocess 捕获的 bytes stdout 规范化为文本。"""

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            discovery.COMMAND_TIMEOUT_SECONDS,
            output=b"partial",
        )

    def fake_which(_name: str) -> str:
        return "/usr/bin/mock"

    monkeypatch.setattr(discovery.shutil, "which", fake_which)
    monkeypatch.setattr(discovery.subprocess, "run", fake_run)

    result = discovery.run_command(["sinfo"])

    assert result["stdout"] == "partial"
    assert isinstance(result["stdout"], str)
    assert result["returncode"] is None


@pytest.mark.parametrize(
    ("cluster_name", "partition", "partitions"),
    [
        ("UNKNOWN_CLUSTER", "gpu", [{"name": "gpu"}]),
        ("", "gpu", [{"name": "gpu"}]),
        ("TO_FILL", "gpu", [{"name": "gpu"}]),
        ("cluster-a", "TO_FILL", [{"name": "gpu"}]),
        ("cluster-a", "", [{"name": "gpu"}]),
        ("cluster-a", "missing", [{"name": "gpu"}]),
    ],
)
def test_should_refuse_invalid_write_config_values(
    cluster_name: str,
    partition: str,
    partitions: list[dict[str, str]],
) -> None:
    """验证写回配置前会拒绝未知集群、空分区和缺失分区。"""
    with pytest.raises(ValueError):
        discovery.validate_write_config_values(cluster_name, partition, partitions)


def test_should_write_config_atomically(tmp_path: Path) -> None:
    """验证配置写回使用临时文件并替换目标文件。"""
    path = tmp_path / "default.json"
    data = {"approved_cluster": "cluster-a", "partition": "gpu"}

    discovery.write_json_atomic(path, data)

    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert not list(tmp_path.glob("*.tmp"))


def test_should_call_os_replace_with_same_directory_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证原子写使用同目录临时文件调用 os.replace。"""
    path = tmp_path / "default.json"
    data = {"approved_cluster": "cluster-a", "partition": "gpu"}
    captured: dict[str, Path] = {}
    original_replace = os.replace

    def fake_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        captured["src"] = src_path
        captured["dst"] = dst_path
        original_replace(src_path, dst_path)

    monkeypatch.setattr(discovery.os, "replace", fake_replace)

    discovery.write_json_atomic(path, cast(dict[str, Any], data))

    assert captured["dst"] == path
    assert captured["src"].parent == path.parent
    assert captured["src"].name.endswith(".tmp")
    assert json.loads(path.read_text(encoding="utf-8")) == data
