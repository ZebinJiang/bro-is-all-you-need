#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/slurm/m13_n1d6_cache_prime.sh \
    --checkout-root <checkout> \
    --workspace-root <workspace> \
    --lock-receipt runs/<task>/<lock>.json \
    --output-dir runs/<task>/<cache-prime-output> \
    --allow-network
USAGE
}

CHECKOUT_ROOT=""
WORKSPACE_ROOT=""
LOCK_RECEIPT=""
OUTPUT_DIR=""
ALLOW_NETWORK=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkout-root) CHECKOUT_ROOT="${2:-}"; shift 2 ;;
    --workspace-root) WORKSPACE_ROOT="${2:-}"; shift 2 ;;
    --lock-receipt) LOCK_RECEIPT="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --allow-network) ALLOW_NETWORK=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
[[ -n "$CHECKOUT_ROOT" && -n "$WORKSPACE_ROOT" && -n "$LOCK_RECEIPT" && -n "$OUTPUT_DIR" ]] || {
  echo "all path arguments are required" >&2
  exit 2
}
[[ "$ALLOW_NETWORK" -eq 1 ]] || {
  echo "cache prime requires explicit --allow-network" >&2
  exit 2
}

CHECKOUT_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "$CHECKOUT_ROOT")"
OUTPUT_REAL="$(python3 -S -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=False))' "$OUTPUT_DIR")"
case "$OUTPUT_REAL" in
  "$CHECKOUT_REAL"/runs/*) ;;
  *) echo "--output-dir must remain below checkout runs/" >&2; exit 2 ;;
esac
mkdir -p "$OUTPUT_REAL"
cd "$CHECKOUT_REAL"

# 该脚本是唯一显式联网入口;compute sbatch 不调用它。
COMMAND=(
  python3 -S -m autovla.cli.env
  --checkout-root "$CHECKOUT_REAL"
  --workspace-root "$WORKSPACE_ROOT"
  cache gr00t_n1d6_runtime
  --lock-receipt "$LOCK_RECEIPT"
  --allow-network
)
printf 'cache-prime command:' > "$OUTPUT_REAL/raw-command.txt"
printf ' %q' "${COMMAND[@]}" >> "$OUTPUT_REAL/raw-command.txt"
printf '\n' >> "$OUTPUT_REAL/raw-command.txt"
"${COMMAND[@]}" > "$OUTPUT_REAL/result.json"
