#!/usr/bin/env bash
set -euo pipefail

usage(){ echo "Usage: scripts/sandbox/run_local_sandbox.sh --run-id <id> -- <command> [args...]"; }
RUN_ID=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$RUN_ID" ]] || { echo "--run-id is required" >&2; exit 2; }
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid run id: $RUN_ID" >&2; exit 2; }
[[ $# -gt 0 ]] || { echo "Command is required after --" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="$ROOT_DIR/runs/local/$RUN_ID"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/outputs" "$RUN_DIR/tmp" "$RUN_DIR/home"

export SANDBOX_PROJECT_ROOT="$ROOT_DIR"
export SANDBOX_RUN_ID="$RUN_ID"
export SANDBOX_RUN_DIR="$RUN_DIR"
export TMPDIR="$RUN_DIR/tmp"
export HOME="$RUN_DIR/home"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

cd "$ROOT_DIR"
"$@"
