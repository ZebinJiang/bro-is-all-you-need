#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 2

VENV="$ROOT/runs/tmp/m1-tool-venv"
PY="$VENV/bin/python"
PYRIGHT="$VENV/bin/pyright"
TASK_ROOT="$ROOT/runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001"
READY_STAMP="$TASK_ROOT/stamps/m1-tool-venv.ready.json"
PROVENANCE_DIR="$TASK_ROOT/source-provenance"
PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"
PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"
FILELIST_DIR="$ROOT/runs/tmp/m1-tool-filelists"
BLACK_CACHE="$PIP_TMP/black-cache-wrapper"
RUFF_CACHE="$FILELIST_DIR/ruff-cache"
PY_CACHE="$PIP_TMP/python-cache-wrapper"
BLACK_FILELIST="$FILELIST_DIR/m1_python_files.txt"
PYRIGHT_CONFIG="$FILELIST_DIR/pyrightconfig.wrapper.json"

export PIP_CACHE_DIR="$PIP_CACHE"
export TMPDIR="$PIP_TMP"
export BLACK_CACHE_DIR="$BLACK_CACHE"
export RUFF_CACHE_DIR="$RUFF_CACHE"
export PYTHONPYCACHEPREFIX="$PY_CACHE"
export PYTEST_ADDOPTS="-p no:cacheprovider"

mkdir -p "$PIP_CACHE" "$PIP_TMP" "$FILELIST_DIR" "$BLACK_CACHE" "$RUFF_CACHE" "$PY_CACHE" "$PROVENANCE_DIR"

if [[ ! -x "$PY" ]]; then
  echo "missing project-local python: $PY"
  exit 127
fi

if [[ ! -x "$PYRIGHT" ]]; then
  echo "missing project-local pyright: $PYRIGHT"
  exit 127
fi

if [[ ! -f "$READY_STAMP" ]]; then
  echo "missing quality readiness stamp: $READY_STAMP"
  echo "run: bash scripts/quality/bootstrap_project_local_tools.sh"
  exit 127
fi

"$PY" - "$READY_STAMP" "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

stamp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(sys.argv[2]).resolve()
if Path(stamp["target_root"]).resolve() != root:
    raise SystemExit(f"quality readiness stamp points at another checkout: {stamp['target_root']}")
PY

find autovla tests/core tests/config tests/dataloader tests/training tests/maintenance tests/slurm scripts/maintenance scripts/slurm -type f -name "*.py" -print | sort > "$BLACK_FILELIST"

cat > "$PYRIGHT_CONFIG" <<JSON
{
  "include": [
    "../../../autovla",
    "../../../autovla/core",
    "../../../autovla/config",
    "../../../tests/core",
    "../../../tests/config",
    "../../../tests/dataloader",
    "../../../tests/training",
    "../../../tests/maintenance",
    "../../../tests/slurm",
    "../../../scripts/maintenance",
    "../../../scripts/slurm"
  ],
  "extraPaths": [
    "../../.."
  ],
  "exclude": [
    "**/__pycache__",
    ".git",
    "datasets",
    "runs",
    "code-input",
    "../../../code-input",
    "playground",
    "results",
    "checkpoints",
    "starVLA",
    "examples",
    "eval"
  ],
  "typeCheckingMode": "strict",
  "pythonVersion": "3.10",
  "venvPath": "$ROOT/runs/tmp",
  "venv": "m1-tool-venv"
}
JSON

"$PY" - "$ROOT" "$PYRIGHT_CONFIG" "$PROVENANCE_DIR/pyright-root.json" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
config = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3])
payload = {
    "target_root": str(root),
    "pyright_config": str(config),
    "include": json.loads(config.read_text(encoding="utf-8"))["include"],
    "result": "PASS",
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

overall=0

run_step() {
  local name="$1"
  shift
  echo "== $name =="
  "$@"
  local rc=$?
  echo "$name exit_code=$rc"
  if [[ "$rc" -ne 0 ]]; then
    overall=1
  fi
}

run_step product_py_compile "$PY" -m py_compile \
  scripts/maintenance/delete_from_cleanup_manifest.py \
  scripts/maintenance/generate_cleanup_proposal.py \
  scripts/slurm/discover_slurm_environment.py \
  tests/dataloader/__init__.py \
  tests/maintenance/test_delete_cleanup_manifest.py \
  tests/slurm/test_discover_slurm_environment.py
run_step product_pytest "$PY" -m pytest tests/core tests/config tests/dataloader tests/training tests/maintenance tests/slurm -v

echo "== product_black_filelist_each =="
black_rc=0
while IFS= read -r path; do
  "$PY" -m black --check --line-length 100 --workers 1 "$path"
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    black_rc=$rc
    break
  fi
done < "$BLACK_FILELIST"
echo "product_black_filelist_each exit_code=$black_rc"
if [[ "$black_rc" -ne 0 ]]; then
  overall=1
fi

run_step product_ruff "$PY" -m ruff check --config "line-length=100" autovla tests/core tests/config tests/dataloader tests/training tests/maintenance tests/slurm scripts/maintenance scripts/slurm
run_step product_pyright "$PYRIGHT" -p "$PYRIGHT_CONFIG"
run_step governance_py_compile "$PY" -m py_compile tests/meta/test_repo_policy.py
run_step governance_pytest "$PY" -m pytest tests/meta/test_repo_policy.py -v
run_step governance_black "$PY" -m black --check --line-length 100 --workers 1 tests/meta
run_step governance_ruff "$PY" -m ruff check --config "line-length=100" tests/meta

exit "$overall"
