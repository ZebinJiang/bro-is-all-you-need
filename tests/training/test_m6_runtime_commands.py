"""验证 M6 生成输入、离线命令和项目 Slurm 包装边界。"""

from __future__ import annotations

import json
import os
import runpy
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TRACE_JOB = ROOT / "scripts/slurm/m7_ddp_semlock_trace.sbatch"
SUBMIT_WRAPPER = ROOT / "scripts/slurm/submit_sandbox_job.sh"
TRACE_SYSCALLS = (
    "clone,clone3,fork,vfork,execve,openat,unlink,unlinkat," "setns,unshare,exit,exit_group"
)
TRACE_RECORD_HEADER = (
    "label\tobserved_at\tpid\tppid\tstart_ticks\tsid\tpgid\tstate\trole\texe\trank\t"
    "local_rank\tworld_size\tipc_ns\tmnt_ns\tpid_ns\tuser_ns\tauthorization_basis\t"
    "authorization_anchor_pid\tauthorization_anchor_start_ticks\ttrace_file_present\t"
    "cmdline\n"
)
JOB_3068_STRACE_HELP = """\
Usage: strace [options] PROG [ARGS]
  -I INTERRUPTIBLE, --interruptible=INTERRUPTIBLE
                 1: no signals are blocked
  -o FILE, --output=FILE
                 send trace output to FILE instead of stderr
"""
NATIVE_STRACE_HELP = JOB_3068_STRACE_HELP + "  --kill-on-exit  kill all tracees on exit\n"


@cache
def _evidence_root_validator() -> Callable[[str], Path]:
    """加载生成脚本的路径校验器,避免测试复制生产策略。"""
    script_dir = ROOT / "scripts/runtime"
    sys.path.insert(0, str(script_dir))
    try:
        namespace = runpy.run_path(str(script_dir / "generate_m6_reduced_runtime.py"))
    finally:
        sys.path.pop(0)
    return cast(Callable[[str], Path], namespace["_require_governed_evidence_root"])


def _governed_pytest_evidence_root(tmp_path: Path) -> Path:
    """保留 pytest 唯一路径;本地越界时映射到进程隔离的 runs/tmp 子路径。"""
    validator = _evidence_root_validator()
    candidate = tmp_path / "runtime-evidence"
    try:
        return validator(str(candidate))
    except ValueError:
        unique_root = (
            ROOT
            / "runs/tmp/pytest-m6-runtime"
            / str(os.getpid())
            / tmp_path.parent.name
            / tmp_path.name
        )
        return validator(str(unique_root / "runtime-evidence"))


def _invoke_generator(
    evidence_root: Path, data_root: Path, *, check: bool
) -> subprocess.CompletedProcess[str]:
    """以当前解释器调用生成器,并把检查策略交给测试用例。"""
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/generate_m6_reduced_runtime.py"),
            "--evidence-root",
            str(evidence_root),
            "--data-root",
            str(data_root),
            "--runtime-python",
            sys.executable,
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def _generated_runtime(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    """在 pytest 隔离目录生成一次 fixture/config/request 集合。"""
    evidence_root = _governed_pytest_evidence_root(tmp_path)
    data_root = evidence_root / "fixture-data"
    data_root.mkdir(parents=True)
    (data_root / "sample_index.jsonl").write_text(
        json.dumps({"container": "fixture.tar", "member_prefix": "sample-0"}) + "\n",
        encoding="utf-8",
    )
    result = _invoke_generator(evidence_root, data_root, check=True)
    payload = json.loads(result.stdout)
    return Path(payload["config_path"]), {
        target: Path(path) for target, path in payload["requests"].items()
    }


def _render(request: Path) -> subprocess.CompletedProcess[str]:
    """调用只渲染不执行的命令入口。"""
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/render_m6_runtime_command.py"),
            "--request",
            str(request),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _trace_test_run(tmp_path: Path, label: str) -> Path:
    """把 fake harness 证据限定到项目治理的 pytest 目录。"""
    run_dir = _governed_pytest_evidence_root(tmp_path) / label
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    return run_dir


def _trace_harness_argv(run_dir: Path, timeout_value: str, *command: str) -> list[str]:
    """通过 source guard 调用无 ptrace 的监督/清理测试入口。"""
    return [
        "bash",
        "-c",
        'source "$1"; shift; m7_run_supervision_harness "$@"',
        "m7-harness",
        str(TRACE_JOB),
        str(run_dir),
        timeout_value,
        *command,
    ]


def _validate_trace_runtime_request(
    request: Path,
) -> subprocess.CompletedProcess[str]:
    """直接调用 launcher 的同一结构化请求校验入口。"""
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; m7_validate_runtime_request "$2"',
            "m7-request-validation",
            str(TRACE_JOB),
            str(request),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _proc_start_ticks(pid: int) -> int | None:
    """读取 PID start time,用于测试侧防止 PID 复用误判。"""
    try:
        fields = (
            (Path("/proc") / str(pid) / "stat")
            .read_text(encoding="utf-8")
            .rsplit(") ", 1)[1]
            .split()
        )
        return int(fields[19])
    except (FileNotFoundError, IndexError, PermissionError, ValueError):
        return None


def _same_process_is_alive(pid: int, start_ticks: int) -> bool:
    """仅把 start time 仍相同的 PID 视为原测试进程。"""
    return _proc_start_ticks(pid) == start_ticks


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> bool:
    """为测试证据做有界轮询,不影响候选脚本的运行拓扑。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _read_recorded_identity(records: Path, pid: int) -> dict[str, str] | None:
    """读取某 PID 的首条完整 live namespace 记录。"""
    if not records.is_file():
        return None
    keys = TRACE_RECORD_HEADER.rstrip("\n").split("\t")
    for line in records.read_text(encoding="utf-8").splitlines()[1:]:
        values = line.split("\t", len(keys) - 1)
        if len(values) == len(keys) and values[2] == str(pid):
            return dict(zip(keys, values, strict=True))
    return None


def _kill_same_test_process(pid: int, start_ticks: int) -> None:
    """仅在断言失败时回收仍匹配 start time 的 fake 子进程。"""
    if _same_process_is_alive(pid, start_ticks):
        os.kill(pid, signal.SIGKILL)


def _write_fake_strace(run_dir: Path) -> Path:
    """写入无 ptrace 的确定性 strace 生命周期替身。"""
    fake_strace = run_dir / "outputs/fake-strace"
    fake_strace.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--version" ]]; then
  printf '%s\n' 'strace -- version 5.10-job3068-fixture'
  exit 0
fi
: "${M7_FAKE_STRACE_ARGV_LOG:?M7_FAKE_STRACE_ARGV_LOG is required}"
printf '%s\n' "$@" >"$M7_FAKE_STRACE_ARGV_LOG"
trace_prefix=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --kill-on-exit)
      [[ "${M7_FAKE_STRACE_REJECT_KILL_ON_EXIT:-0}" != "1" ]] || exit 64
      shift
      ;;
    --interruptible=1|-ff|-ttt|-yy)
      shift
      ;;
    -s|-e)
      shift 2
      ;;
    -o)
      trace_prefix="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done
[[ -n "$trace_prefix" && "$#" -gt 0 ]]
if [[ -n "${M7_FAKE_STRACE_SAME_SESSION_PID_FILE:-}" ]]; then
  set -m
  /usr/bin/tail -f /dev/null >/dev/null 2>&1 &
  printf '%s\n' "$!" >"$M7_FAKE_STRACE_SAME_SESSION_PID_FILE"
fi
if [[ -n "${M7_FAKE_STRACE_DETACHED_PID_FILE:-}" ]]; then
  set +m
  /usr/bin/setsid /usr/bin/bash -c \
    'printf "%s\\n" "$$" >"$1"; exec /usr/bin/tail -f /dev/null' \
    m7-fake-detached "$M7_FAKE_STRACE_DETACHED_PID_FILE" >/dev/null 2>&1 &
fi
"$@" &
tracee_pid=$!
printf '0.000000 execve("%s", [], []) = 0\n' "$1" >"$trace_prefix.$tracee_pid"
wait "$tracee_pid"
""",
        encoding="utf-8",
    )
    fake_strace.chmod(0o700)
    return fake_strace


def _fake_strace_environment(
    run_dir: Path,
    fake_strace: Path,
    help_file: Path,
    *,
    sentinel_pid: int | None = None,
    create_leaks: bool = False,
) -> dict[str, str]:
    """构造兼容模式 harness 的显式环境和证据路径。"""
    environment = {
        **os.environ,
        "M7_HARNESS_STRACE_BIN": str(fake_strace),
        "M7_HARNESS_STRACE_HELP": str(help_file),
        "M7_FAKE_STRACE_ARGV_LOG": str(run_dir / "outputs/fake-strace-argv.txt"),
        "M7_FAKE_STRACE_REJECT_KILL_ON_EXIT": "1",
    }
    if sentinel_pid is not None:
        environment["M7_HARNESS_STALE_TRACE_PID"] = str(sentinel_pid)
    if create_leaks:
        environment["M7_FAKE_STRACE_SAME_SESSION_PID_FILE"] = str(
            run_dir / "outputs/fake-same-session.pid"
        )
        environment["M7_FAKE_STRACE_DETACHED_PID_FILE"] = str(run_dir / "outputs/fake-detached.pid")
    return environment


def test_runtime_matrix_should_be_offline_bounded_and_device_explicit() -> None:
    """验证四类目标显式区分 CPU/CUDA、进程数和未执行状态。"""
    payload = yaml.safe_load(
        (ROOT / "configs/runtime/m6-runtime-matrix.yaml").read_text(encoding="utf-8")
    )
    assert payload["local_only"] is True
    assert payload["offline"] is True
    assert payload["max_steps"] == 2
    assert payload["targets"]["cpu"] == {
        "strategy": "single_device",
        "devices": 1,
        "device": "cpu",
    }
    assert payload["targets"]["gpu"]["device"] == "cuda"
    assert payload["targets"]["ddp"]["devices"] == 2
    assert payload["targets"]["fsdp2"]["devices"] == 2
    assert all("pass" not in value for value in payload["status"].values())


def test_runtime_surfaces_should_not_embed_machine_local_home_paths() -> None:
    """验证测试、文档和运行配置不绑定某台开发机的 home。"""
    machine_home = "/" + "home" + "/" + "cz-jzb"
    for path in (
        Path(__file__),
        ROOT / "docs/validation/M6_RUNTIME_VALIDATION.md",
        ROOT / "configs/runtime/m6-runtime-matrix.yaml",
        ROOT / "configs/runtime/m6-reduced-runtime.template.yaml",
    ):
        assert machine_home not in path.read_text(encoding="utf-8")


def test_generator_should_write_resolved_local_fixture_and_requests(tmp_path: Path) -> None:
    """验证生成器不依赖 tests、不写权重且严格解析全部 placeholder。"""
    from autovla.config import load_yaml

    config_path, requests = _generated_runtime(tmp_path)
    config_text = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    assert "__AUTOVLA_" not in config_text
    assert config["model"]["architecture_variant"] == "reduced_runtime"
    assert config["model"]["checkpoint_path"] is None
    assert config["model"]["local_files_only"] is True
    assert Path(config["model"]["eagle_asset_path"]).is_dir()
    assert config["data"]["datasets"][0]["embodiment"] == "reduced"
    assert config["training"]["max_steps"] == 2
    resolved = load_yaml(config_path)
    assert resolved.model.architecture_variant == "reduced_runtime"
    assert resolved.data.datasets[0].embodiment == "reduced"
    assert resolved.training.distributed.device == "cpu"
    assert set(requests) == {"cpu", "gpu", "ddp", "fsdp2"}
    generated = tuple(config_path.parents[1].rglob("*"))
    assert not any(
        path.suffix in {".bin", ".ckpt", ".pt", ".pth", ".safetensors"} for path in generated
    )
    generator_source = (ROOT / "scripts/runtime/generate_m6_reduced_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "tests." not in generator_source


def test_generator_should_accept_all_governed_tmp_children(tmp_path: Path) -> None:
    """验证四类 tmp 根仅在严格子路径上接受生成证据。"""
    validator = _evidence_root_validator()
    run_id = f"pytest-{os.getpid()}-{tmp_path.parent.name}-{tmp_path.name}"
    candidates = (
        ROOT / "runs/tmp" / run_id / "evidence",
        ROOT / "runs/local" / run_id / "tmp/evidence",
        ROOT / "runs/slurm" / run_id / "tmp/evidence",
        ROOT / "runs/slurm_debug" / run_id / "tmp/evidence",
    )
    assert tuple(validator(str(path)) for path in candidates) == tuple(
        path.resolve(strict=False) for path in candidates
    )


def test_generator_should_generate_under_slurm_tmp_child(tmp_path: Path) -> None:
    """验证 Slurm-like pytest 临时根可以生成完整运行请求。"""
    run_id = f"pytest-{os.getpid()}-{tmp_path.parent.name}-{tmp_path.name}"
    run_root = ROOT / "runs/slurm" / run_id
    evidence_root = run_root / "tmp" / tmp_path.name / "runtime-evidence"
    data_root = evidence_root / "fixture-data"
    data_root.mkdir(parents=True)
    (data_root / "sample_index.jsonl").write_text(
        json.dumps({"container": "fixture.tar", "member_prefix": "sample-0"}) + "\n",
        encoding="utf-8",
    )

    try:
        result = _invoke_generator(evidence_root, data_root, check=True)

        payload = json.loads(result.stdout)
        assert Path(payload["config_path"]).is_relative_to(evidence_root.resolve())
        assert set(payload["requests"]) == {"cpu", "gpu", "ddp", "fsdp2"}
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def test_generator_should_reject_paths_outside_strict_governed_tmp_children(
    tmp_path: Path,
) -> None:
    """验证容器根、越界、穿越、逃逸和非 tmp 运行路径全部 fail closed。"""
    validator = _evidence_root_validator()
    run_id = f"pytest-{os.getpid()}-{tmp_path.parent.name}-{tmp_path.name}"
    symlink_parent = ROOT / "runs/tmp" / run_id
    symlink_parent.mkdir(parents=True)
    escape_link = symlink_parent / "escape"
    escape_link.symlink_to(ROOT.parent / f"outside-{run_id}", target_is_directory=True)
    rejected = {
        "runs-root": ROOT / "runs",
        "repo-root": ROOT,
        "repo-outside": ROOT.parent / f"outside-{run_id}",
        "relative": Path("runs/tmp/relative-evidence"),
        "path-traversal": Path(f"{ROOT}/runs/tmp/{run_id}/../escaped"),
        "runs-tmp-root": ROOT / "runs/tmp",
        "local-tmp-root": ROOT / "runs/local" / run_id / "tmp",
        "slurm-tmp-root": ROOT / "runs/slurm" / run_id / "tmp",
        "slurm-debug-tmp-root": ROOT / "runs/slurm_debug" / run_id / "tmp",
        "non-tmp-run-path": ROOT / "runs/slurm" / run_id / "outputs/evidence",
        "other-runs-top-level": ROOT / "runs/results" / run_id / "evidence",
        "symlink-escape": escape_link / "evidence",
    }

    try:
        for path in rejected.values():
            with pytest.raises(ValueError, match="evidence root"):
                validator(str(path))
    finally:
        shutil.rmtree(symlink_parent, ignore_errors=True)


def test_renderer_should_distinguish_cpu_gpu_and_two_rank_targets(tmp_path: Path) -> None:
    """验证 CPU/CUDA 设备和两个 torchrun rank 均进入真实 CLI argv。"""
    _, requests = _generated_runtime(tmp_path)
    rendered = {target: _render(request) for target, request in requests.items()}
    assert all(result.returncode == 0 for result in rendered.values())
    assert "training.distributed.device=cpu" in rendered["cpu"].stdout
    assert "training.distributed.device=cuda" in rendered["gpu"].stdout
    assert rendered["cpu"].stdout != rendered["gpu"].stdout
    assert "training.distributed.strategy_key=single_device" in rendered["gpu"].stdout
    for target, strategy in (
        ("ddp", "distributed_data_parallel"),
        ("fsdp2", "fully_sharded_data_parallel"),
    ):
        assert "torchrun" in rendered[target].stdout
        assert "--nproc-per-node 2" in rendered[target].stdout
        assert "--module autovla.cli.train" in rendered[target].stdout
        assert f"training.distributed.strategy_key={strategy}" in rendered[target].stdout
        assert "training.max_steps=2" in rendered[target].stdout
    assert all("HF_HUB_OFFLINE=1" in result.stdout for result in rendered.values())


def test_renderer_should_reject_missing_config_and_output_paths(tmp_path: Path) -> None:
    """验证执行前缺失配置或生成输出目录会 fail closed。"""
    _, requests = _generated_runtime(tmp_path)
    request = json.loads(requests["cpu"].read_text(encoding="utf-8"))
    request["config_path"] = str(requests["cpu"].parent / "missing.yaml")
    bad_config = requests["cpu"].parent / "bad-config.json"
    bad_config.write_text(json.dumps(request), encoding="utf-8")
    assert _render(bad_config).returncode != 0
    request["config_path"] = json.loads(requests["cpu"].read_text(encoding="utf-8"))["config_path"]
    request["output_dir"] = str(requests["cpu"].parent / "missing-output")
    bad_output = requests["cpu"].parent / "bad-output.json"
    bad_output.write_text(json.dumps(request), encoding="utf-8")
    assert _render(bad_output).returncode != 0


def test_slurm_entry_should_use_project_wrapper_and_real_m6_job(tmp_path: Path) -> None:
    """验证默认 dry-run 进入批准 wrapper,且专用 job 执行请求 launcher。"""
    _, requests = _generated_runtime(tmp_path)
    wrapper = ROOT / "scripts/slurm/render_m6_runtime_job.sh"
    run_id = f"m6-wrapper-{tmp_path.parent.name}-{tmp_path.name}"
    run_root = ROOT / "runs/slurm" / run_id
    try:
        result = subprocess.run(
            [
                "bash",
                str(wrapper),
                "--target",
                "gpu",
                "--request",
                str(requests["gpu"]),
                "--run-id",
                run_id,
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "DRY RUN: no job submitted" in result.stdout
        assert "scripts/slurm/m6_runtime_job.sbatch" in result.stdout
        assert str(requests["gpu"]) in result.stdout
        source = wrapper.read_text(encoding="utf-8")
        job_source = (ROOT / "scripts/slurm/m6_runtime_job.sbatch").read_text(encoding="utf-8")
        assert "submit_sandbox_job.sh" in source
        assert not any(line.lstrip().startswith("sbatch ") for line in source.splitlines())
        assert "torchrun" not in source
        assert "template_job.sbatch" not in source
        assert "mock_autovla_task" not in job_source
        assert "run_m6_runtime_request.py" in job_source
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


def test_m7_ddp_semlock_trace_job_should_have_exact_bounded_contract(
    tmp_path: Path,
) -> None:
    """验证一次性 trace launcher 保持精确分布式请求、工具和输出边界。"""
    source = TRACE_JOB.read_text(encoding="utf-8")
    for required in (
        ': "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"',
        ': "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"',
        ': "${SANDBOX_RUNTIME_REQUEST:?SANDBOX_RUNTIME_REQUEST is required}"',
        'target = request.get("target")',
        'not isinstance(target, str) or target not in {"ddp", "fsdp2"}',
        "runtime request field target must be exactly ddp or fsdp2",
        'request.get("max_steps") != 2',
        'request.get("offline") is not True',
        "M7_STRACE_KILL_ON_EXIT_ARGS=(--kill-on-exit)",
        'M7_STRACE_MODE="native_kill_on_exit"',
        'M7_STRACE_MODE="compatibility_bounded_cleanup"',
        f'M7_TRACE_SYSCALLS="{TRACE_SYSCALLS}"',
        "local trace_timeout_seconds=90",
        "grep -Fq -- '--kill-on-exit'",
        "printf 'strace_mode=%s\\n' \"$M7_STRACE_MODE\"",
        "printf 'strace_version=%s\\n' \"$M7_STRACE_VERSION\"",
        "/usr/bin/setsid --fork --wait",
        '--request "$SANDBOX_RUNTIME_REQUEST"',
        '"$runtime_python" scripts/runtime/run_m6_runtime_request.py',
        '--output-dir "$SANDBOX_RUN_DIR/outputs/checkpoints"',
        '--evidence-json "$runtime_evidence"',
        'm7_extract_effective_command "$runtime_evidence"',
        'command = payload.get("command")',
        '"authoritative_source": str(evidence_path)',
        "M7_EVIDENCE_INCOMPLETE_EXIT=79",
        "M7_ORPHAN_CLEANUP_EXIT=80",
        "M7_COMMAND_EVIDENCE_EXIT=81",
        "M7_TRACE_SCOPE_EXIT=82",
        "/usr/bin/mktemp -d --",
        "initial_entry_count=0",
        'M7_PREFLIGHT_TRACE_PREFIX="$M7_TRACE_DIR/preflight"',
        'M7_TRACE_PREFIX="$M7_TRACE_DIR/trace"',
        "process-authorized-identities.tsv",
        "m7_pid_has_live_root_ancestry",
        "m7_identity_matches_authority",
    ):
        assert required in source

    for required_environment in (
        'export HOME="$SANDBOX_RUN_DIR/home"',
        'export TMPDIR="$SANDBOX_RUN_DIR/tmp"',
        'export XDG_CACHE_HOME="$SANDBOX_RUN_DIR/cache"',
        "export HF_DATASETS_OFFLINE=1",
        "export HF_HUB_OFFLINE=1",
        "export TRANSFORMERS_OFFLINE=1",
        "export WANDB_MODE=disabled",
        "export PYTHONNOUSERSITE=1",
        "export PYTHONDONTWRITEBYTECODE=1",
    ):
        assert required_environment in source

    assert '[[ ! -x "$tool" ]]' in source
    assert "diagnostic_field=strace_kill_on_exit" not in source
    assert "diagnostic_field=ptrace_child_preflight" in source
    assert 'm7_start_supervised_strace "$M7_SUPERVISOR_PID_FILE" "5s" "2s"' in source
    assert '"${trace_timeout_seconds}s" "10s" /usr/bin/strace' in source
    assert 'exec /usr/bin/timeout --signal=TERM --kill-after="$kill_after_value"' in source
    assert "m7_observe_live" in source
    assert "process-namespace-live.tsv" in source
    assert "live-role-namespace-coverage.json" in source
    for role in (
        '"torchrun": 1',
        '"rank_0": 1',
        '"rank_1": 1',
        '"resource_tracker_rank_0": 1',
        '"resource_tracker_rank_1": 1',
        '"dataloader_worker_rank_0": 2',
        '"dataloader_worker_rank_1": 2',
    ):
        assert role in source
    for proc_field in (
        "start_ticks",
        "ppid",
        "sid",
        "pgid",
        "exe",
        "rank",
        "local_rank",
        "world_size",
        "ipc_ns",
        "mnt_ns",
        "pid_ns",
        "user_ns",
        "authorization_basis",
        "authorization_anchor_pid",
        "authorization_anchor_start_ticks",
    ):
        assert proc_field in source
    assert 'trace_exec = "execve(" in trace_file.read_text' in source
    assert 'trace_file = Path(f"{trace_prefix}.{pid}")' in source
    assert 'pid="${trace_file##*.}"' not in source
    assert 'for trace_file in "$M7_TRACE_PREFIX".*' not in source
    assert '"$M7_AUTHORIZED_IDENTITIES" | sort -nu' in source
    assert "M7_HARNESS_STALE_TRACE_PID" in source
    assert "$SANDBOX_RUN_DIR/logs/strace-preflight" not in source
    assert source.count('-e trace="$trace_syscalls" -o "$trace_prefix"') == 1
    assert '/usr/bin/strace "$M7_PREFLIGHT_TRACE_PREFIX" "$M7_TRACE_SYSCALLS" /bin/true' in source
    assert '/usr/bin/strace "$M7_TRACE_PREFIX"' in source
    assert "/clone|clone3|fork|vfork|execve|setns|unshare/" in source
    assert "m7_pid_matches_start" in source
    assert 'kill -"$signal" -- "-$pgid"' in source
    assert "remaining_same_start_count" in source
    assert "ORPHAN_CLEANUP_FAILED" in source
    assert 'readlink "/proc/$pid/ns/ipc"' in source
    assert 'readlink "/proc/$pid/ns/mnt"' in source
    assert 'readlink "/proc/$pid/ns/pid"' in source
    assert 'readlink "/proc/$pid/ns/user"' in source
    assert "findmnt -T /dev/shm" in source
    assert "/dev/shm/sem.*" in source
    assert "status=DIAGNOSTIC_COMMAND_FINISHED" in source
    assert "status=PASS" not in source
    assert "scripts/runtime/render_m6_runtime_command.py" not in source
    assert "training.distributed.strategy_key=" not in source

    run_dir = _trace_test_run(tmp_path, "trace-prefix-scope")
    prepared = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; m7_prepare_supervision_files "$2"; '
                'm7_prepare_trace_scope "$2"; printf "%s\\n%s\\n%s\\n" '
                '"$M7_TRACE_DIR" "$M7_PREFLIGHT_TRACE_PREFIX" "$M7_TRACE_PREFIX"'
            ),
            "m7-trace-prefix-scope",
            str(TRACE_JOB),
            str(run_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert prepared.returncode == 0, prepared.stderr
    trace_directory, preflight_prefix, runtime_prefix = map(Path, prepared.stdout.splitlines())
    assert trace_directory.parent == (run_dir / "logs").resolve()
    assert trace_directory.name.startswith("m7-ddp-semlock.")
    assert preflight_prefix == trace_directory / "preflight"
    assert runtime_prefix == trace_directory / "trace"
    assert preflight_prefix != runtime_prefix
    assert not tuple(trace_directory.iterdir())
    trace_scope = (run_dir / "outputs/trace-directory.txt").read_text(encoding="utf-8")
    assert "initial_entry_count=0" in trace_scope
    assert f"preflight_trace_prefix={preflight_prefix}" in trace_scope
    assert f"trace_prefix={runtime_prefix}" in trace_scope

    sleep_lines = {
        line.strip() for line in source.splitlines() if line.strip().startswith('/usr/bin/sleep "')
    }
    assert sleep_lines == {
        '/usr/bin/sleep "$M7_CLEANUP_INTERVAL_SECONDS"',
        '/usr/bin/sleep "$M7_OBSERVER_INTERVAL_SECONDS"',
    }
    assert "只读 observer 的短 yield" in source
    runtime_start = source.index("m7_start_supervised_strace", source.index("m7_main()"))
    observer_start = source.index("m7_start_observer", runtime_start)
    assert "/usr/bin/sleep" not in source[runtime_start:observer_start]

    forbidden_topology_or_workaround = (
        "num_workers=0",
        "persistent_workers=false",
        "multiprocessing_context=fork",
        "resource_tracker.unregister",
        "_resource_tracker",
    )
    assert not any(token in source for token in forbidden_topology_or_workaround)
    forbidden_network_or_install = (
        "pip install",
        "uv pip",
        "apt-get",
        "conda install",
        "curl ",
        "wget ",
        "git clone",
        "HF_HUB_OFFLINE=0",
        "WANDB_MODE=online",
    )
    assert not any(token in source for token in forbidden_network_or_install)
    assert not any(
        line.strip().startswith(("sbatch ", "srun ", "exec sbatch ", "exec srun "))
        for line in source.splitlines()
    )

    wrapper_source = SUBMIT_WRAPPER.read_text(encoding="utf-8")
    assert 'case "$JOB_REAL" in "$ROOT_REAL"/scripts/slurm/*)' in wrapper_source
    assert "m7_ddp_semlock_trace" not in wrapper_source


def test_m7_job_3068_help_should_select_compatibility_mode(tmp_path: Path) -> None:
    """验证 job 3068 能力会选择兼容清理,而不是 BLOCKED_TOOL_ENV。"""
    run_dir = _trace_test_run(tmp_path, "job-3068-capability")
    help_file = run_dir / "outputs/strace-help-job-3068.txt"
    help_file.write_text(JOB_3068_STRACE_HELP, encoding="utf-8")
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; m7_select_strace_mode "$2"; '
                'printf "%s\\n%s\\n%s\\n" "$M7_STRACE_MODE" '
                '"$M7_STRACE_KILL_ON_EXIT_CAPABILITY" '
                '"${#M7_STRACE_KILL_ON_EXIT_ARGS[@]}"'
            ),
            "m7-job-3068-capability",
            str(TRACE_JOB),
            str(help_file),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "compatibility_bounded_cleanup",
        "unsupported",
        "0",
    ]


def test_m7_native_mode_should_preserve_kill_on_exit_argv(tmp_path: Path) -> None:
    """验证能力支持时仍把原生 kill-on-exit 传给 strace。"""
    run_dir = _trace_test_run(tmp_path, "native-strace-argv")
    fake_strace = _write_fake_strace(run_dir)
    help_file = run_dir / "outputs/native-strace-help.txt"
    help_file.write_text(NATIVE_STRACE_HELP, encoding="utf-8")
    environment = _fake_strace_environment(run_dir, fake_strace, help_file)
    environment["M7_FAKE_STRACE_REJECT_KILL_ON_EXIT"] = "0"
    result = subprocess.run(
        _trace_harness_argv(run_dir, "2s", "/bin/true"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    argv = (run_dir / "outputs/fake-strace-argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[:8] == [
        "--kill-on-exit",
        "--interruptible=1",
        "-ff",
        "-ttt",
        "-yy",
        "-s",
        "256",
        "-e",
    ]
    assert argv[8] == f"trace={TRACE_SYSCALLS}"
    assert argv[9] == "-o"
    status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
    assert "strace_mode=native_kill_on_exit" in status
    assert "strace_kill_on_exit_capability=supported" in status
    assert "strace_version=strace -- version 5.10-job3068-fixture" in status


def _run_compatibility_lifecycle_harness(
    tmp_path: Path, label: str, timeout_value: str
) -> tuple[subprocess.Popen[str], Path, subprocess.Popen[str], int, list[tuple[int, int]]]:
    """启动会遗留同 session 与 detached 子进程的兼容模式替身。"""
    run_dir = _trace_test_run(tmp_path, label)
    fake_strace = _write_fake_strace(run_dir)
    help_file = run_dir / "outputs/job-3068-strace-help.txt"
    help_file.write_text(JOB_3068_STRACE_HELP, encoding="utf-8")
    sentinel = subprocess.Popen(
        ["/usr/bin/tail", "-f", "/dev/null"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    sentinel_start = _proc_start_ticks(sentinel.pid)
    assert sentinel_start is not None
    environment = _fake_strace_environment(
        run_dir,
        fake_strace,
        help_file,
        sentinel_pid=sentinel.pid,
        create_leaks=True,
    )
    process = subprocess.Popen(
        _trace_harness_argv(run_dir, timeout_value, "/usr/bin/tail", "-f", "/dev/null"),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    pid_files = [
        run_dir / "outputs/fake-same-session.pid",
        run_dir / "outputs/fake-detached.pid",
    ]
    assert _wait_until(lambda: all(path.is_file() for path in pid_files))
    identities: list[tuple[int, int]] = []
    records = run_dir / "outputs/process-authorized-identities.tsv"
    for pid_file in pid_files:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        start_ticks = _proc_start_ticks(pid)
        assert start_ticks is not None
        assert _wait_until(lambda pid=pid: _read_recorded_identity(records, pid) is not None)
        identities.append((pid, start_ticks))
    return process, run_dir, sentinel, sentinel_start, identities


@pytest.mark.parametrize(
    ("event", "expected_code"),
    (("timeout", 124), ("int", 130), ("term", 143)),
)
def test_m7_compatibility_mode_should_reap_authorized_lifecycle_tree(
    tmp_path: Path, event: str, expected_code: int
) -> None:
    """验证兼容模式在 timeout/INT/TERM 后回收授权进程且不触碰 sentinel。"""
    timeout_value = "1s" if event == "timeout" else "10s"
    process, run_dir, sentinel, sentinel_start, identities = _run_compatibility_lifecycle_harness(
        tmp_path, f"compatibility-{event}", timeout_value
    )
    try:
        if event == "int":
            process.send_signal(signal.SIGINT)
        elif event == "term":
            process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == expected_code, (stdout, stderr)
        for pid, start_ticks in identities:
            assert not _same_process_is_alive(pid, start_ticks)
        assert _same_process_is_alive(sentinel.pid, sentinel_start)

        authorized = run_dir / "outputs/process-authorized-identities.tsv"
        for pid, _ in identities:
            assert _read_recorded_identity(authorized, pid) is not None
        assert _read_recorded_identity(authorized, sentinel.pid) is None
        cleanup = (run_dir / "outputs/process-cleanup.txt").read_text(encoding="utf-8")
        assert "remaining_same_start_count=0" in cleanup
        assert "cleanup_status=COMPLETE" in cleanup
        assert f"\t{sentinel.pid}\t{sentinel_start}\t" not in cleanup

        argv = (run_dir / "outputs/fake-strace-argv.txt").read_text(encoding="utf-8").splitlines()
        assert "--kill-on-exit" not in argv
        assert argv[:7] == ["--interruptible=1", "-ff", "-ttt", "-yy", "-s", "256", "-e"]
        assert argv[7] == f"trace={TRACE_SYSCALLS}"
        status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
        assert "strace_mode=compatibility_bounded_cleanup" in status
        assert "strace_kill_on_exit_capability=unsupported" in status
        assert f"final_exit_code={expected_code}" in status
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for pid, start_ticks in identities:
            _kill_same_test_process(pid, start_ticks)
        if _same_process_is_alive(sentinel.pid, sentinel_start):
            sentinel.terminate()
        try:
            sentinel.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_same_test_process(sentinel.pid, sentinel_start)
            sentinel.wait(timeout=5)


def test_m7_compatibility_cleanup_failure_should_remain_exit_80(tmp_path: Path) -> None:
    """验证兼容模式清理证据失败仍以独立状态 80 关闭。"""
    run_dir = _trace_test_run(tmp_path, "compatibility-cleanup-failure")
    fake_strace = _write_fake_strace(run_dir)
    help_file = run_dir / "outputs/job-3068-strace-help.txt"
    help_file.write_text(JOB_3068_STRACE_HELP, encoding="utf-8")
    environment = _fake_strace_environment(run_dir, fake_strace, help_file)
    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                'source "$1"; shift; '
                'm7_cleanup_recorded() { printf "forced_cleanup_failure=true\\n" '
                '>>"$6"; return 1; }; m7_run_supervision_harness "$@"'
            ),
            "m7-forced-cleanup-failure",
            str(TRACE_JOB),
            str(run_dir),
            "2s",
            "/bin/true",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=environment,
    )
    assert result.returncode == 80, result.stderr
    status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
    assert "strace_mode=compatibility_bounded_cleanup" in status
    assert "cleanup_status=ORPHAN_CLEANUP_FAILED" in status
    assert "final_exit_code=80" in status


def test_m7_trace_supervision_harness_should_preserve_normal_exit(tmp_path: Path) -> None:
    """验证正常退出码原样返回且清理证据确认没有残留身份。"""
    run_dir = _trace_test_run(tmp_path, "normal-exit")
    result = subprocess.run(
        _trace_harness_argv(run_dir, "2s", "/usr/bin/bash", "-c", "exit 7"),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 7, result.stderr
    assert "cleanup_status=COMPLETE" in (run_dir / "outputs/process-cleanup.txt").read_text(
        encoding="utf-8"
    )
    status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
    assert "traced_exit_code=7" in status
    assert "final_exit_code=7" in status
    records = (run_dir / "outputs/process-namespace-live.tsv").read_text(encoding="utf-8")
    assert not any(line.split("\t", 3)[2] == str(os.getpid()) for line in records.splitlines()[1:])


def test_m7_trace_harness_should_ignore_stale_trace_pid_outside_invocation(
    tmp_path: Path,
) -> None:
    """验证 stale trace 后缀不能观察、授权或清理无关的 live PID。"""
    run_dir = _trace_test_run(tmp_path, "stale-trace-sentinel")
    sentinel = subprocess.Popen(
        ["/usr/bin/sleep", "30"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    sentinel_start = _proc_start_ticks(sentinel.pid)
    assert sentinel_start is not None
    try:
        result = subprocess.run(
            _trace_harness_argv(run_dir, "2s", "/usr/bin/bash", "-c", "exit 0"),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "M7_HARNESS_STALE_TRACE_PID": str(sentinel.pid)},
        )
        assert result.returncode == 0, result.stderr
        assert _same_process_is_alive(sentinel.pid, sentinel_start)

        trace_scope = dict(
            line.split("=", 1)
            for line in (
                (run_dir / "outputs/trace-directory.txt").read_text(encoding="utf-8").splitlines()
            )
            if "=" in line
        )
        assert trace_scope["status"] == "READY"
        assert trace_scope["initial_entry_count"] == "0"
        trace_directory = Path(trace_scope["trace_directory"])
        assert trace_directory.parent == (run_dir / "logs").resolve()
        stale_trace = Path(f"{trace_scope['trace_prefix']}.{sentinel.pid}")
        assert stale_trace.is_file()
        assert "execve(" in stale_trace.read_text(encoding="utf-8")

        records = run_dir / "outputs/process-namespace-live.tsv"
        authorized = run_dir / "outputs/process-authorized-identities.tsv"
        assert _read_recorded_identity(records, sentinel.pid) is None
        assert _read_recorded_identity(authorized, sentinel.pid) is None
        cleanup = (run_dir / "outputs/process-cleanup.txt").read_text(encoding="utf-8")
        assert f"\t{sentinel.pid}\t{sentinel_start}\t" not in cleanup
        assert "cleanup_status=COMPLETE" in cleanup
    finally:
        if _same_process_is_alive(sentinel.pid, sentinel_start):
            sentinel.terminate()
        try:
            sentinel.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_same_test_process(sentinel.pid, sentinel_start)
            sentinel.wait(timeout=5)


def _run_detached_trace_harness(
    tmp_path: Path, label: str, timeout_value: str
) -> tuple[subprocess.Popen[str], Path, int, int]:
    """启动可安全识别的 detached fake 子进程并等待 live 记录。"""
    run_dir = _trace_test_run(tmp_path, label)
    pid_file = run_dir / "outputs/detached.pid"
    command = (
        "/usr/bin/setsid /usr/bin/sleep 30 & "
        'child=$!; printf \'%s\\n\' "$child" >"$1"; wait "$child"'
    )
    process = subprocess.Popen(
        _trace_harness_argv(
            run_dir,
            timeout_value,
            "/usr/bin/bash",
            "-c",
            command,
            "m7-detached-child",
            str(pid_file),
        ),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert _wait_until(pid_file.is_file), "fake detached PID was not recorded"
    child_pid = int(pid_file.read_text(encoding="utf-8").strip())
    start_ticks = _proc_start_ticks(child_pid)
    assert start_ticks is not None
    records = run_dir / "outputs/process-namespace-live.tsv"
    assert _wait_until(lambda: _read_recorded_identity(records, child_pid) is not None)
    return process, run_dir, child_pid, start_ticks


def _assert_detached_cleanup(
    process: subprocess.Popen[str], run_dir: Path, child_pid: int, start_ticks: int
) -> tuple[str, str]:
    """收集 harness 并验证同一 PID/start time 不再存活。"""
    try:
        stdout, stderr = process.communicate(timeout=15)
        assert not _same_process_is_alive(child_pid, start_ticks)
        cleanup = (run_dir / "outputs/process-cleanup.txt").read_text(encoding="utf-8")
        assert "remaining_same_start_count=0" in cleanup
        assert "cleanup_status=COMPLETE" in cleanup
        return stdout, stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        _kill_same_test_process(child_pid, start_ticks)


def test_m7_trace_supervision_harness_should_cleanup_timeout_detached_child(
    tmp_path: Path,
) -> None:
    """验证 timeout 后 detached session 被 start-safe 清理且 live namespace 完整。"""
    process, run_dir, child_pid, start_ticks = _run_detached_trace_harness(
        tmp_path, "timeout-detached", "1s"
    )
    identity = _read_recorded_identity(run_dir / "outputs/process-namespace-live.tsv", child_pid)
    assert identity is not None
    assert identity["pid"] == str(child_pid)
    assert identity["start_ticks"] == str(start_ticks)
    assert identity["ppid"].isdigit()
    assert identity["sid"].isdigit()
    assert identity["pgid"].isdigit()
    assert identity["exe"] == "/usr/bin/sleep"
    for field in ("ipc_ns", "mnt_ns", "pid_ns", "user_ns"):
        assert identity[field].endswith("]") and ":[" in identity[field]
    _, stderr = _assert_detached_cleanup(process, run_dir, child_pid, start_ticks)
    assert process.returncode == 124, stderr
    status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
    assert "traced_exit_code=124" in status
    assert "final_exit_code=124" in status


@pytest.mark.parametrize(
    ("interrupt_signal", "expected_code"),
    ((signal.SIGINT, 130), (signal.SIGTERM, 143)),
)
def test_m7_trace_supervision_harness_should_cleanup_on_signal(
    tmp_path: Path, interrupt_signal: signal.Signals, expected_code: int
) -> None:
    """验证 INT/TERM 都触发 detached tracee 清理并返回对应诊断状态。"""
    process, run_dir, child_pid, start_ticks = _run_detached_trace_harness(
        tmp_path, f"signal-{interrupt_signal.name.lower()}", "10s"
    )
    process.send_signal(interrupt_signal)
    _, stderr = _assert_detached_cleanup(process, run_dir, child_pid, start_ticks)
    assert process.returncode == expected_code, stderr
    status = (run_dir / "outputs/harness-status.txt").read_text(encoding="utf-8")
    assert f"final_exit_code={expected_code}" in status


def test_m7_effective_command_evidence_should_be_authoritative_and_governed(
    tmp_path: Path,
) -> None:
    """验证仅接受 runner 先写出的结构化有效命令及治理覆盖路径。"""
    run_dir = _trace_test_run(tmp_path, "effective-command")
    output_dir = run_dir / "outputs/checkpoints"
    output_dir.mkdir(parents=True)
    evidence = run_dir / "outputs/runtime_evidence.json"
    metrics = evidence.with_suffix(".metrics.jsonl")
    command = [
        "torchrun",
        "--nproc-per-node",
        "2",
        "--module",
        "autovla.cli.train",
        f"training.checkpoint.directory={output_dir}",
        f"training.logging.jsonl_path={metrics}",
    ]
    evidence.write_text(
        json.dumps({"command": command, "output_dir": str(output_dir)}) + "\n",
        encoding="utf-8",
    )
    artifact = run_dir / "outputs/effective-command.json"
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; m7_extract_effective_command "$2" "$3" "$4" "$5" "$6"',
            "m7-command-evidence",
            str(TRACE_JOB),
            str(evidence),
            str(output_dir),
            str(evidence),
            str(artifact),
            str(run_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["authoritative_source"] == str(evidence.resolve())
    assert payload["command"] == command
    assert payload["output_dir"] == str(output_dir.resolve())
    assert payload["evidence_json"] == str(evidence.resolve())

    malformed = run_dir / "outputs/runtime-evidence-malformed.json"
    malformed.write_text(json.dumps({"output_dir": str(output_dir)}) + "\n", encoding="utf-8")
    malformed_artifact = run_dir / "outputs/effective-command-malformed.json"
    rejected = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; m7_extract_effective_command "$2" "$3" "$4" "$5" "$6"',
            "m7-command-evidence",
            str(TRACE_JOB),
            str(malformed),
            str(output_dir),
            str(malformed),
            str(malformed_artifact),
            str(run_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "non-empty string array" in rejected.stderr
    assert not malformed_artifact.exists()


def test_m7_live_namespace_gate_should_fail_closed_when_roles_are_missing(
    tmp_path: Path,
) -> None:
    """验证 after-exit 推断不能替代完整的 live role/namespace 证据。"""
    run_dir = _trace_test_run(tmp_path, "incomplete-coverage")
    records = run_dir / "outputs/process-namespace-live.tsv"
    records.write_text(TRACE_RECORD_HEADER, encoding="utf-8")
    authorized = run_dir / "outputs/process-authorized-identities.tsv"
    authorized.write_text(TRACE_RECORD_HEADER, encoding="utf-8")
    observer = run_dir / "outputs/process-observer-status.txt"
    observer.write_text("reason=lifecycle_exited\npolls=1\n", encoding="utf-8")
    report = run_dir / "outputs/live-role-namespace-coverage.json"
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; m7_evaluate_live_coverage "$2" "$3" "$4" "$5" "$6"',
            "m7-coverage",
            str(TRACE_JOB),
            str(records),
            str(authorized),
            str(observer),
            str(run_dir / "logs/sem-lifetime"),
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["complete"] is False
    assert set(payload["missing"]) == set(payload["required"])


def test_m7_ddp_semlock_trace_job_should_pass_bash_syntax() -> None:
    """验证诊断脚本通过 bash 语法检查。"""
    result = subprocess.run(
        ["bash", "-n", str(TRACE_JOB)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_m7_ddp_semlock_trace_job_should_require_wrapper_environment(
    tmp_path: Path,
) -> None:
    """验证三个 wrapper 输入缺失时均在任何 runtime 前按字段失败。"""
    request = tmp_path / "request.json"
    request.write_text("{}\n", encoding="utf-8")
    values = {
        "SANDBOX_PROJECT_ROOT": str(ROOT),
        "SANDBOX_RUN_DIR": str(tmp_path / "run"),
        "SANDBOX_RUNTIME_REQUEST": str(request),
    }
    for missing in values:
        environment = {**os.environ, **values}
        environment.pop(missing)
        result = subprocess.run(
            ["bash", str(TRACE_JOB)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert result.returncode != 0
        assert f"{missing} is required" in result.stderr


@pytest.mark.parametrize("target", ("ddp", "fsdp2"))
def test_m7_trace_job_should_accept_exact_distributed_targets_through_same_validator(
    tmp_path: Path,
    target: str,
) -> None:
    """验证 DDP 与 FSDP2 进入同一结构化预运行校验路径。"""
    request = tmp_path / f"valid-{target}.json"
    request.write_text(
        json.dumps(
            {
                "runtime_python": sys.executable,
                "target": target,
                "max_steps": 2,
                "offline": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _validate_trace_runtime_request(request)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == sys.executable
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        pytest.param(
            "target",
            "gpu",
            "runtime request field target must be exactly ddp or fsdp2",
            id="target-gpu",
        ),
        pytest.param(
            "target",
            "cpu",
            "runtime request field target must be exactly ddp or fsdp2",
            id="target-cpu",
        ),
        pytest.param(
            "target",
            "unknown",
            "runtime request field target must be exactly ddp or fsdp2",
            id="target-unknown",
        ),
        pytest.param(
            "target",
            True,
            "runtime request field target must be exactly ddp or fsdp2",
            id="target-bool",
        ),
        pytest.param(
            "target",
            None,
            "runtime request field target must be exactly ddp or fsdp2",
            id="target-null",
        ),
        ("max_steps", 3, "runtime request field max_steps must be exactly 2"),
        ("offline", False, "runtime request field offline must be true"),
    ),
)
def test_m7_ddp_semlock_trace_job_should_reject_request_drift_before_runtime(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    """验证目标、两步和离线字段漂移均在 strace runtime 前失败。"""
    request_payload: dict[str, object] = {
        "runtime_python": sys.executable,
        "target": "ddp",
        "max_steps": 2,
        "offline": True,
    }
    request_payload[field] = value
    request = tmp_path / f"bad-{field}.json"
    request.write_text(json.dumps(request_payload) + "\n", encoding="utf-8")
    run_dir = tmp_path / f"run-{field}"
    environment = {
        **os.environ,
        "SANDBOX_PROJECT_ROOT": str(ROOT),
        "SANDBOX_RUN_DIR": str(run_dir),
        "SANDBOX_RUNTIME_REQUEST": str(request),
    }

    result = subprocess.run(
        ["bash", str(TRACE_JOB)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert not tuple((run_dir / "logs").glob("m7-ddp-semlock.*"))
    assert not (run_dir / "outputs/trace-preflight.txt").exists()


def test_wrapper_should_accept_tracked_trace_job_and_reject_runs_tmp_job(
    tmp_path: Path,
) -> None:
    """验证 wrapper dry-run 接受精确 tracked path,并继续拒绝 runs/tmp。"""
    _, requests = _generated_runtime(tmp_path)
    suffix = f"{os.getpid()}-{tmp_path.parent.name}-{tmp_path.name}"
    accepted_run_id = f"m7-trace-accepted-{suffix}"
    rejected_run_id = f"m7-trace-rejected-{suffix}"
    accepted_run_root = ROOT / "runs/slurm" / accepted_run_id
    rejected_launcher_root = ROOT / "runs/tmp" / f"pytest-m7-trace-rejected-{suffix}"
    rejected_launcher = rejected_launcher_root / "trace.sbatch"
    assert not accepted_run_root.exists()
    assert not rejected_launcher_root.exists()
    rejected_launcher.parent.mkdir(parents=True)
    rejected_launcher.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    common = [
        "bash",
        str(SUBMIT_WRAPPER),
        "--config",
        "configs/slurm/m6_runtime_ddp.json",
        "--experiment-config",
        "configs/experiments/m6_runtime.json",
        "--runtime-request",
        str(requests["ddp"]),
        "--dry-run",
    ]
    try:
        accepted = subprocess.run(
            [
                *common,
                "--job-script",
                "scripts/slurm/m7_ddp_semlock_trace.sbatch",
                "--run-id",
                accepted_run_id,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert accepted.returncode == 0, accepted.stderr
        assert "DRY RUN: no job submitted" in accepted.stdout
        assert "scripts/slurm/m7_ddp_semlock_trace.sbatch" in accepted.stdout
        assert "Submitted batch job" not in accepted.stdout

        rejected = subprocess.run(
            [
                *common,
                "--job-script",
                str(rejected_launcher.relative_to(ROOT)),
                "--run-id",
                rejected_run_id,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 2
        assert "Job script must be under scripts/slurm/" in rejected.stderr
        assert "DRY RUN: no job submitted" not in rejected.stdout
        assert "Submitted batch job" not in rejected.stdout
        assert not (ROOT / "runs/slurm" / rejected_run_id).exists()
    finally:
        shutil.rmtree(accepted_run_root, ignore_errors=True)
        shutil.rmtree(rejected_launcher_root, ignore_errors=True)


def test_runtime_evidence_schema_should_require_command_and_status_fields() -> None:
    """验证 AC7 证据 schema 绑定命令、环境分类和状态 token。"""
    schema = json.loads(
        (ROOT / "configs/runtime/m6-runtime-evidence.schema.json").read_text(encoding="utf-8")
    )
    required = set(schema["required"])
    assert {"command", "runtime", "status", "status_tokens", "return_code"} <= required
    assert schema["properties"]["target"]["enum"] == ["cpu", "gpu", "ddp", "fsdp2"]
    token_rules = schema["properties"]["status_tokens"]
    required_tokens = {rule["contains"]["const"] for rule in token_rules["allOf"]}
    assert required_tokens == {
        "NO_BACKEND_WINNER",
        "OFFICIAL_GR00T_CHECKPOINT_VALIDATION_DEFERRED_LOCAL_ASSET_ABSENT",
        "OFFICIAL_ASSET_PARITY_NOT_RUN_LOCAL_ASSET_ABSENT",
    }
    assert token_rules["minItems"] == 3
    assert token_rules["uniqueItems"] is True


def _fake_torch_module(root: Path) -> Path:
    """写入不访问真实 Torch/CUDA 的最小能力探针模块。"""
    modules = root / "fake-modules"
    modules.mkdir()
    (modules / "torch.py").write_text(
        """
class _Cuda:
    @staticmethod
    def is_available():
        return False

    @staticmethod
    def device_count():
        return 0

cuda = _Cuda()
__version__ = "0.test"
""".lstrip(),
        encoding="utf-8",
    )
    return modules


def _fake_runtime(path: Path, body: str) -> Path:
    """写入一个可执行但不启动训练的测试进程。"""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)
    return path


@pytest.mark.parametrize(
    ("target", "runtime_body", "expected_code", "detail", "extra_token"),
    (
        ("cpu", "#!/bin/sh\nexit 0\n", 0, "", None),
        (
            "cpu",
            "#!/bin/sh\nexit 7\n",
            7,
            "runtime command failed with exit code 7",
            None,
        ),
        (
            "cpu",
            "#!/definitely/missing/autovla-interpreter\n",
            127,
            "runtime executable failure",
            "RUNTIME_EXECUTABLE_UNAVAILABLE",
        ),
        (
            "gpu",
            "#!/bin/sh\nexit 0\n",
            2,
            "runtime capability failure",
            "RUNTIME_DEVICE_OR_TORCH_UNAVAILABLE",
        ),
    ),
)
def test_runtime_process_code_and_evidence_are_exact(
    tmp_path: Path,
    target: str,
    runtime_body: str,
    expected_code: int,
    detail: str,
    extra_token: str | None,
) -> None:
    """验证成功、设备、可执行文件和普通命令状态完全一致。"""
    _, requests = _generated_runtime(tmp_path)
    request_path = requests[target]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["runtime_python"] = str(
        _fake_runtime(request_path.parent / "fake-runtime", runtime_body)
    )
    request_path.write_text(json.dumps(request), encoding="utf-8")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(_fake_torch_module(request_path.parent))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/run_m6_runtime_request.py"),
            "--request",
            str(request_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    evidence = json.loads(Path(request["evidence_json"]).read_text(encoding="utf-8"))
    assert result.returncode == expected_code
    assert evidence["return_code"] == expected_code
    assert evidence["status"] == ("PASS" if expected_code == 0 else "FAIL")
    assert detail in result.stderr
    expected_tokens = {
        "NO_BACKEND_WINNER",
        "OFFICIAL_GR00T_CHECKPOINT_VALIDATION_DEFERRED_LOCAL_ASSET_ABSENT",
        "OFFICIAL_ASSET_PARITY_NOT_RUN_LOCAL_ASSET_ABSENT",
    }
    assert expected_tokens <= set(evidence["status_tokens"])
    if extra_token is not None:
        assert extra_token in evidence["status_tokens"]
