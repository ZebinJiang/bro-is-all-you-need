#!/usr/bin/env python3
"""调度项目本地 Codex Manager 的 Teamwork 包装器。

输入：
- 里程碑、阶段、可选 prompt/report 路径和 Codex 会话选择参数；
- 项目本地 `.agent-docs/teamwork/` 路由状态。

输出：
- dry-run 时打印解析后的路径、路由表和安全命令预览；
- 非 dry-run 时把 Codex 输出捕获到 `<stage>.last.md`，更新本地会话元数据，
  并向 `messages.jsonl` 追加一次 dispatch 事件。

治理边界：
- 不选择里程碑、不批准 gate、不提交 Slurm、不执行 git push/PR；
- 不读取全局 `~/.claude` prompt 或项目状态；
- 不自动提升 `.last.md` 到 canonical `.md` 报告。
"""

import argparse
import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


STAGES = ("DISCUSS", "PLAN", "EXECUTE", "VERIFY", "REVIEW")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
FORBIDDEN_FLAGS = {
    "--approve-gate",
    "--mark-complete",
    "--set-passes",
    "--push",
    "--pr",
    "--sbatch",
    "--srun",
    "--submit",
}
SLURM_SUBMISSION_FLAGS = {
    "--account",
    "--array",
    "--begin",
    "--chdir",
    "--constraint",
    "--cpus-per-gpu",
    "--cpus-per-task",
    "--dependency",
    "--error",
    "--exclude",
    "--export",
    "--gres",
    "--gres-flags",
    "--gpus",
    "--gpus-per-node",
    "--gpus-per-task",
    "--job-name",
    "--mail-type",
    "--mem",
    "--mem-per-cpu",
    "--mem-per-gpu",
    "--nodes",
    "--nodelist",
    "--ntasks",
    "--ntasks-per-node",
    "--output",
    "--partition",
    "--qos",
    "--reservation",
    "--signal",
    "--time",
    "--tmp",
    "--wait",
    "--wrap",
}


def utc_now() -> str:
    """返回 UTC ISO 时间戳，供本地 Teamwork 元数据记录使用。"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def fail(message: str, code: int = 2) -> None:
    """用统一格式向 stderr 输出治理错误并退出。"""
    print(f"dispatch_codex_manager: {message}", file=sys.stderr)
    raise SystemExit(code)


def reject_forbidden_flags(argv: list[str]) -> None:
    """在 argparse 之前拒绝 gate、PR、Slurm 提交等禁止参数。"""
    for raw in argv[1:]:
        flag = raw.split("=", 1)[0]
        if flag in FORBIDDEN_FLAGS or flag in SLURM_SUBMISSION_FLAGS or flag.startswith("--slurm"):
            fail(f"forbidden governance flag rejected before parsing: {flag}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """解析 wrapper CLI 参数，未知参数交给 argparse 正常拒绝。"""
    reject_forbidden_flags(argv)
    parser = argparse.ArgumentParser(description="Dispatch project-local Codex Manager through Teamwork.")
    parser.add_argument("--milestone", required=True)
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--repo-root")
    parser.add_argument("--teamwork-root")
    parser.add_argument("--prompt-path")
    parser.add_argument("--report-path")
    parser.add_argument("--mode", choices=("bootstrap", "resume", "auto"), default="auto")
    parser.add_argument("--session-id")
    parser.add_argument("--use-last", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sandbox", choices=SANDBOXES, default="workspace-write")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="xhigh")
    return parser.parse_args(argv[1:])


def is_inside(path: Path, parent: Path) -> bool:
    """判断路径是否位于指定父目录下，避免依赖较新的 Path API。"""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def ensure_inside(path: Path, parent: Path, label: str) -> Path:
    """校验路径必须在 parent 内，并返回解析后的绝对路径。"""
    resolved = path.resolve()
    if not is_inside(resolved, parent):
        fail(f"{label} must be inside {parent}")
    return resolved


def ensure_not_under_global_claude(path: Path, label: str) -> None:
    """拒绝全局 ~/.claude 下的 prompt 或项目状态路径。"""
    global_claude = (Path.home() / ".claude").resolve()
    if is_inside(path.resolve(), global_claude) or path.resolve() == global_claude:
        fail(f"{label} must not be under ~/.claude")


def resolve_repo_root(raw: str | None) -> Path:
    """解析仓库根目录；优先显式路径，其次 git rev-parse，最后退回脚本位置。"""
    if raw:
        repo_root = Path(raw).expanduser().resolve()
    else:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            repo_root = Path(completed.stdout.strip()).resolve()
        else:
            repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / ".git").exists():
        fail("repo-root must be a git repository root")
    return repo_root


def resolve_user_path(raw: str, repo_root: Path) -> Path:
    """把用户提供的相对路径按 repo_root 解析，绝对路径保持绝对语义。"""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def resolve_teamwork_root(repo_root: Path, raw: str | None) -> Path:
    """解析并校验项目本地 Teamwork 根目录。"""
    teamwork_root = resolve_user_path(raw, repo_root) if raw else (repo_root / ".agent-docs" / "teamwork").resolve()
    if not teamwork_root.exists():
        fail(f"teamwork-root does not exist: {teamwork_root}")
    ensure_inside(teamwork_root, repo_root, "teamwork-root")
    ensure_not_under_global_claude(teamwork_root, "teamwork-root")
    return teamwork_root


def resolve_prompt_path(repo_root: Path, teamwork_root: Path, milestone: str, stage: str, raw: str | None) -> Path:
    """解析 prompt 路径，要求存在、位于 teamwork_root 内且不在 ~/.claude 下。"""
    if raw:
        prompt_path = resolve_user_path(raw, repo_root)
        if not prompt_path.exists():
            fail(f"prompt-path does not exist: {prompt_path}")
    else:
        prompt_path = (teamwork_root / "prompts" / milestone / f"{stage}.prompt.md").resolve()
        if not prompt_path.exists():
            fail(f"default prompt is missing: {prompt_path}")
    ensure_not_under_global_claude(prompt_path, "prompt-path")
    return ensure_inside(prompt_path, teamwork_root, "prompt-path")


def resolve_report_paths(
    repo_root: Path,
    teamwork_root: Path,
    milestone: str,
    stage: str,
    raw: str | None,
) -> tuple[Path, Path]:
    """解析 canonical report 和 `.last.md` 捕获路径；只创建捕获路径父目录。"""
    if raw:
        report_path = resolve_user_path(raw, repo_root)
    else:
        report_path = (teamwork_root / "reports" / milestone / f"{stage}.md").resolve()
    report_path = ensure_inside(report_path, teamwork_root, "report-path")
    capture_path = (teamwork_root / "reports" / milestone / f"{stage}.last.md").resolve()
    capture_path = ensure_inside(capture_path, teamwork_root, "report-capture-path")
    capture_path.parent.mkdir(parents=True, exist_ok=True)
    return report_path, capture_path


def routing_paths(teamwork_root: Path, milestone: str, stage: str, report_path: Path, capture_path: Path) -> dict[str, Path]:
    """返回所有项目本地 Teamwork 路由文件路径。"""
    return {
        "task_board": teamwork_root / "workspace" / "task-board.md",
        "claude_inbox": teamwork_root / "claude-inbox.md",
        "messages": teamwork_root / "messages.jsonl",
        "next_actor": teamwork_root / "next-actor.json",
        "session": teamwork_root / "codex-manager-session.json",
        "prompt": teamwork_root / "prompts" / milestone / f"{stage}.prompt.md",
        "canonical_report": report_path,
        "report_capture": capture_path,
    }


def read_session_file(path: Path) -> dict:
    """读取本地 Codex Manager 会话文件；不存在时返回空字典。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"session metadata is not valid JSON: {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"session metadata must be a JSON object: {path}")
    return data


def parse_iso_timestamp(raw: str | None) -> datetime.datetime | None:
    """解析 ISO 时间戳；失败时返回 None 并由调用方保守处理。"""
    if not raw or not isinstance(raw, str):
        return None
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def has_prior_no_ambiguity_reason(session_data: dict) -> bool:
    """判断 session 文件是否已有 P0 bootstrap 的无歧义 use-last 记录。"""
    reason = str(session_data.get("use_last_fallback_reason", "")).lower()
    return (
        session_data.get("use_last_fallback") is True
        and session_data.get("active_milestone") == "P0"
        and "no_ambiguity" in reason
    )


def repo_local_metadata_newer_than(repo_codex: Path, bootstrap_at: datetime.datetime) -> tuple[bool, str]:
    """扫描 repo-local `.codex` 文件 mtime，判断是否存在晚于 bootstrap 的元数据。"""
    newest_path = None
    newest_time = None
    for root, _, files in os.walk(repo_codex):
        for name in files:
            path = Path(root) / name
            try:
                mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)
            except OSError:
                continue
            if newest_time is None or mtime > newest_time:
                newest_time = mtime
                newest_path = path
    if newest_time is None:
        return False, "no_ambiguity: repo-local .codex exists but contains no files"
    if newest_time > bootstrap_at:
        return True, f"repo-local .codex metadata newer than bootstrap: {newest_path}"
    return False, "no_ambiguity: repo-local .codex metadata is not newer than bootstrap"


def write_json_atomic(path: Path, data: dict) -> None:
    """以同目录临时文件加 os.replace 原子写入 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def record_use_last_result(session_path: Path, session_data: dict, success: bool, reason: str) -> None:
    """记录 `--use-last` 歧义检查结果，失败也保留原因。"""
    updated = dict(session_data)
    updated["use_last_fallback"] = bool(success)
    updated["use_last_fallback_reason"] = reason
    updated["use_last_checked_at"] = utc_now()
    write_json_atomic(session_path, updated)


def check_use_last_allowed(session_path: Path, repo_root: Path, session_data: dict) -> tuple[bool, str]:
    """保守检查 `codex exec resume --last` 是否允许使用。"""
    if session_data.get("session_id"):
        return False, "session_id exists; use --session-id instead of --use-last"

    help_result = subprocess.run(
        ["codex", "exec", "resume", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    help_text = help_result.stdout + help_result.stderr
    if help_result.returncode != 0 or "--last" not in help_text:
        return False, "codex exec resume --help does not advertise --last"

    bootstrap_raw = session_data.get("last_bootstrap_at")
    if not bootstrap_raw and session_data.get("dispatch_mode") == "bootstrap":
        bootstrap_raw = session_data.get("updated_at")
    bootstrap_at = parse_iso_timestamp(bootstrap_raw)
    if bootstrap_at is None:
        return False, "cannot determine last bootstrap timestamp"

    repo_codex = repo_root / ".codex"
    if not repo_codex.exists():
        if has_prior_no_ambiguity_reason(session_data):
            return True, "no_ambiguity: reused prior P0 bootstrap reason without repo-local .codex metadata"
        return False, "inconclusive: repo-local .codex metadata is unavailable"

    newer, reason = repo_local_metadata_newer_than(repo_codex, bootstrap_at)
    if newer:
        return False, reason
    return True, reason


def determine_dispatch_mode(
    args: argparse.Namespace,
    session_path: Path,
    repo_root: Path,
    session_data: dict,
) -> tuple[str, str | None, str]:
    """根据 CLI 和 session 文件确定 bootstrap、resume-by-id 或 resume-last。"""
    if args.session_id and args.use_last:
        fail("--session-id and --use-last are mutually exclusive")
    if args.mode == "bootstrap":
        if args.session_id or args.use_last:
            fail("--mode bootstrap cannot be combined with --session-id or --use-last")
        return "bootstrap", None, ""
    if args.mode == "resume":
        if args.session_id:
            return "resume-by-id", args.session_id, ""
        if args.use_last:
            ok, reason = check_use_last_allowed(session_path, repo_root, session_data)
            record_use_last_result(session_path, session_data, ok, reason)
            if not ok:
                fail(reason)
            return "resume-last", None, reason
        fail("--mode resume requires --session-id or --use-last")

    if args.session_id:
        return "resume-by-id", args.session_id, ""
    if args.use_last:
        ok, reason = check_use_last_allowed(session_path, repo_root, session_data)
        record_use_last_result(session_path, session_data, ok, reason)
        if not ok:
            fail(reason)
        return "resume-last", None, reason
    session_id = session_data.get("session_id")
    if session_id:
        return "resume-by-id", str(session_id), ""
    return "bootstrap", None, ""


def build_codex_command(
    dispatch_mode: str,
    session_id: str | None,
    repo_root: Path,
    sandbox: str,
    model: str,
    effort: str,
    capture_path: Path,
) -> list[str]:
    """按 PLAN 指定形状构造 Codex CLI 参数列表，不使用 shell。"""
    if dispatch_mode == "bootstrap":
        return [
            "codex",
            "exec",
            "--json",
            "-C",
            str(repo_root),
            "-s",
            sandbox,
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={effort}",
            "-o",
            str(capture_path),
            "-",
        ]
    if dispatch_mode == "resume-by-id":
        if not session_id:
            fail("resume-by-id requires a session id")
        return [
            "codex",
            "exec",
            "-C",
            str(repo_root),
            "-s",
            sandbox,
            "resume",
            session_id,
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={effort}",
            "-o",
            str(capture_path),
            "-",
        ]
    if dispatch_mode == "resume-last":
        return [
            "codex",
            "exec",
            "-C",
            str(repo_root),
            "-s",
            sandbox,
            "resume",
            "--last",
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={effort}",
            "-o",
            str(capture_path),
            "-",
        ]
    fail(f"unknown dispatch mode: {dispatch_mode}")


def format_command_preview(command: list[str], prompt_path: Path) -> str:
    """生成可复制的 shell-safe 命令预览。"""
    return shlex.join(command) + " < " + shlex.quote(str(prompt_path))


def print_dry_run(
    repo_root: Path,
    teamwork_root: Path,
    prompt_path: Path,
    report_path: Path,
    capture_path: Path,
    routes: dict[str, Path],
    dispatch_mode: str,
    command_preview: str,
) -> None:
    """打印 dry-run 解析结果和项目本地 Teamwork 路由表。"""
    print("Resolved paths:")
    print(f"  repo_root: {repo_root}")
    print(f"  teamwork_root: {teamwork_root}")
    print(f"  prompt_path: {prompt_path}")
    print(f"  canonical_report_path: {report_path}")
    print(f"  report_capture_path: {capture_path}")
    print("")
    print("Local Teamwork routing table:")
    for key in sorted(routes):
        print(f"  {key}: {routes[key].resolve()}")
    print("")
    print(f"Dispatch mode: {dispatch_mode}")
    print("Command preview:")
    print(f"  {command_preview}")


def run_codex(command: list[str], prompt_path: Path) -> subprocess.CompletedProcess:
    """读取 prompt 并运行 Codex；捕获 stdout/stderr/returncode。"""
    prompt_text = prompt_path.read_text(encoding="utf-8")
    try:
        return subprocess.run(
            command,
            input=prompt_text,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))


def candidate_text(value) -> str | None:
    """把 JSON 字段安全转换为非空字符串候选。"""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def event_type_text(event: dict) -> str:
    """合并常见事件类型字段，供保守识别创建事件使用。"""
    parts = []
    for key in ("type", "event", "event_type", "name"):
        value = event.get(key)
        if isinstance(value, str):
            parts.append(value.lower())
    return " ".join(parts)


def is_creation_event(event: dict) -> bool:
    """判断 JSONL 事件是否清楚表示 session/conversation/thread 创建。"""
    text = event_type_text(event)
    subject = any(word in text for word in ("session", "conversation", "thread"))
    action = any(word in text for word in ("create", "created", "start", "started", "init", "initialized"))
    return subject and action


def try_extract_session_id(jsonl_events: str) -> tuple[str | None, str]:
    """从 Codex JSONL stdout 中保守提取稳定会话 ID。

    返回：
    - `(id, "jsonl:<field>")`：找到 top-level 或 payload 中的稳定 ID；
    - `(None, "not_found")`：没有找到或输入行不可解析。
    """
    for line in jsonl_events.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for key in ("session_id", "conversation_id", "thread_id"):
            value = candidate_text(event.get(key))
            if value:
                return value, f"jsonl:{key}"
        payload = event.get("payload")
        if isinstance(payload, dict):
            for key in ("session_id", "conversation_id", "thread_id"):
                value = candidate_text(payload.get(key))
                if value:
                    return value, f"jsonl:payload.{key}"
            payload_id = candidate_text(payload.get("id"))
            if payload_id and is_creation_event(event):
                return payload_id, "jsonl:payload.id"
    return None, "not_found"


def path_for_metadata(path: Path, repo_root: Path) -> str:
    """尽量用 repo 相对路径记录本地文件，repo 外路径保留绝对路径。"""
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def update_session_metadata(
    session_path: Path,
    existing: dict,
    dispatch_mode: str,
    session_id: str | None,
    session_method: str,
    use_last_reason: str,
    repo_root: Path,
    milestone: str,
    stage: str,
    prompt_path: Path,
    report_path: Path,
    capture_path: Path,
    sandbox: str,
    model: str,
    effort: str,
    command_preview: str,
    exit_code: int,
    timestamp: str,
) -> None:
    """更新 Codex Manager session 元数据；使用原子写避免部分写入。"""
    data = dict(existing)
    data.update(
        {
            "session_id": session_id,
            "session_id_extraction_method": session_method,
            "use_last_fallback": dispatch_mode == "resume-last",
            "use_last_fallback_reason": use_last_reason,
            "dispatch_mode": dispatch_mode,
            "repo_root": str(repo_root),
            "active_milestone": milestone,
            "current_stage": stage,
            "last_prompt_path": path_for_metadata(prompt_path, repo_root),
            "last_report_path": path_for_metadata(capture_path, repo_root),
            "canonical_report_path": path_for_metadata(report_path, repo_root),
            "sandbox": sandbox,
            "model": model,
            "reasoning_effort": effort,
            "codex_command_preview": command_preview,
            "updated_at": timestamp,
            "last_exit_code": exit_code,
        }
    )
    if dispatch_mode == "bootstrap":
        data["last_bootstrap_at"] = timestamp
    write_json_atomic(session_path, data)


def append_dispatch_event(messages_path: Path, payload: dict) -> None:
    """向 Teamwork messages.jsonl 追加单行 dispatch 事件。"""
    messages_path.parent.mkdir(parents=True, exist_ok=True)
    with messages_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def choose_session_metadata(
    dispatch_mode: str,
    selected_session_id: str | None,
    existing_session_id: str | None,
    result: subprocess.CompletedProcess,
) -> tuple[str | None, str]:
    """根据 dispatch 类型和 stdout 结果生成 session_id 元数据。"""
    if dispatch_mode == "bootstrap":
        session_id, method = try_extract_session_id(result.stdout or "")
        if session_id:
            return session_id, method
        if result.returncode != 0 or not (result.stdout or "").strip():
            return None, "command_failed_or_no_events"
        return None, method
    if dispatch_mode == "resume-by-id":
        return selected_session_id or existing_session_id, "resume-by-id"
    return None, "resume-last-not-extracted"


def main() -> int:
    """执行 CLI 主流程：解析、校验、预览或调度 Codex。"""
    args = parse_args(sys.argv)
    repo_root = resolve_repo_root(args.repo_root)
    teamwork_root = resolve_teamwork_root(repo_root, args.teamwork_root)
    prompt_path = resolve_prompt_path(repo_root, teamwork_root, args.milestone, args.stage, args.prompt_path)
    report_path, capture_path = resolve_report_paths(repo_root, teamwork_root, args.milestone, args.stage, args.report_path)
    routes = routing_paths(teamwork_root, args.milestone, args.stage, report_path, capture_path)
    session_path = routes["session"].resolve()
    session_data = read_session_file(session_path)
    dispatch_mode, selected_session_id, use_last_reason = determine_dispatch_mode(args, session_path, repo_root, session_data)
    command = build_codex_command(
        dispatch_mode,
        selected_session_id,
        repo_root,
        args.sandbox,
        args.model,
        args.reasoning_effort,
        capture_path,
    )
    command_preview = format_command_preview(command, prompt_path)

    if args.dry_run:
        print_dry_run(
            repo_root,
            teamwork_root,
            prompt_path,
            report_path,
            capture_path,
            routes,
            dispatch_mode,
            command_preview,
        )
        return 0

    result = run_codex(command, prompt_path)
    timestamp = utc_now()
    existing_session_id = session_data.get("session_id") if isinstance(session_data.get("session_id"), str) else None
    session_id, session_method = choose_session_metadata(
        dispatch_mode,
        selected_session_id,
        existing_session_id,
        result,
    )
    update_session_metadata(
        session_path,
        session_data,
        dispatch_mode,
        session_id,
        session_method,
        use_last_reason,
        repo_root,
        args.milestone,
        args.stage,
        prompt_path,
        report_path,
        capture_path,
        args.sandbox,
        args.model,
        args.reasoning_effort,
        command_preview,
        result.returncode,
        timestamp,
    )
    append_dispatch_event(
        routes["messages"].resolve(),
        {
            "actor": "codex-manager-wrapper",
            "event_type": "dispatch",
            "milestone": args.milestone,
            "stage": args.stage,
            "dispatch_mode": dispatch_mode,
            "prompt_path": path_for_metadata(prompt_path, repo_root),
            "report_capture_path": path_for_metadata(capture_path, repo_root),
            "exit_code": result.returncode,
            "timestamp": timestamp,
        },
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
