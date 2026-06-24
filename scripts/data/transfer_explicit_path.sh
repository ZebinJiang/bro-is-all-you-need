#!/usr/bin/env bash
set -euo pipefail

usage(){ cat <<'USAGE'
Usage:
  scripts/data/transfer_explicit_path.sh \
    --run-id <safe_id> \
    --direction <inbound|outbound> \
    --source <path> \
    --destination <path> \
    [--mode <copy|symlink>] \
    [--dry-run|--execute]

Default is --dry-run. Use --execute only after explicit user authorization.
USAGE
}

RUN_ID=""
DIRECTION=""
SOURCE=""
DESTINATION=""
MODE="copy"
EXECUTE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    --direction) DIRECTION="${2:-}"; shift 2 ;;
    --source) SOURCE="${2:-}"; shift 2 ;;
    --destination) DESTINATION="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --dry-run) EXECUTE=0; shift ;;
    --execute) EXECUTE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$RUN_ID" && -n "$DIRECTION" && -n "$SOURCE" && -n "$DESTINATION" ]] || { usage >&2; exit 2; }
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid run id: $RUN_ID" >&2; exit 2; }
[[ "$DIRECTION" == "inbound" || "$DIRECTION" == "outbound" ]] || { echo "direction must be inbound or outbound" >&2; exit 2; }
[[ "$MODE" == "copy" || "$MODE" == "symlink" ]] || { echo "mode must be copy or symlink" >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="$ROOT_DIR/runs/transfers/$RUN_ID"
mkdir -p "$RUN_DIR/logs" "$RUN_DIR/outputs"

SOURCE_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$SOURCE")"
DEST_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$DESTINATION")"

if [[ "$DIRECTION" == "inbound" ]]; then
  case "$DEST_REAL" in
    "$ROOT_DIR"/datasets/readonly/*|"$ROOT_DIR"/datasets/working/*|"$ROOT_DIR"/datasets/cache/*|"$ROOT_DIR"/assets/input/*) ;;
    *) echo "Inbound destination should be under datasets/{readonly,working,cache}/ or assets/input/: $DEST_REAL" >&2; exit 2 ;;
  esac
fi

if [[ "$DIRECTION" == "outbound" ]]; then
  case "$SOURCE_REAL" in
    "$ROOT_DIR"/*) ;;
    *) echo "Outbound source must be inside project root: $SOURCE_REAL" >&2; exit 2 ;;
  esac
fi

SIZE_ESTIMATE="unknown"
if [[ -e "$SOURCE_REAL" ]]; then
  SIZE_ESTIMATE="$(du -sh "$SOURCE_REAL" 2>/dev/null | awk '{print $1}' || true)"
fi

COMMAND_TEXT=""
if [[ "$MODE" == "copy" ]]; then
  COMMAND_TEXT="cp -a '$SOURCE_REAL' '$DEST_REAL'"
else
  COMMAND_TEXT="ln -s '$SOURCE_REAL' '$DEST_REAL'"
fi

cat > "$RUN_DIR/logs/transfer_command.txt" <<EOT
run_id=$RUN_ID
direction=$DIRECTION
mode=$MODE
source=$SOURCE_REAL
destination=$DEST_REAL
size_estimate=$SIZE_ESTIMATE
execute=$EXECUTE
command=$COMMAND_TEXT
note=External path access is a one-time user-authorized exception. Do not reuse after this task without a new explicit instruction.
EOT

python3 -S - "$RUN_DIR" "$RUN_ID" "$DIRECTION" "$MODE" "$SOURCE_REAL" "$DEST_REAL" "$SIZE_ESTIMATE" "$EXECUTE" <<'PYCODE'
import json, sys
from pathlib import Path
run_dir = Path(sys.argv[1])
manifest = {
    'run_id': sys.argv[2],
    'direction': sys.argv[3],
    'mode': sys.argv[4],
    'source': sys.argv[5],
    'destination': sys.argv[6],
    'size_estimate': sys.argv[7],
    'executed': sys.argv[8] == '1',
    'one_time_external_path_exception': True,
}
with (run_dir / 'outputs' / 'transfer_manifest.json').open('w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
    f.write('\n')
PYCODE

if [[ "$EXECUTE" -eq 0 ]]; then
  echo "DRY RUN: no transfer executed"
  cat "$RUN_DIR/logs/transfer_command.txt"
  exit 0
fi

if [[ "$MODE" == "copy" ]]; then
  mkdir -p "$(dirname "$DEST_REAL")"
  cp -a "$SOURCE_REAL" "$DEST_REAL"
else
  mkdir -p "$(dirname "$DEST_REAL")"
  ln -s "$SOURCE_REAL" "$DEST_REAL"
fi

echo "transfer complete: $RUN_DIR/outputs/transfer_manifest.json"
