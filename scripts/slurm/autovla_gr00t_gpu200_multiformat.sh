#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/autovla_gr00t_gpu200_multiformat.sh \
    --config <path> \
    --output-dir <path> \
    [--python-bin <path>]

Render a compute-ready sbatch wrapper for the bounded GR00T GPU200 telemetry tranche.
This script does not submit a Slurm job.
USAGE
}

CONFIG_PATH=""
OUTPUT_DIR=""
PYTHON_BIN="${AUTOVLA_PROJECT_PYTHON:-python}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

[[ -n "$CONFIG_PATH" ]] || { echo "--config is required" >&2; usage; exit 2; }
[[ -n "$OUTPUT_DIR" ]] || { echo "--output-dir is required" >&2; usage; exit 2; }
[[ -f "$CONFIG_PATH" ]] || { echo "config not found: $CONFIG_PATH" >&2; exit 2; }

exec "$PYTHON_BIN" -m autovla.training.telemetry render-slurm \
  --config "$CONFIG_PATH" \
  --output-dir "$OUTPUT_DIR"
