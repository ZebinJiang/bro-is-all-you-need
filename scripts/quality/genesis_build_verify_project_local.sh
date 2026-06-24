#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TASK_ID="GVLA-M2-TOOLENV-RECOVERY-001"
TOOL_PY="$ROOT/runs/tmp/m1-tool-venv/bin/python"
WORK_ROOT="$ROOT/runs/tmp/$TASK_ID"
DIST_DIR="$WORK_ROOT/dist"
WHEEL_VENV="$WORK_ROOT/clean-install-venv"
WHEEL_PY="$WHEEL_VENV/bin/python"
PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"
PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"
PY_CACHE="$WORK_ROOT/python-cache"
PROVENANCE_DIR="$WORK_ROOT/source-provenance"
QUARANTINE_DIR="$WORK_ROOT/quarantine"
FINGERPRINT_ID="$(cat "$WORK_ROOT/wheelhouse/current-fingerprint.txt")"
WHEELHOUSE="$WORK_ROOT/wheelhouse/$FINGERPRINT_ID/wheels"
READY_STAMP="$WORK_ROOT/stamps/m1-tool-venv.ready.json"

export PIP_CACHE_DIR="$PIP_CACHE"
export TMPDIR="$PIP_TMP"
export PYTHONPYCACHEPREFIX="$PY_CACHE"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

mkdir -p "$DIST_DIR" "$PIP_CACHE" "$PIP_TMP" "$PY_CACHE" "$PROVENANCE_DIR" "$QUARANTINE_DIR"

quarantine_root_build_artifacts() {
  local phase="$1"
  local artifact
  local target_dir="$QUARANTINE_DIR/root-build-artifacts.$phase.$(date -u +%Y%m%dT%H%M%SZ)"
  for artifact in build UNKNOWN.egg-info starVLA.egg-info; do
    if [[ -e "$ROOT/$artifact" ]]; then
      mkdir -p "$target_dir"
      mv "$ROOT/$artifact" "$target_dir/"
      echo "quarantined root build artifact: $artifact -> $target_dir/"
    fi
  done
}

if [[ ! -x "$TOOL_PY" ]]; then
  echo "missing required project-local python: $TOOL_PY"
  echo "run make genesis-check-bootstrap before genesis-build-check"
  exit 127
fi

if [[ ! -f "$READY_STAMP" ]]; then
  echo "missing quality readiness stamp: $READY_STAMP"
  echo "run make genesis-check-bootstrap before genesis-build-check"
  exit 127
fi

echo "== genesis_build =="
quarantine_root_build_artifacts "before"
"$TOOL_PY" -m build --no-isolation --wheel --outdir "$DIST_DIR"
quarantine_root_build_artifacts "after"

WHEEL_PATH="$(
  "$TOOL_PY" - "$DIST_DIR" <<'PY'
from pathlib import Path
import sys

dist_dir = Path(sys.argv[1])
wheels = sorted(
    dist_dir.glob("*.whl"),
    key=lambda path: (path.stat().st_mtime_ns, path.name),
    reverse=True,
)
if not wheels:
    raise SystemExit(f"no wheel found in {dist_dir}")
print(wheels[0])
PY
)"

echo "PASS build: wheel=$WHEEL_PATH"

if [[ -e "$WHEEL_VENV" ]]; then
  QUARANTINED="$WORK_ROOT/quarantine/clean-install-venv.$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$(dirname "$QUARANTINED")"
  mv "$WHEEL_VENV" "$QUARANTINED"
  echo "quarantined old clean install venv: $QUARANTINED"
fi

echo "== wheel_venv =="
"$TOOL_PY" -m venv "$WHEEL_VENV"
echo "PASS wheel_venv: path=$WHEEL_VENV"

echo "== wheel_install =="
"$WHEEL_PY" -m pip install \
  --no-index \
  --find-links "$WHEELHOUSE" \
  "$WHEEL_PATH"
echo "PASS wheel_install"

echo "== pip_check =="
"$WHEEL_PY" -m pip check
echo "PASS pip_check"

echo "== import_genesisvla =="
"$WHEEL_PY" - "$ROOT" "$WHEEL_VENV" "$PROVENANCE_DIR/runtime-import.json" <<'PY'
import json
import os
import site
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
venv = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3])
cwd = Path(os.getcwd()).resolve()
clean_path = []
for entry in sys.path:
    resolved = cwd if entry == "" else Path(entry).resolve()
    if resolved.is_relative_to(venv):
        clean_path.append(entry)
        continue
    if resolved == root or resolved.is_relative_to(root):
        continue
    clean_path.append(entry)
sys.path = clean_path

import genesisvla
import numpy
import omegaconf

genesis_path = Path(genesisvla.__file__).resolve()
site_packages = [Path(path).resolve() for path in site.getsitepackages()]
if not any(genesis_path.is_relative_to(path) for path in site_packages):
    raise SystemExit(f"genesisvla import is not from clean venv site-packages: {genesis_path}")

typed_marker = genesis_path.parent / "py.typed"
if not typed_marker.exists():
    raise SystemExit(f"missing installed py.typed marker: {typed_marker}")

payload = {
    "venv": str(venv),
    "genesisvla_file": str(genesis_path),
    "numpy_file": str(Path(numpy.__file__).resolve()),
    "omegaconf_file": str(Path(omegaconf.__file__).resolve()),
    "py_typed": str(typed_marker),
    "result": "PASS",
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"PASS import_genesisvla: {genesis_path}")
PY

echo "== wheel_content_scan =="
"$TOOL_PY" - "$ROOT" "$WHEEL_PATH" "$PROVENANCE_DIR/build-source.json" <<'PY'
from pathlib import Path
import json
import sys
import zipfile

root = Path(sys.argv[1]).resolve()
wheel_path = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3])
forbidden_parts = {
    "__pycache__",
    "checkpoints",
    "code-input",
    "playground",
    "results",
}
forbidden_top_level = {"cache", "datasets", "runs"}
forbidden_suffixes = (
    ".arrow",
    ".bin",
    ".ckpt",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pth",
    ".pt",
    ".pyc",
    ".safetensors",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".zip",
    ".zst",
)

bad_entries: list[tuple[str, str]] = []
with zipfile.ZipFile(wheel_path) as wheel:
    names = wheel.namelist()
    for name in names:
        normalized = name.replace("\\", "/")
        lowered = normalized.lower()
        parts = [part.lower() for part in normalized.split("/") if part and part != "."]
        if any(part in forbidden_parts for part in parts):
            bad_entries.append((name, "forbidden path component"))
        if parts and parts[0] in forbidden_top_level:
            bad_entries.append((name, "forbidden top-level artifact path"))
        if lowered.endswith(forbidden_suffixes):
            bad_entries.append((name, "forbidden artifact suffix"))

if bad_entries:
    print("FAIL wheel_content_scan", file=sys.stderr)
    for name, reason in bad_entries[:50]:
        print(f"{reason}: {name}", file=sys.stderr)
    if len(bad_entries) > 50:
        print(f"... {len(bad_entries) - 50} more forbidden entries", file=sys.stderr)
    raise SystemExit(1)

payload = {
    "source_root": str(root),
    "wheel": str(wheel_path),
    "wheel_entries": len(names),
    "forbidden_scan": "PASS",
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"PASS wheel_content_scan: wheel={wheel_path.name} entries={len(names)}")
PY

echo "PASS genesis_build_verify_project_local"
