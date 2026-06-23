#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TASK_ID="GVLA-M2-TOOLENV-RECOVERY-001"
TASK_ROOT="$ROOT/runs/tmp/$TASK_ID"
VENV="$ROOT/runs/tmp/m1-tool-venv"
PY="$VENV/bin/python"
PIP_CACHE="$ROOT/runs/tmp/m1-tool-pip-cache"
PIP_TMP="$ROOT/runs/tmp/m1-tool-pip-tmp"
REQ="$ROOT/requirements/quality/quality-requirements.txt"
CONSTRAINTS="$ROOT/requirements/quality/quality-constraints.txt"
LOCK_DIR="$TASK_ROOT/locks"
STAMP_DIR="$TASK_ROOT/stamps"
LOG_DIR="$TASK_ROOT/logs"
WHEELHOUSE_ROOT="$TASK_ROOT/wheelhouse"
QUARANTINE_DIR="$TASK_ROOT/quarantine"
FILL_WHEELHOUSE=0

if [[ "${1:-}" == "--fill-wheelhouse" ]]; then
  FILL_WHEELHOUSE=1
  shift
fi

if [[ "$#" -ne 0 ]]; then
  echo "usage: $0 [--fill-wheelhouse]"
  exit 64
fi

export PIP_CACHE_DIR="$PIP_CACHE"
export TMPDIR="$PIP_TMP"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

mkdir -p \
  "$PIP_CACHE" \
  "$PIP_TMP" \
  "$LOCK_DIR" \
  "$STAMP_DIR" \
  "$LOG_DIR" \
  "$WHEELHOUSE_ROOT" \
  "$QUARANTINE_DIR"

exec 9>"$LOCK_DIR/bootstrap.lock"
if ! flock -n 9; then
  echo "bootstrap already running: $LOCK_DIR/bootstrap.lock"
  exit 75
fi

choose_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
  elif command -v python3.10 >/dev/null 2>&1; then
    command -v python3.10
  else
    command -v python
  fi
}

PYTHON_BIN="$(choose_python)"
PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import sys

print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
PY
)"
PYTHON_MINOR="$("$PYTHON_BIN" - <<'PY'
import sys

print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

if [[ "$PYTHON_MINOR" != "3.10" ]]; then
  echo "unsupported bootstrap python: $PYTHON_BIN ($PYTHON_VERSION); expected Python 3.10"
  exit 78
fi

FINGERPRINT_JSON="$WHEELHOUSE_ROOT/platform-fingerprint.json"
FINGERPRINT_ID="$(
  "$PYTHON_BIN" - "$ROOT" "$REQ" "$CONSTRAINTS" "$FINGERPRINT_JSON" <<'PY'
import hashlib
import json
import platform
import sys
import sysconfig
from pathlib import Path

root = Path(sys.argv[1])
requirements = Path(sys.argv[2])
constraints = Path(sys.argv[3])
fingerprint_json = Path(sys.argv[4])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


fingerprint = {
    "schema_version": 1,
    "task_id": "GVLA-M2-TOOLENV-RECOVERY-001",
    "target_root": str(root.resolve()),
    "python_executable": str(Path(sys.executable).resolve()),
    "python_version": platform.python_version(),
    "python_implementation": platform.python_implementation(),
    "sysconfig_platform": sysconfig.get_platform(),
    "machine": platform.machine(),
    "libc": "-".join(part for part in platform.libc_ver() if part) or "unknown",
    "quality_requirements_sha256": sha256(requirements),
    "quality_constraints_sha256": sha256(constraints),
    "pyproject_sha256": sha256(root / "pyproject.toml"),
}
fingerprint_id = hashlib.sha256(
    json.dumps(fingerprint, sort_keys=True).encode("utf-8")
).hexdigest()[:24]
fingerprint["fingerprint_id"] = fingerprint_id
fingerprint_json.write_text(json.dumps(fingerprint, indent=2, sort_keys=True) + "\n")
print(fingerprint_id)
PY
)"

WHEELHOUSE="$WHEELHOUSE_ROOT/$FINGERPRINT_ID"
WHEELS="$WHEELHOUSE/wheels"
MANIFEST="$WHEELHOUSE/manifest.json"
READY_STAMP="$STAMP_DIR/m1-tool-venv.ready.json"
VENV_READY="$VENV/.genesis-quality-ready.json"
mkdir -p "$WHEELS"
printf "%s\n" "$FINGERPRINT_ID" > "$WHEELHOUSE_ROOT/current-fingerprint.txt"

missing_wheels() {
  "$PYTHON_BIN" - "$CONSTRAINTS" "$WHEELS" <<'PY'
import re
import sys
from pathlib import Path

constraints = Path(sys.argv[1])
wheels = Path(sys.argv[2])


def normalize(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


expected: list[tuple[str, str]] = []
for line in constraints.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    if "==" not in stripped:
        continue
    name, version = stripped.split("==", 1)
    expected.append((normalize(name), version.split()[0]))

available: set[tuple[str, str]] = set()
for path in wheels.glob("*.whl"):
    parts = path.name.split("-")
    if len(parts) >= 2:
        available.add((normalize(parts[0]), parts[1]))

missing = [f"{name}=={version}" for name, version in expected if (name, version) not in available]
for item in missing:
    print(item)
raise SystemExit(1 if missing else 0)
PY
}

write_manifest() {
  "$PYTHON_BIN" - "$ROOT" "$FINGERPRINT_JSON" "$REQ" "$CONSTRAINTS" "$WHEELS" "$MANIFEST" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
fingerprint_json = Path(sys.argv[2])
requirements = Path(sys.argv[3])
constraints = Path(sys.argv[4])
wheels = Path(sys.argv[5])
manifest_path = Path(sys.argv[6])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


fingerprint = json.loads(fingerprint_json.read_text(encoding="utf-8"))
manifest = {
    "schema_version": 1,
    "task_id": "GVLA-M2-TOOLENV-RECOVERY-001",
    "target_root": str(root.resolve()),
    "platform_fingerprint_sha256": sha256(fingerprint_json),
    "fingerprint": fingerprint,
    "requirements": {
        "quality_requirements": {
            "path": str(requirements.relative_to(root)),
            "sha256": sha256(requirements),
        },
        "quality_constraints": {
            "path": str(constraints.relative_to(root)),
            "sha256": sha256(constraints),
        },
    },
    "policy": {
        "wheels_only": True,
        "sdists_allowed": False,
        "editable_allowed": False,
        "external_paths_allowed": False,
    },
    "wheels": [],
}
for path in sorted(wheels.glob("*.whl")):
    parts = path.name.split("-")
    manifest["wheels"].append(
        {
            "filename": path.name,
            "project": parts[0] if parts else path.stem,
            "version": parts[1] if len(parts) > 1 else "unknown",
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
            "source": "project-local-cache-or-bounded-online-fill",
        }
    )
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
}

verify_manifest() {
  "$PYTHON_BIN" - "$MANIFEST" "$WHEELS" "$ROOT" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
wheels = Path(sys.argv[2])
root = Path(sys.argv[3]).resolve()
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

if Path(manifest["target_root"]).resolve() != root:
    raise SystemExit("manifest target_root does not match current checkout")
if not manifest["policy"]["wheels_only"]:
    raise SystemExit("manifest does not enforce wheels_only")

expected = {entry["filename"]: entry for entry in manifest["wheels"]}
actual = {path.name: path for path in wheels.glob("*.whl")}
extra = sorted(set(actual) - set(expected))
missing = sorted(set(expected) - set(actual))
if extra or missing:
    raise SystemExit(f"wheel manifest mismatch: missing={missing} extra={extra}")

for filename, entry in expected.items():
    path = actual[filename]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry["sha256"]:
        raise SystemExit(f"sha256 mismatch for {filename}")
    if path.stat().st_size != entry["size_bytes"]:
        raise SystemExit(f"size mismatch for {filename}")

print(f"PASS wheelhouse_manifest: {manifest_path}")
PY
}

if ! missing_wheels > "$LOG_DIR/missing-wheels-before-fill.txt"; then
  echo "missing wheelhouse distributions:"
  cat "$LOG_DIR/missing-wheels-before-fill.txt"
  if [[ "$FILL_WHEELHOUSE" -ne 1 ]]; then
    echo "run: bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse"
    exit 66
  fi
fi

if [[ "$FILL_WHEELHOUSE" -eq 1 ]]; then
  echo "== bounded_online_wheelhouse_fill =="
  (
    export PIP_DEFAULT_TIMEOUT=60
    export PIP_RETRIES=2
    "$PYTHON_BIN" -m pip download \
      --dest "$WHEELS" \
      --only-binary=:all: \
      --find-links "$WHEELS" \
      --disable-pip-version-check \
      --no-input \
      --retries 2 \
      --timeout 60 \
      -r "$REQ" \
      -c "$CONSTRAINTS"
  ) > "$LOG_DIR/online-fill.log" 2>&1 || {
    cat "$LOG_DIR/online-fill.log"
    exit 67
  }
fi

if ! missing_wheels > "$LOG_DIR/missing-wheels-after-fill.txt"; then
  echo "wheelhouse is still incomplete:"
  cat "$LOG_DIR/missing-wheels-after-fill.txt"
  exit 68
fi

write_manifest
verify_manifest

stamp_matches() {
  [[ -f "$READY_STAMP" && -x "$PY" ]] || return 1
  "$PY" - "$READY_STAMP" "$ROOT" "$MANIFEST" "$FINGERPRINT_ID" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

stamp = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
root = Path(sys.argv[2]).resolve()
manifest = Path(sys.argv[3])
fingerprint_id = sys.argv[4]
manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
if Path(stamp["target_root"]).resolve() != root:
    raise SystemExit(1)
if stamp["wheelhouse_manifest_sha256"] != manifest_sha:
    raise SystemExit(1)
if stamp["fingerprint_id"] != fingerprint_id:
    raise SystemExit(1)
PY
}

health_check() {
  "$PY" -m pip check
  "$PY" -m build --version
  "$VENV/bin/pyright" --version
  "$PY" -m black --version
  "$PY" -m ruff --version
  "$PY" -m pytest --version
  "$PY" - "$CONSTRAINTS" "$ROOT" <<'PY'
import importlib.metadata
import site
import sys
from pathlib import Path

constraints = Path(sys.argv[1])
root = Path(sys.argv[2]).resolve()
required = {
    line.split("==", 1)[0].lower().replace("_", "-"): line.split("==", 1)[1].strip()
    for line in constraints.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#") and "==" in line
}
for name, expected in required.items():
    actual = importlib.metadata.version(name)
    if actual != expected:
        raise SystemExit(f"{name} expected {expected}, got {actual}")

for site_package in site.getsitepackages():
    for pth in Path(site_package).glob("*.pth"):
        text = pth.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("/") and not Path(line).resolve().is_relative_to(root):
                raise SystemExit(f"foreign pth path in {pth}: {line}")

print("PASS quality_tool_health")
PY
}

if stamp_matches && health_check; then
  echo "PASS bootstrap_project_local_tools: ready stamp is current"
  exit 0
fi

if [[ -e "$VENV" ]]; then
  VENV_REAL="$(readlink -f "$VENV")"
  case "$VENV_REAL" in
    "$ROOT"/runs/tmp/*) ;;
    *)
      echo "refusing to quarantine venv outside project-local runs/tmp: $VENV_REAL"
      exit 70
      ;;
  esac
  QUARANTINED="$QUARANTINE_DIR/m1-tool-venv.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$VENV" "$QUARANTINED"
  echo "quarantined incomplete or stale venv: $QUARANTINED"
fi

echo "== offline_bootstrap =="
"$PYTHON_BIN" -m venv "$VENV"
"$PY" -m pip install \
  --no-index \
  --find-links "$WHEELS" \
  -r "$REQ" \
  -c "$CONSTRAINTS" > "$LOG_DIR/offline-bootstrap.log" 2>&1 || {
  cat "$LOG_DIR/offline-bootstrap.log"
  exit 69
}

health_check

"$PY" - "$ROOT" "$VENV" "$REQ" "$CONSTRAINTS" "$MANIFEST" "$FINGERPRINT_ID" "$READY_STAMP" <<'PY'
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
venv = Path(sys.argv[2]).resolve()
requirements = Path(sys.argv[3])
constraints = Path(sys.argv[4])
manifest = Path(sys.argv[5])
fingerprint_id = sys.argv[6]
ready_stamp = Path(sys.argv[7])


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


direct = [
    "black",
    "ruff",
    "pyright",
    "pytest",
    "build",
    "setuptools",
    "wheel",
    "numpy",
    "omegaconf",
]
stamp = {
    "schema_version": 1,
    "task_id": "GVLA-M2-TOOLENV-RECOVERY-001",
    "target_root": str(root),
    "venv": str(venv),
    "python_executable": str(Path(sys.executable).resolve()),
    "python_version": platform.python_version(),
    "fingerprint_id": fingerprint_id,
    "quality_requirements_sha256": sha256(requirements),
    "quality_constraints_sha256": sha256(constraints),
    "wheelhouse_manifest_sha256": sha256(manifest),
    "installed_packages": {name: importlib.metadata.version(name) for name in direct},
    "pip_check": "PASS",
    "foreign_pth_scan": "PASS",
}
ready_stamp.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n")
(venv / ".genesis-quality-ready.json").write_text(
    json.dumps(stamp, indent=2, sort_keys=True) + "\n"
)
PY

echo "PASS bootstrap_project_local_tools: ready stamp written at $READY_STAMP"
