#!/usr/bin/env bash
#SBATCH --comment=autovla-m7-ddp-semlock-trace
set -euo pipefail

M7_EVIDENCE_INCOMPLETE_EXIT=79
M7_ORPHAN_CLEANUP_EXIT=80
M7_COMMAND_EVIDENCE_EXIT=81
M7_TRACE_SCOPE_EXIT=82
M7_OBSERVER_INTERVAL_SECONDS="${M7_OBSERVER_INTERVAL_SECONDS:-0.005}"
M7_OBSERVER_MAX_POLLS="${M7_OBSERVER_MAX_POLLS:-25000}"
M7_CLEANUP_INTERVAL_SECONDS="${M7_CLEANUP_INTERVAL_SECONDS:-0.02}"
M7_CLEANUP_POLLS="${M7_CLEANUP_POLLS:-100}"
M7_WAIT_PID=""
M7_OBSERVER_PID=""
M7_SUPERVISOR_PID_FILE=""
M7_PROCESS_RECORDS=""
M7_OBSERVER_STATUS=""
M7_CLEANUP_REPORT=""
M7_AUTHORIZED_IDENTITIES=""
M7_TRACE_DIR=""
M7_TRACE_DIRECTORY_REPORT=""
M7_PREFLIGHT_TRACE_PREFIX=""
M7_TRACE_PREFIX=""
M7_TMPDIR=""
M7_ACTIVE_CLEANUP_REPORT=""
M7_TRACE_SYSCALLS="clone,clone3,fork,vfork,execve,openat,unlink,unlinkat,setns,unshare,exit,exit_group"
M7_STRACE_MODE="not_selected"
M7_STRACE_KILL_ON_EXIT_CAPABILITY="not_evaluated"
M7_STRACE_VERSION="not_evaluated"
M7_STRACE_KILL_ON_EXIT_ARGS=()

m7_select_strace_mode() {
  local help_file="$1"
  [[ -f "$help_file" ]] || return 1
  M7_STRACE_KILL_ON_EXIT_ARGS=()
  if grep -Fq -- '--kill-on-exit' "$help_file"; then
    M7_STRACE_MODE="native_kill_on_exit"
    M7_STRACE_KILL_ON_EXIT_CAPABILITY="supported"
    M7_STRACE_KILL_ON_EXIT_ARGS=(--kill-on-exit)
  else
    # 兼容模式仅省略当前 strace 不支持的原生退出联杀选项。
    M7_STRACE_MODE="compatibility_bounded_cleanup"
    M7_STRACE_KILL_ON_EXIT_CAPABILITY="unsupported"
  fi
}

m7_capture_strace_version() {
  local strace_bin="$1" version_output
  version_output="$("$strace_bin" --version 2>&1)" || return 1
  M7_STRACE_VERSION="${version_output%%$'\n'*}"
  [[ -n "$M7_STRACE_VERSION" ]]
}

m7_load_proc_identity() {
  local pid="$1" stat_line stat_rest env_line key value
  local -a stat_fields
  [[ "$pid" =~ ^[0-9]+$ && -r "/proc/$pid/stat" ]] || return 1
  stat_line="$(<"/proc/$pid/stat")" || return 1
  stat_rest="${stat_line##*) }"
  read -r -a stat_fields <<<"$stat_rest"
  [[ "${#stat_fields[@]}" -ge 20 ]] || return 1

  M7_PROC_PID="$pid"
  M7_PROC_STATE="${stat_fields[0]}"
  M7_PROC_PPID="${stat_fields[1]}"
  M7_PROC_PGID="${stat_fields[2]}"
  M7_PROC_SID="${stat_fields[3]}"
  M7_PROC_START_TICKS="${stat_fields[19]}"
  M7_PROC_EXE="$(readlink "/proc/$pid/exe" 2>/dev/null || true)"
  M7_PROC_IPC_NS="$(readlink "/proc/$pid/ns/ipc" 2>/dev/null || true)"
  M7_PROC_MNT_NS="$(readlink "/proc/$pid/ns/mnt" 2>/dev/null || true)"
  M7_PROC_PID_NS="$(readlink "/proc/$pid/ns/pid" 2>/dev/null || true)"
  M7_PROC_USER_NS="$(readlink "/proc/$pid/ns/user" 2>/dev/null || true)"
  M7_PROC_CMDLINE="$(tr '\0\t\n' '   ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  M7_PROC_RANK=""
  M7_PROC_LOCAL_RANK=""
  M7_PROC_WORLD_SIZE=""
  if [[ -r "/proc/$pid/environ" ]]; then
    while IFS='=' read -r key value; do
      case "$key" in
        RANK) M7_PROC_RANK="$value" ;;
        LOCAL_RANK) M7_PROC_LOCAL_RANK="$value" ;;
        WORLD_SIZE) M7_PROC_WORLD_SIZE="$value" ;;
      esac
    done < <(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null || true)
  fi

  case "$M7_PROC_CMDLINE" in
    *torchrun*|*torch.distributed.run*)
      M7_PROC_ROLE="torchrun"
      ;;
    *multiprocessing.resource_tracker*)
      M7_PROC_ROLE="resource_tracker_rank_${M7_PROC_RANK:-unknown}"
      ;;
    *multiprocessing.spawn*|*spawn_main*|*--multiprocessing-fork*)
      M7_PROC_ROLE="dataloader_worker_rank_${M7_PROC_RANK:-unknown}"
      ;;
    *autovla.cli.train*)
      M7_PROC_ROLE="rank_${M7_PROC_RANK:-unknown}"
      ;;
    *run_m6_runtime_request.py*)
      M7_PROC_ROLE="runtime_runner"
      ;;
    *strace*)
      M7_PROC_ROLE="strace"
      ;;
    *timeout*)
      M7_PROC_ROLE="timeout"
      ;;
    *)
      M7_PROC_ROLE="other"
      ;;
  esac
}

m7_append_loaded_identity() {
  local destination="$1" label="$2" trace_prefix="$3" authorization_basis="$4"
  local authorization_anchor_pid="$5" authorization_anchor_start="$6"
  local trace_present="false"
  [[ -f "$trace_prefix.$M7_PROC_PID" ]] && trace_present="true"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$label" "$(date +%s.%N)" "$M7_PROC_PID" "$M7_PROC_PPID" \
    "$M7_PROC_START_TICKS" "$M7_PROC_SID" "$M7_PROC_PGID" "$M7_PROC_STATE" \
    "$M7_PROC_ROLE" "$M7_PROC_EXE" "$M7_PROC_RANK" "$M7_PROC_LOCAL_RANK" \
    "$M7_PROC_WORLD_SIZE" "$M7_PROC_IPC_NS" "$M7_PROC_MNT_NS" "$M7_PROC_PID_NS" \
    "$M7_PROC_USER_NS" "$authorization_basis" "$authorization_anchor_pid" \
    "$authorization_anchor_start" "$trace_present" "$M7_PROC_CMDLINE" >>"$destination"
}

m7_snapshot_pid() {
  local label="$1" pid="$2" records="$3" authorized="$4" trace_prefix="$5"
  local authorization_basis="$6" authorization_anchor_pid="$7"
  local authorization_anchor_start="$8" expected_start="${9:-}"
  m7_load_proc_identity "$pid" || return 0
  [[ -z "$expected_start" || "$M7_PROC_START_TICKS" == "$expected_start" ]] || return 0
  m7_append_loaded_identity "$records" "$label" "$trace_prefix" \
    "$authorization_basis" "$authorization_anchor_pid" "$authorization_anchor_start"
  if [[ -n "$authorized" ]]; then
    m7_append_loaded_identity "$authorized" "$label" "$trace_prefix" \
      "$authorization_basis" "$authorization_anchor_pid" "$authorization_anchor_start"
  fi
}

m7_pid_has_live_root_ancestry() {
  local pid="$1" expected_start="$2" root_pid="$3" root_start="$4"
  local root_sid="$5" root_pgid="$6" current_pid="$1" parent_pid depth
  m7_load_proc_identity "$pid" || return 1
  [[ "$M7_PROC_START_TICKS" == "$expected_start" ]] || return 1
  for ((depth = 0; depth < 64; depth++)); do
    if [[ "$current_pid" == "$root_pid" ]]; then
      m7_load_proc_identity "$root_pid" || return 1
      [[ "$M7_PROC_START_TICKS" == "$root_start" \
        && "$M7_PROC_SID" == "$root_sid" \
        && "$M7_PROC_PGID" == "$root_pgid" ]] || return 1
      m7_load_proc_identity "$pid" || return 1
      [[ "$M7_PROC_START_TICKS" == "$expected_start" ]]
      return
    fi
    m7_load_proc_identity "$current_pid" || return 1
    parent_pid="$M7_PROC_PPID"
    [[ "$parent_pid" =~ ^[0-9]+$ && "$parent_pid" -gt 0 ]] || return 1
    current_pid="$parent_pid"
  done
  return 1
}

m7_authority_has_current_session() {
  local authorized="$1" pid="$2" start="$3" sid="$4" pgid="$5"
  awk -F '\t' -v pid="$pid" -v start="$start" -v sid="$sid" -v pgid="$pgid" '
    NR > 1 && $3 == pid && $5 == start && $6 == sid && $7 == pgid { found = 1 }
    END { exit(found ? 0 : 1) }
  ' "$authorized"
}

m7_authorize_live_candidate() {
  local label="$1" pid="$2" root_pid="$3" root_start="$4" root_sid="$5"
  local root_pgid="$6" records="$7" authorized="$8" trace_prefix="$9"
  local basis candidate_start
  m7_load_proc_identity "$pid" || return 0
  candidate_start="$M7_PROC_START_TICKS"
  if [[ "$pid" == "$root_pid" ]]; then
    [[ "$candidate_start" == "$root_start" \
      && "$M7_PROC_SID" == "$root_sid" \
      && "$M7_PROC_PGID" == "$root_pgid" \
      && "$root_sid" == "$pid" \
      && "$root_pgid" == "$pid" ]] || return 0
    basis="dedicated_root_session"
  else
    m7_pid_has_live_root_ancestry "$pid" "$candidate_start" "$root_pid" \
      "$root_start" "$root_sid" "$root_pgid" || return 0
    basis="live_root_ancestry"
  fi
  m7_snapshot_pid "$label" "$pid" "$records" "$authorized" "$trace_prefix" \
    "$basis" "$root_pid" "$root_start" "$candidate_start"
}

m7_snapshot_authorized_continuity() {
  local label="$1" records="$2" authorized="$3" trace_prefix="$4"
  local identities="$M7_TMPDIR/authorized-continuity.$$"
  local pid start anchor_pid anchor_start
  awk -F '\t' 'NR > 1 && $3 ~ /^[0-9]+$/ && $5 ~ /^[0-9]+$/ {
    key = $3 ":" $5
    if (!seen[key]++) print $3, $5, $19, $20
  }' "$authorized" >"$identities"
  while read -r pid start anchor_pid anchor_start; do
    m7_load_proc_identity "$pid" || continue
    [[ "$M7_PROC_START_TICKS" == "$start" ]] || continue
    if m7_authority_has_current_session "$authorized" "$pid" "$start" \
      "$M7_PROC_SID" "$M7_PROC_PGID"; then
      m7_snapshot_pid "$label" "$pid" "$records" "" "$trace_prefix" \
        "authorized_session_continuity" "$anchor_pid" "$anchor_start" "$start"
    fi
  done <"$identities"
}

m7_snapshot_live_candidates() {
  local label="$1" root_pid_file="$2" records="$3" authorized="$4"
  local trace_prefix="$5" tmpdir="$6"
  local candidates="$tmpdir/observer-candidates.$$" root_pid="" root_start=""
  local root_sid="" root_pgid="" pid
  : >"$candidates"
  if [[ -s "$root_pid_file" ]]; then
    read -r root_pid root_start root_sid root_pgid <"$root_pid_file" || true
  fi
  if [[ "$root_pid" =~ ^[0-9]+$ && "$root_start" =~ ^[0-9]+$ \
    && "$root_sid" =~ ^[0-9]+$ && "$root_pgid" =~ ^[0-9]+$ ]]; then
    ps -e -o pid=,ppid= 2>/dev/null | awk -v root="$root_pid" '
      { parent[$1] = $2 }
      END {
        selected[root] = 1
        for (iteration = 0; iteration < 64; iteration++) {
          for (candidate in parent) {
            if ((parent[candidate] in selected) && selected[parent[candidate]]) {
              selected[candidate] = 1
            }
          }
        }
        for (candidate in selected) {
          if (selected[candidate]) print candidate
        }
      }
    ' >>"$candidates" || true
  fi
  sort -nu -o "$candidates" "$candidates"
  while read -r pid; do
    [[ -n "$pid" ]] && m7_authorize_live_candidate "$label" "$pid" "$root_pid" \
      "$root_start" "$root_sid" "$root_pgid" "$records" "$authorized" \
      "$trace_prefix"
  done <"$candidates"
  if [[ -s "$authorized" ]]; then
    m7_snapshot_authorized_continuity "$label" "$records" "$authorized" \
      "$trace_prefix"
  fi
}

m7_observe_live() {
  local root_pid_file="$1" lifecycle_pid="$2" records="$3" authorized="$4"
  local trace_prefix="$5" status_file="$6" tmpdir="$7"
  local polls=0 reason="bounded_limit_reached"
  while [[ "$polls" -lt "$M7_OBSERVER_MAX_POLLS" ]]; do
    m7_snapshot_live_candidates "live_$polls" "$root_pid_file" "$records" \
      "$authorized" "$trace_prefix" "$tmpdir"
    polls=$((polls + 1))
    if ! kill -0 "$lifecycle_pid" 2>/dev/null; then
      m7_snapshot_live_candidates "lifecycle_exit" "$root_pid_file" "$records" \
        "$authorized" "$trace_prefix" "$tmpdir"
      reason="lifecycle_exited"
      break
    fi
    # 只读 observer 的短 yield 不位于候选进程树，也不是启动延迟或运行规避。
    /usr/bin/sleep "$M7_OBSERVER_INTERVAL_SECONDS"
  done
  {
    printf 'reason=%s\n' "$reason"
    printf 'polls=%s\n' "$polls"
    printf 'interval_seconds=%s\n' "$M7_OBSERVER_INTERVAL_SECONDS"
  } >"$status_file"
}

m7_start_supervised_command() {
  local root_pid_file="$1" timeout_value="$2" kill_after_value="$3"
  shift 3
  : >"$root_pid_file"
  /usr/bin/setsid --fork --wait /usr/bin/bash -c '
    root_pid_file=$1
    timeout_value=$2
    kill_after_value=$3
    shift 3
    stat_line=$(<"/proc/$$/stat")
    stat_rest=${stat_line##*) }
    read -r -a stat_fields <<<"$stat_rest"
    [[ ${#stat_fields[@]} -ge 20 ]] || exit 83
    printf "%s\t%s\t%s\t%s\n" "$$" "${stat_fields[19]}" \
      "${stat_fields[3]}" "${stat_fields[2]}" >"$root_pid_file"
    exec /usr/bin/timeout --signal=TERM --kill-after="$kill_after_value" \
      "$timeout_value" "$@"
  ' m7-supervisor "$root_pid_file" "$timeout_value" "$kill_after_value" "$@" &
  M7_WAIT_PID=$!
  if [[ -n "$M7_PROCESS_RECORDS" && -n "$M7_TRACE_PREFIX" ]]; then
    # $! 只有在仍是当前 shell 的 setsid 直接子进程时才构成 live 授权证据。
    if m7_load_proc_identity "$M7_WAIT_PID" \
      && [[ "$M7_PROC_PPID" == "$$" && "$M7_PROC_EXE" == "/usr/bin/setsid" ]]; then
      local wait_start="$M7_PROC_START_TICKS"
      m7_snapshot_pid "setsid_wait_wrapper" "$M7_WAIT_PID" "$M7_PROCESS_RECORDS" \
        "$M7_AUTHORIZED_IDENTITIES" "$M7_TRACE_PREFIX" "direct_wait_supervisor" \
        "$M7_WAIT_PID" "$wait_start" "$wait_start"
    fi
  fi
}

m7_start_supervised_strace() {
  local root_pid_file="$1" timeout_value="$2" kill_after_value="$3"
  local strace_bin="$4" trace_prefix="$5" trace_syscalls="$6"
  shift 6
  m7_start_supervised_command "$root_pid_file" "$timeout_value" "$kill_after_value" \
    "$strace_bin" "${M7_STRACE_KILL_ON_EXIT_ARGS[@]}" --interruptible=1 \
    -ff -ttt -yy -s 256 -e trace="$trace_syscalls" -o "$trace_prefix" "$@"
}

m7_start_observer() {
  m7_observe_live "$M7_SUPERVISOR_PID_FILE" "$M7_WAIT_PID" "$M7_PROCESS_RECORDS" \
    "$M7_AUTHORIZED_IDENTITIES" "$M7_TRACE_PREFIX" "$M7_OBSERVER_STATUS" \
    "$M7_TMPDIR" &
  M7_OBSERVER_PID=$!
}

m7_stop_observer() {
  local attempt
  [[ -n "$M7_OBSERVER_PID" ]] || return 0
  for ((attempt = 0; attempt < 40; attempt++)); do
    kill -0 "$M7_OBSERVER_PID" 2>/dev/null || break
    /usr/bin/sleep "$M7_OBSERVER_INTERVAL_SECONDS"
  done
  if kill -0 "$M7_OBSERVER_PID" 2>/dev/null; then
    kill -TERM "$M7_OBSERVER_PID" 2>/dev/null || true
  fi
  wait "$M7_OBSERVER_PID" 2>/dev/null || true
  M7_OBSERVER_PID=""
}

m7_pid_matches_start() {
  local pid="$1" expected_start="$2"
  m7_load_proc_identity "$pid" || return 1
  [[ "$M7_PROC_START_TICKS" == "$expected_start" ]]
}

m7_identity_matches_authority() {
  local pid="$1" expected_start="$2" expected_sid="$3" expected_pgid="$4"
  m7_load_proc_identity "$pid" || return 1
  [[ "$M7_PROC_START_TICKS" == "$expected_start" \
    && "$M7_PROC_SID" == "$expected_sid" \
    && "$M7_PROC_PGID" == "$expected_pgid" ]]
}

m7_write_unique_records() {
  local authorized="$1" unique="$2"
  awk -F '\t' '
    NR > 1 && $3 ~ /^[0-9]+$/ && $5 ~ /^[0-9]+$/ {
      key = $3 ":" $5 ":" $6 ":" $7
      if (!seen[key]++) print $3, $5, $6, $7, $9
    }
  ' "$authorized" >"$unique"
}

m7_recorded_alive() {
  local unique="$1" pid start sid pgid role
  while read -r pid start sid pgid role; do
    if m7_identity_matches_authority "$pid" "$start" "$sid" "$pgid"; then
      return 0
    fi
  done <"$unique"
  return 1
}

m7_signal_recorded() {
  local signal="$1" unique="$2" current_pgid pid start sid pgid role
  m7_load_proc_identity "$$" || return 1
  current_pgid="$M7_PROC_PGID"

  # 仅对仍由同一 start time 标识的专用 session leader 发送组信号。
  while read -r pid start sid pgid role; do
    if [[ "$pid" == "$sid" && "$pid" == "$pgid" && "$pgid" != "$current_pgid" ]] \
      && [[ "$pid" != "$$" ]] \
      && m7_identity_matches_authority "$pid" "$start" "$sid" "$pgid"; then
      kill -"$signal" -- "-$pgid" 2>/dev/null || true
    fi
  done <"$unique"

  # detached session 或 process group 逐 PID 处理，且先复核 start time 防止 PID 复用。
  while read -r pid start sid pgid role; do
    if [[ "$pid" != "$$" ]] \
      && m7_identity_matches_authority "$pid" "$start" "$sid" "$pgid"; then
      kill -"$signal" "$pid" 2>/dev/null || true
    fi
  done <"$unique"
}

m7_cleanup_recorded() {
  local records="$1" authorized="$2" root_pid_file="$3" trace_prefix="$4"
  local tmpdir="$5" report="$6"
  local unique="$tmpdir/recorded-identities.$$" attempt remaining=0
  m7_snapshot_live_candidates "cleanup_entry" "$root_pid_file" "$records" \
    "$authorized" "$trace_prefix" "$tmpdir"
  m7_write_unique_records "$authorized" "$unique"
  m7_signal_recorded TERM "$unique"
  for ((attempt = 0; attempt < M7_CLEANUP_POLLS; attempt++)); do
    m7_recorded_alive "$unique" || break
    /usr/bin/sleep "$M7_CLEANUP_INTERVAL_SECONDS"
  done
  if m7_recorded_alive "$unique"; then
    m7_signal_recorded KILL "$unique"
    for ((attempt = 0; attempt < M7_CLEANUP_POLLS; attempt++)); do
      m7_recorded_alive "$unique" || break
      /usr/bin/sleep "$M7_CLEANUP_INTERVAL_SECONDS"
    done
  fi
  while read -r pid start sid pgid role; do
    if m7_identity_matches_authority "$pid" "$start" "$sid" "$pgid"; then
      printf 'remaining\t%s\t%s\t%s\t%s\t%s\n' "$pid" "$start" "$sid" "$pgid" "$role" \
        >>"$report"
      remaining=$((remaining + 1))
    fi
  done <"$unique"
  {
    printf 'authorized_identity_count=%s\n' "$(wc -l <"$unique")"
    printf 'remaining_same_start_count=%s\n' "$remaining"
    if [[ "$remaining" -eq 0 ]]; then
      printf 'cleanup_status=COMPLETE\n'
    else
      printf 'cleanup_status=ORPHAN_CLEANUP_FAILED\n'
    fi
  } >>"$report"
  [[ "$remaining" -eq 0 ]]
}

m7_extract_effective_command() {
  local evidence_json="$1" expected_output="$2" expected_evidence="$3" artifact="$4"
  local run_dir="$5"
  python3 -S - "$evidence_json" "$expected_output" "$expected_evidence" "$artifact" "$run_dir" <<'PY'
import json
import sys
from pathlib import Path

evidence_path = Path(sys.argv[1]).resolve(strict=True)
expected_output = Path(sys.argv[2]).resolve(strict=True)
expected_evidence = Path(sys.argv[3]).resolve(strict=True)
artifact = Path(sys.argv[4])
run_dir = Path(sys.argv[5]).resolve(strict=True)
if run_dir not in expected_output.parents or run_dir not in expected_evidence.parents:
    raise SystemExit("effective command paths must remain under SANDBOX_RUN_DIR")
if evidence_path != expected_evidence:
    raise SystemExit("runtime evidence path differs from the governed override")
with evidence_path.open(encoding="utf-8") as stream:
    payload = json.load(stream)
command = payload.get("command")
if not isinstance(command, list) or not command or not all(
    isinstance(item, str) and item for item in command
):
    raise SystemExit("runtime evidence command must be a non-empty string array")
if Path(str(payload.get("output_dir", ""))).resolve() != expected_output:
    raise SystemExit("runtime evidence output_dir differs from the governed override")
expected_checkpoint = f"training.checkpoint.directory={expected_output}"
expected_metrics = f"training.logging.jsonl_path={expected_evidence.with_suffix('.metrics.jsonl')}"
checkpoint_overrides = [
    item for item in command if item.startswith("training.checkpoint.directory=")
]
metrics_overrides = [
    item for item in command if item.startswith("training.logging.jsonl_path=")
]
if checkpoint_overrides != [expected_checkpoint] or metrics_overrides != [expected_metrics]:
    raise SystemExit("effective command is missing governed output/evidence overrides")
rendered = {
    "authoritative_source": str(evidence_path),
    "command": command,
    "evidence_json": str(expected_evidence),
    "output_dir": str(expected_output),
    "verified": True,
}
artifact.write_text(json.dumps(rendered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

m7_evaluate_live_coverage() {
  local records="$1" authorized="$2" observer_status="$3" trace_prefix="$4" report="$5"
  python3 -S - "$records" "$authorized" "$observer_status" "$trace_prefix" "$report" <<'PY'
import json
import sys
from collections import defaultdict
from pathlib import Path

records_path = Path(sys.argv[1])
authorized_path = Path(sys.argv[2])
status_path = Path(sys.argv[3])
trace_prefix = Path(sys.argv[4])
report_path = Path(sys.argv[5])
required = {
    "torchrun": 1,
    "rank_0": 1,
    "rank_1": 1,
    "resource_tracker_rank_0": 1,
    "resource_tracker_rank_1": 1,
    "dataloader_worker_rank_0": 2,
    "dataloader_worker_rank_1": 2,
}
status = {}
if status_path.is_file():
    for line in status_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            status[key] = value
observed: dict[str, dict[tuple[int, int], dict[str, object]]] = defaultdict(dict)
authorized_identities: set[tuple[int, int]] = set()
authorized_lines = (
    authorized_path.read_text(encoding="utf-8").splitlines()
    if authorized_path.is_file()
    else []
)
for line in authorized_lines[1:]:
    fields = line.split("\t", 21)
    if len(fields) != 22:
        continue
    try:
        authorized_identities.add((int(fields[2]), int(fields[4])))
    except ValueError:
        continue
lines = records_path.read_text(encoding="utf-8").splitlines() if records_path.is_file() else []
for line in lines[1:]:
    fields = line.split("\t", 21)
    if len(fields) != 22:
        continue
    role = fields[8]
    try:
        pid = int(fields[2])
        start_ticks = int(fields[4])
    except ValueError:
        continue
    if (pid, start_ticks) not in authorized_identities:
        continue
    namespaces = fields[13:17]
    complete = (
        bool(fields[9])
        and all(namespaces)
        and fields[5].isdigit()
        and fields[6].isdigit()
        and all(value.endswith("]") and ":[" in value for value in namespaces)
    )
    trace_file = Path(f"{trace_prefix}.{pid}")
    trace_exec = False
    if trace_file.is_file():
        try:
            trace_exec = "execve(" in trace_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            trace_exec = False
    if complete and trace_exec:
        observed[role][(pid, start_ticks)] = {
            "exe": fields[9],
            "authorization_anchor_pid": fields[18],
            "authorization_anchor_start_ticks": fields[19],
            "authorization_basis": fields[17],
            "ipc_ns": fields[13],
            "mnt_ns": fields[14],
            "pgid": fields[6],
            "pid": pid,
            "pid_ns": fields[15],
            "ppid": fields[3],
            "rank": fields[10],
            "sid": fields[5],
            "start_ticks": start_ticks,
            "trace_file": str(trace_file),
            "user_ns": fields[16],
        }
counts = {role: len(observed.get(role, {})) for role in required}
missing = {
    role: {"observed": counts[role], "required": count}
    for role, count in required.items()
    if counts[role] < count
}
if status.get("reason") != "lifecycle_exited":
    missing["observer_completion"] = {
        "observed": status.get("reason", "missing"),
        "required": "lifecycle_exited",
    }
payload = {
    "complete": not missing,
    "missing": missing,
    "observed": {
        role: list(identities.values()) for role, identities in sorted(observed.items())
    },
    "observer": status,
    "required": required,
}
report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
raise SystemExit(0 if not missing else 1)
PY
}

m7_write_runtime_status() {
  local path="$1" traced_rc="$2" final_rc="$3" cleanup_status="$4" coverage_status="$5"
  local command_status="$6"
  {
    printf 'status=DIAGNOSTIC_COMMAND_FINISHED\n'
    printf 'traced_exit_code=%s\n' "$traced_rc"
    printf 'final_exit_code=%s\n' "$final_rc"
    printf 'cleanup_status=%s\n' "$cleanup_status"
    printf 'live_coverage_status=%s\n' "$coverage_status"
    printf 'effective_command_status=%s\n' "$command_status"
    printf 'strace_mode=%s\n' "$M7_STRACE_MODE"
    printf 'strace_kill_on_exit_capability=%s\n' \
      "$M7_STRACE_KILL_ON_EXIT_CAPABILITY"
    printf 'strace_version=%s\n' "$M7_STRACE_VERSION"
    printf 'trace_timeout_seconds=90\n'
    if [[ "$traced_rc" -eq 124 || "$traced_rc" -eq 137 ]]; then
      printf 'timed_out=true\n'
    else
      printf 'timed_out=false\n'
    fi
    printf 'finished_at=%s\n' "$(date --iso-8601=seconds)"
  } >"$path"
}

m7_prepare_trace_scope() {
  local run_dir="$1" run_real trace_parent trace_parent_real trace_dir trace_real
  local -a initial_entries
  trace_parent="$run_dir/logs"
  mkdir -p "$trace_parent" "$run_dir/outputs"
  run_real="$(/usr/bin/realpath -e -- "$run_dir")" || return 1
  trace_parent_real="$(/usr/bin/realpath -e -- "$trace_parent")" || return 1
  if [[ "$trace_parent_real" != "$run_real/logs" ]]; then
    printf 'status=FAIL\ndiagnostic_field=trace_directory\nreason=logs_not_under_run_dir\n' \
      >"$M7_TRACE_DIRECTORY_REPORT"
    return 1
  fi
  trace_dir="$(/usr/bin/mktemp -d -- "$trace_parent/m7-ddp-semlock.XXXXXXXX")" \
    || return 1
  trace_real="$(/usr/bin/realpath -e -- "$trace_dir")" || return 1
  if [[ "$trace_real" != "$trace_parent_real/"* ]]; then
    printf 'status=FAIL\ndiagnostic_field=trace_directory\nreason=trace_dir_escape\n' \
      >"$M7_TRACE_DIRECTORY_REPORT"
    return 1
  fi
  shopt -s dotglob nullglob
  initial_entries=("$trace_real"/*)
  shopt -u dotglob nullglob
  if [[ "${#initial_entries[@]}" -ne 0 ]]; then
    printf 'status=FAIL\ndiagnostic_field=trace_directory\nreason=not_initially_empty\n' \
      >"$M7_TRACE_DIRECTORY_REPORT"
    return 1
  fi
  M7_TRACE_DIR="$trace_real"
  M7_PREFLIGHT_TRACE_PREFIX="$M7_TRACE_DIR/preflight"
  M7_TRACE_PREFIX="$M7_TRACE_DIR/trace"
  {
    printf 'status=READY\n'
    printf 'trace_directory=%s\n' "$M7_TRACE_DIR"
    printf 'preflight_trace_prefix=%s\n' "$M7_PREFLIGHT_TRACE_PREFIX"
    printf 'trace_prefix=%s\n' "$M7_TRACE_PREFIX"
    printf 'initial_entry_count=0\n'
  } >"$M7_TRACE_DIRECTORY_REPORT"
}

m7_abort_supervision() {
  local requested_rc="$1" cleanup_status="COMPLETE"
  trap - EXIT INT TERM
  m7_stop_observer
  if [[ -n "$M7_PROCESS_RECORDS" && -f "$M7_PROCESS_RECORDS" ]]; then
    if ! m7_cleanup_recorded "$M7_PROCESS_RECORDS" "$M7_AUTHORIZED_IDENTITIES" \
      "$M7_SUPERVISOR_PID_FILE" "$M7_TRACE_PREFIX" "$M7_TMPDIR" \
      "${M7_ACTIVE_CLEANUP_REPORT:-$M7_CLEANUP_REPORT}"; then
      requested_rc="$M7_ORPHAN_CLEANUP_EXIT"
      cleanup_status="ORPHAN_CLEANUP_FAILED"
    fi
  fi
  if [[ -n "${M7_RUNTIME_STATUS:-}" ]]; then
    m7_write_runtime_status "$M7_RUNTIME_STATUS" "$requested_rc" "$requested_rc" \
      "$cleanup_status" "NOT_EVALUATED" "NOT_EVALUATED"
  fi
  exit "$requested_rc"
}

m7_prepare_supervision_files() {
  local run_dir="$1"
  M7_TMPDIR="$run_dir/tmp"
  M7_SUPERVISOR_PID_FILE="$run_dir/outputs/trace-supervisor.pid"
  M7_PROCESS_RECORDS="$run_dir/outputs/process-namespace-live.tsv"
  M7_AUTHORIZED_IDENTITIES="$run_dir/outputs/process-authorized-identities.tsv"
  M7_OBSERVER_STATUS="$run_dir/outputs/process-observer-status.txt"
  M7_CLEANUP_REPORT="$run_dir/outputs/process-cleanup.txt"
  M7_ACTIVE_CLEANUP_REPORT="$M7_CLEANUP_REPORT"
  M7_TRACE_DIRECTORY_REPORT="$run_dir/outputs/trace-directory.txt"
  printf 'label\tobserved_at\tpid\tppid\tstart_ticks\tsid\tpgid\tstate\trole\texe\trank\tlocal_rank\tworld_size\tipc_ns\tmnt_ns\tpid_ns\tuser_ns\tauthorization_basis\tauthorization_anchor_pid\tauthorization_anchor_start_ticks\ttrace_file_present\tcmdline\n' \
    >"$M7_PROCESS_RECORDS"
  printf 'label\tobserved_at\tpid\tppid\tstart_ticks\tsid\tpgid\tstate\trole\texe\trank\tlocal_rank\tworld_size\tipc_ns\tmnt_ns\tpid_ns\tuser_ns\tauthorization_basis\tauthorization_anchor_pid\tauthorization_anchor_start_ticks\ttrace_file_present\tcmdline\n' \
    >"$M7_AUTHORIZED_IDENTITIES"
  : >"$M7_SUPERVISOR_PID_FILE"
  : >"$M7_CLEANUP_REPORT"
}

m7_run_supervision_harness() {
  local run_dir="$1" timeout_value="$2" command_rc cleanup_status="COMPLETE"
  shift 2
  mkdir -p "$run_dir/logs" "$run_dir/outputs" "$run_dir/tmp"
  m7_prepare_supervision_files "$run_dir"
  M7_RUNTIME_STATUS="$run_dir/outputs/harness-status.txt"
  if ! m7_prepare_trace_scope "$run_dir"; then
    m7_write_runtime_status "$M7_RUNTIME_STATUS" "$M7_TRACE_SCOPE_EXIT" \
      "$M7_TRACE_SCOPE_EXIT" "NOT_STARTED" "HARNESS_NOT_APPLICABLE" \
      "HARNESS_NOT_APPLICABLE"
    return "$M7_TRACE_SCOPE_EXIT"
  fi
  # 仅测试 harness 可预置同前缀 stale 文件，用于证明文件名不授予 PID 权限。
  if [[ -n "${M7_HARNESS_STALE_TRACE_PID:-}" ]]; then
    if [[ ! "$M7_HARNESS_STALE_TRACE_PID" =~ ^[0-9]+$ ]]; then
      return 2
    fi
    printf '0.000000 execve("/stale/unrelated", [], []) = 0\n' \
      >"$M7_TRACE_PREFIX.$M7_HARNESS_STALE_TRACE_PID"
  fi
  if [[ -n "${M7_HARNESS_STRACE_BIN:-}" || -n "${M7_HARNESS_STRACE_HELP:-}" ]]; then
    if [[ -z "${M7_HARNESS_STRACE_BIN:-}" \
      || -z "${M7_HARNESS_STRACE_HELP:-}" ]]; then
      return 2
    fi
    m7_select_strace_mode "$M7_HARNESS_STRACE_HELP" || return 2
    m7_capture_strace_version "$M7_HARNESS_STRACE_BIN" || return 2
    m7_start_supervised_strace "$M7_SUPERVISOR_PID_FILE" "$timeout_value" "10s" \
      "$M7_HARNESS_STRACE_BIN" "$M7_TRACE_PREFIX" "$M7_TRACE_SYSCALLS" "$@"
  else
    m7_start_supervised_command "$M7_SUPERVISOR_PID_FILE" "$timeout_value" "10s" "$@"
  fi
  m7_start_observer
  printf 'ready\n' >"$run_dir/outputs/harness-ready.txt"
  trap 'm7_abort_supervision 130' INT
  trap 'm7_abort_supervision 143' TERM
  trap 'm7_abort_supervision $?' EXIT
  set +e
  wait "$M7_WAIT_PID"
  command_rc=$?
  set -e
  m7_stop_observer
  trap - EXIT INT TERM
  if ! m7_cleanup_recorded "$M7_PROCESS_RECORDS" "$M7_AUTHORIZED_IDENTITIES" \
    "$M7_SUPERVISOR_PID_FILE" "$M7_TRACE_PREFIX" "$M7_TMPDIR" \
    "$M7_CLEANUP_REPORT"; then
    cleanup_status="ORPHAN_CLEANUP_FAILED"
    m7_write_runtime_status "$M7_RUNTIME_STATUS" "$command_rc" "$M7_ORPHAN_CLEANUP_EXIT" \
      "$cleanup_status" "HARNESS_NOT_APPLICABLE" "HARNESS_NOT_APPLICABLE"
    return "$M7_ORPHAN_CLEANUP_EXIT"
  fi
  m7_write_runtime_status "$M7_RUNTIME_STATUS" "$command_rc" "$command_rc" \
    "$cleanup_status" "HARNESS_NOT_APPLICABLE" "HARNESS_NOT_APPLICABLE"
  return "$command_rc"
}

m7_validate_runtime_request() {
  local request_path="$1"
  python3 -S - "$request_path" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as stream:
        request = json.load(stream)
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"runtime request could not be parsed: {exc}") from exc
runtime_python = request.get("runtime_python")
if not isinstance(runtime_python, str) or not runtime_python:
    raise SystemExit("runtime request field runtime_python must be a non-empty string")
# 仅允许两个分布式目标；运行请求本身决定实际策略。
target = request.get("target")
if not isinstance(target, str) or target not in {"ddp", "fsdp2"}:
    raise SystemExit("runtime request field target must be exactly ddp or fsdp2")
if request.get("max_steps") != 2:
    raise SystemExit("runtime request field max_steps must be exactly 2")
if request.get("offline") is not True:
    raise SystemExit("runtime request field offline must be true")
print(runtime_python)
PY
}

m7_main() {
  : "${SANDBOX_PROJECT_ROOT:?SANDBOX_PROJECT_ROOT is required}"
  : "${SANDBOX_RUN_DIR:?SANDBOX_RUN_DIR is required}"
  : "${SANDBOX_RUNTIME_REQUEST:?SANDBOX_RUNTIME_REQUEST is required}"

  umask 077
  mkdir -p "$SANDBOX_RUN_DIR/logs" "$SANDBOX_RUN_DIR/outputs/checkpoints" \
    "$SANDBOX_RUN_DIR/tmp" "$SANDBOX_RUN_DIR/home" "$SANDBOX_RUN_DIR/cache"
  export HOME="$SANDBOX_RUN_DIR/home"
  export TMPDIR="$SANDBOX_RUN_DIR/tmp"
  export XDG_CACHE_HOME="$SANDBOX_RUN_DIR/cache"
  export HF_HOME="$SANDBOX_RUN_DIR/cache/huggingface"
  export TORCH_HOME="$SANDBOX_RUN_DIR/cache/torch"
  export HF_DATASETS_OFFLINE=1
  export HF_HUB_OFFLINE=1
  export TRANSFORMERS_OFFLINE=1
  export WANDB_MODE=disabled
  export PYTHONNOUSERSITE=1
  export PYTHONDONTWRITEBYTECODE=1

  cd "$SANDBOX_PROJECT_ROOT"
  local runtime_python
  runtime_python="$(m7_validate_runtime_request "$SANDBOX_RUNTIME_REQUEST")"
  if [[ "$runtime_python" != /* ]]; then
    echo "runtime request field runtime_python must be an absolute path" >&2
    return 2
  fi
  if [[ ! -f "$runtime_python" || ! -x "$runtime_python" ]]; then
    echo "runtime request field runtime_python must be an executable file: $runtime_python" >&2
    return 2
  fi

  local trace_timeout_seconds=90
  local preflight_report="$SANDBOX_RUN_DIR/outputs/trace-preflight.txt"
  local preflight_cleanup="$SANDBOX_RUN_DIR/outputs/trace-preflight-process-cleanup.txt"
  local strace_help="$SANDBOX_RUN_DIR/outputs/strace-help.txt"
  local shm_mount="$SANDBOX_RUN_DIR/outputs/dev-shm-mount.txt"
  local shm_inventory="$SANDBOX_RUN_DIR/outputs/dev-shm-sem-inventory.tsv"
  local trace_clues="$SANDBOX_RUN_DIR/outputs/trace-process-events.tsv"
  local runtime_evidence="$SANDBOX_RUN_DIR/outputs/runtime_evidence.json"
  local effective_command="$SANDBOX_RUN_DIR/outputs/effective-command.json"
  local coverage_report="$SANDBOX_RUN_DIR/outputs/live-role-namespace-coverage.json"
  local trace_rc final_rc cleanup_status="COMPLETE" coverage_status="COMPLETE"
  local command_status="COMPLETE" ptrace_rc preflight_cleanup_status="COMPLETE"
  M7_RUNTIME_STATUS="$SANDBOX_RUN_DIR/outputs/trace-runtime-status.txt"
  m7_prepare_supervision_files "$SANDBOX_RUN_DIR"

  if [[ ! -d /dev/shm ]]; then
    printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=dev_shm\nreason=directory_unavailable\n' \
      >"$preflight_report"
    return 78
  fi
  local tool
  for tool in /usr/bin/strace /usr/bin/timeout /usr/bin/setsid /usr/bin/bash \
    /usr/bin/sleep /usr/bin/mktemp /usr/bin/realpath /bin/true; do
    if [[ ! -x "$tool" ]]; then
      printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=tool_executable\nmissing_or_not_executable=%s\n' \
        "$tool" >"$preflight_report"
      return 78
    fi
  done
  if ! m7_prepare_trace_scope "$SANDBOX_RUN_DIR"; then
    printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=trace_directory\nreason=unique_empty_scope_unavailable\n' \
      >"$preflight_report"
    return 78
  fi
  if ! /usr/bin/strace --help >"$strace_help" 2>&1; then
    printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=strace_help\nreason=unavailable\n' \
      >"$preflight_report"
    return 78
  fi
  if ! m7_select_strace_mode "$strace_help"; then
    printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=strace_help\nreason=malformed\n' \
      >"$preflight_report"
    return 78
  fi
  if ! m7_capture_strace_version /usr/bin/strace; then
    printf 'status=BLOCKED_TOOL_ENV\ndiagnostic_field=strace_version\nreason=unavailable\n' \
      >"$preflight_report"
    return 78
  fi
  {
    printf 'status=CHECKING\n'
    printf 'strace=/usr/bin/strace\n'
    printf 'strace_mode=%s\n' "$M7_STRACE_MODE"
    printf 'strace_kill_on_exit_capability=%s\n' \
      "$M7_STRACE_KILL_ON_EXIT_CAPABILITY"
    printf 'strace_version=%s\n' "$M7_STRACE_VERSION"
    printf 'strace_help_path=%s\n' "$strace_help"
    printf 'trace_timeout_seconds=%s\n' "$trace_timeout_seconds"
    printf 'trace_syscalls=%s\n' "$M7_TRACE_SYSCALLS"
  } >"$preflight_report"
  M7_ACTIVE_CLEANUP_REPORT="$preflight_cleanup"
  : >"$preflight_cleanup"
  m7_start_supervised_strace "$M7_SUPERVISOR_PID_FILE" "5s" "2s" \
    /usr/bin/strace "$M7_PREFLIGHT_TRACE_PREFIX" "$M7_TRACE_SYSCALLS" /bin/true
  m7_start_observer
  trap 'm7_abort_supervision 130' INT
  trap 'm7_abort_supervision 143' TERM
  trap 'm7_abort_supervision $?' EXIT
  set +e
  wait "$M7_WAIT_PID"
  ptrace_rc=$?
  set -e
  m7_stop_observer
  trap - EXIT INT TERM
  if ! m7_cleanup_recorded "$M7_PROCESS_RECORDS" "$M7_AUTHORIZED_IDENTITIES" \
    "$M7_SUPERVISOR_PID_FILE" "$M7_TRACE_PREFIX" "$M7_TMPDIR" \
    "$preflight_cleanup"; then
    preflight_cleanup_status="ORPHAN_CLEANUP_FAILED"
    {
      printf 'status=FAIL\n'
      printf 'diagnostic_field=ptrace_child_preflight_cleanup\n'
      printf 'reason=authorized_identity_remains\n'
    } >>"$preflight_report"
    m7_write_runtime_status "$M7_RUNTIME_STATUS" "$ptrace_rc" \
      "$M7_ORPHAN_CLEANUP_EXIT" "$preflight_cleanup_status" \
      "NOT_EVALUATED" "NOT_EVALUATED"
    return "$M7_ORPHAN_CLEANUP_EXIT"
  fi
  M7_ACTIVE_CLEANUP_REPORT="$M7_CLEANUP_REPORT"
  if [[ "$ptrace_rc" -ne 0 ]]; then
    {
      printf 'status=BLOCKED_TOOL_ENV\n'
      printf 'diagnostic_field=ptrace_child_preflight\n'
      printf 'ptrace_child_preflight_exit_code=%s\n' "$ptrace_rc"
    } >>"$preflight_report"
    return 78
  fi
  {
    printf 'status=READY\n'
    printf 'ptrace_child_preflight_exit_code=0\n'
    printf 'ptrace_child_preflight_cleanup_status=COMPLETE\n'
    printf 'ptrace_child_preflight_residual_authorized_identities=0\n'
  } >>"$preflight_report"

  {
    printf 'captured_at=%s\n' "$(date --iso-8601=seconds)"
    printf '%s\n' '--- findmnt /dev/shm ---'
    findmnt -T /dev/shm -o TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION -n 2>/dev/null || true
    printf '%s\n' '--- mountinfo /dev/shm ---'
    awk '$5 == "/dev/shm" || index($5, "/dev/shm/") == 1 { print }' /proc/self/mountinfo
    printf '%s\n' '--- stat /dev/shm ---'
    stat -Lc 'path=%n device=%D inode=%i mode=%a user=%U group=%G' /dev/shm
  } >"$shm_mount"
  : >"$shm_inventory"
  printf 'snapshot\tbefore_runtime\t%s\n' "$(date +%s.%N)" >>"$shm_inventory"
  shopt -s nullglob
  local sem_path
  for sem_path in /dev/shm/sem.*; do
    stat -Lc $'entry\t%n\t%i\t%U\t%G\t%a\t%s\t%Y' "$sem_path" >>"$shm_inventory" \
      2>/dev/null || true
  done
  shopt -u nullglob

  m7_start_supervised_strace "$M7_SUPERVISOR_PID_FILE" \
    "${trace_timeout_seconds}s" "10s" /usr/bin/strace "$M7_TRACE_PREFIX" \
    "$M7_TRACE_SYSCALLS" \
    "$runtime_python" scripts/runtime/run_m6_runtime_request.py \
    --request "$SANDBOX_RUNTIME_REQUEST" \
    --output-dir "$SANDBOX_RUN_DIR/outputs/checkpoints" \
    --evidence-json "$runtime_evidence"
  m7_start_observer
  trap 'm7_abort_supervision 130' INT
  trap 'm7_abort_supervision 143' TERM
  trap 'm7_abort_supervision $?' EXIT
  set +e
  wait "$M7_WAIT_PID"
  trace_rc=$?
  set -e
  m7_stop_observer
  trap - EXIT INT TERM

  if ! m7_cleanup_recorded "$M7_PROCESS_RECORDS" "$M7_AUTHORIZED_IDENTITIES" \
    "$M7_SUPERVISOR_PID_FILE" "$M7_TRACE_PREFIX" "$M7_TMPDIR" \
    "$M7_CLEANUP_REPORT"; then
    cleanup_status="ORPHAN_CLEANUP_FAILED"
    final_rc="$M7_ORPHAN_CLEANUP_EXIT"
  else
    final_rc="$trace_rc"
  fi

  local trace_file trace_pid
  local authorized_trace_pids="$M7_TMPDIR/trace-clue-authorized-pids"
  : >"$trace_clues"
  awk -F '\t' 'NR > 1 && $3 ~ /^[0-9]+$/ && !seen[$3]++ { print $3 }' \
    "$M7_AUTHORIZED_IDENTITIES" | sort -nu >"$authorized_trace_pids"
  while read -r trace_pid; do
    trace_file="$M7_TRACE_PREFIX.$trace_pid"
    [[ -f "$trace_file" ]] || continue
    awk -v source="$trace_file" '
      /clone|clone3|fork|vfork|execve|setns|unshare/ { print source "\t" $0 }
    ' "$trace_file" >>"$trace_clues"
  done <"$authorized_trace_pids"

  if [[ "$cleanup_status" == "COMPLETE" ]]; then
    if ! m7_extract_effective_command "$runtime_evidence" \
      "$SANDBOX_RUN_DIR/outputs/checkpoints" "$runtime_evidence" "$effective_command" \
      "$SANDBOX_RUN_DIR"; then
      command_status="MISSING_OR_MALFORMED"
      final_rc="$M7_COMMAND_EVIDENCE_EXIT"
    fi
    if ! m7_evaluate_live_coverage "$M7_PROCESS_RECORDS" "$M7_AUTHORIZED_IDENTITIES" \
      "$M7_OBSERVER_STATUS" "$M7_TRACE_PREFIX" "$coverage_report"; then
      coverage_status="INCOMPLETE"
      [[ "$final_rc" -eq "$M7_COMMAND_EVIDENCE_EXIT" ]] || final_rc="$M7_EVIDENCE_INCOMPLETE_EXIT"
    fi
  else
    command_status="NOT_EVALUATED"
    coverage_status="NOT_EVALUATED"
  fi

  printf 'snapshot\tafter_runtime\t%s\n' "$(date +%s.%N)" >>"$shm_inventory"
  shopt -s nullglob
  for sem_path in /dev/shm/sem.*; do
    stat -Lc $'entry\t%n\t%i\t%U\t%G\t%a\t%s\t%Y' "$sem_path" >>"$shm_inventory" \
      2>/dev/null || true
  done
  shopt -u nullglob
  m7_write_runtime_status "$M7_RUNTIME_STATUS" "$trace_rc" "$final_rc" "$cleanup_status" \
    "$coverage_status" "$command_status"
  return "$final_rc"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  m7_main "$@"
fi
