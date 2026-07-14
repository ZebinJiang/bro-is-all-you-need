#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/quality/autovla_build_verify_project_local.sh \
    --build-python /absolute/build-env/bin/python \
    --quality-python /absolute/quality-env/bin/python \
    --work-root /absolute/repository/runs/tmp/<task>/build-gate \
    --clean-install-venv /absolute/repository/runs/tmp/<task>/build-gate/clean-install \
    --wheelhouse /absolute/offline-wheelhouse

Scanner test mode (does not build or inspect build-package versions):
  scripts/quality/autovla_build_verify_project_local.sh \
    --build-python /absolute/python \
    --scan-only --wheel /absolute/file.whl --sdist /absolute/file.tar.gz \
    --scan-output /absolute/result.json
USAGE
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

scan_archives() {
  local python_path="$1"
  local wheel_path="$2"
  local sdist_path="$3"
  local output_path="$4"
  "$python_path" - "$ROOT" "$wheel_path" "$sdist_path" "$output_path" <<'PY'
from pathlib import Path
import json
import sys
import tarfile
import zipfile

root = Path(sys.argv[1]).resolve()
wheel_path = Path(sys.argv[2]).resolve(strict=True)
sdist_path = Path(sys.argv[3]).resolve(strict=True)
output = Path(sys.argv[4]).resolve()

forbidden_components = {
    ".git",
    "__pycache__",
    "cache",
    "checkpoints",
    "code-input",
    "datasets",
    "envs",
    "playground",
    "related-assets",
    "results",
    "runs",
    "source-checkout",
    "source-checkouts",
    "tests",
    "upstream",
    "upstream-clone",
    "upstream-clones",
    "upstreams",
}
allowed_dataset_namespaces = {
    ("autovla", "data", "datasets"),
    ("autovla", "dataloader", "datasets"),
}
forbidden_suffixes = (
    ".arrow",
    ".avi",
    ".bin",
    ".ckpt",
    ".dll",
    ".dylib",
    ".exe",
    ".h5",
    ".hdf5",
    ".jpeg",
    ".jpg",
    ".jsonl",
    ".mp4",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pickle",
    ".pkl",
    ".png",
    ".pth",
    ".pt",
    ".pyc",
    ".safetensors",
    ".so",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".webm",
    ".whl",
    ".zip",
    ".zst",
)
required_members = {
    "Apache-2.0.txt",
    "LICENSE",
    "MIT.txt",
    "NVIDIA-ISAAC-GROOT-N1D6.txt",
    "THIRD_PARTY_NOTICES.md",
}
required_resources = {
    "autovla/resources/configs/experiments/local_debug.yaml",
    "autovla/resources/configs/models/gr00t_n1d6.yaml",
}


def normalize(name: str, *, strip_sdist_root: bool) -> tuple[str | None, str | None]:
    """规范 archive 路径并为 sdist 去掉唯一分发根。"""
    value = name.replace("\\", "/")
    if not value or value.startswith("/") or "\x00" in value:
        return None, "absolute, empty, or NUL archive path"
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        return None, "archive path traversal"
    if strip_sdist_root:
        if len(parts) <= 1:
            return None, None
        parts = parts[1:]
    if not parts:
        return None, None
    return "/".join(parts), None


def scan(
    names: list[str],
    archive_name: str,
    *,
    strip_sdist_root: bool,
) -> tuple[list[tuple[str, str]], list[str]]:
    """扫描规范路径、禁用组件、工件后缀和必需成员。"""
    bad: list[tuple[str, str]] = []
    normalized_names: list[str] = []
    for original in names:
        normalized, error = normalize(original, strip_sdist_root=strip_sdist_root)
        if error is not None:
            bad.append((original, error))
            continue
        if normalized is None:
            continue
        normalized_names.append(normalized)
        lowered = normalized.lower()
        parts = [part.lower() for part in lowered.split("/")]
        for index, part in enumerate(parts):
            allowed_dataset_namespace = (
                part == "datasets"
                and tuple(parts[: index + 1]) in allowed_dataset_namespaces
            )
            if (
                part in forbidden_components
                and not allowed_dataset_namespace
                or part.startswith("starvla")
            ):
                bad.append((original, f"forbidden archive component: {part}"))
                break
        if lowered.endswith(forbidden_suffixes):
            bad.append((original, "forbidden binary/model/data artifact suffix"))
    for member in sorted(required_members):
        if not any(name == member or name.endswith(f"/{member}") for name in normalized_names):
            bad.append((member, f"missing mixed-license member in {archive_name}"))
    for resource in sorted(required_resources):
        if resource not in normalized_names:
            bad.append((resource, f"missing packaged resource in {archive_name}"))
    return bad, normalized_names


with zipfile.ZipFile(wheel_path) as wheel:
    wheel_names = wheel.namelist()
with tarfile.open(sdist_path, "r:gz") as sdist:
    members = sdist.getmembers()
    sdist_names = [member.name for member in members]
    unsafe_links = [member.name for member in members if member.issym() or member.islnk()]

sdist_roots = {
    name.replace("\\", "/").split("/", 1)[0]
    for name in sdist_names
    if name and not name.startswith("/")
}
bad_entries: list[tuple[str, str]] = []
if len(sdist_roots) != 1:
    bad_entries.append((str(sorted(sdist_roots)), "sdist must contain one distribution root"))
else:
    sdist_root = next(iter(sdist_roots))
    if not sdist_root.lower().startswith("autovla-"):
        bad_entries.append((sdist_root, "sdist distribution root must be autovla-<version>"))
bad_entries.extend((name, "sdist links are prohibited") for name in unsafe_links)
wheel_bad, wheel_normalized = scan(
    wheel_names,
    wheel_path.name,
    strip_sdist_root=False,
)
sdist_bad, sdist_normalized = scan(
    sdist_names,
    sdist_path.name,
    strip_sdist_root=True,
)
bad_entries.extend(wheel_bad)
bad_entries.extend(sdist_bad)

if bad_entries:
    print("FAIL archive_content_scan", file=sys.stderr)
    for name, reason in bad_entries[:80]:
        print(f"{reason}: {name}", file=sys.stderr)
    if len(bad_entries) > 80:
        print(f"... {len(bad_entries) - 80} more forbidden entries", file=sys.stderr)
    raise SystemExit(1)

payload = {
    "archives": {
        "sdist": str(sdist_path),
        "sdist_entries": len(sdist_names),
        "wheel": str(wheel_path),
        "wheel_entries": len(wheel_names),
    },
    "forbidden_scan": "PASS",
    "mixed_license_members": sorted(required_members),
    "normalized_sdist_members": len(sdist_normalized),
    "normalized_wheel_members": len(wheel_normalized),
    "packaged_resources": sorted(required_resources),
    "source_root": str(root),
}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    "PASS archive_content_scan: "
    f"wheel={wheel_path.name} entries={len(wheel_names)} "
    f"sdist={sdist_path.name} entries={len(sdist_names)}"
)
PY
}

BUILD_PY=""
QUALITY_PY=""
WORK_ROOT=""
WHEEL_VENV=""
WHEELHOUSE=""
SCAN_ONLY=0
SCAN_WHEEL=""
SCAN_SDIST=""
SCAN_OUTPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-python) BUILD_PY="${2:-}"; shift 2 ;;
    --quality-python) QUALITY_PY="${2:-}"; shift 2 ;;
    --work-root) WORK_ROOT="${2:-}"; shift 2 ;;
    --clean-install-venv) WHEEL_VENV="${2:-}"; shift 2 ;;
    --wheelhouse) WHEELHOUSE="${2:-}"; shift 2 ;;
    --scan-only) SCAN_ONLY=1; shift ;;
    --wheel) SCAN_WHEEL="${2:-}"; shift 2 ;;
    --sdist) SCAN_SDIST="${2:-}"; shift 2 ;;
    --scan-output) SCAN_OUTPUT="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -n "$BUILD_PY" ]] || { echo "--build-python is required" >&2; usage; exit 2; }
[[ "$BUILD_PY" = /* && -x "$BUILD_PY" ]] || {
  echo "--build-python must be an absolute executable path: $BUILD_PY" >&2
  exit 2
}

if [[ "$SCAN_ONLY" -eq 1 ]]; then
  [[ "$SCAN_WHEEL" = /* && "$SCAN_SDIST" = /* && "$SCAN_OUTPUT" = /* ]] || {
    echo "scan-only paths must be absolute" >&2
    exit 2
  }
  scan_archives "$BUILD_PY" "$SCAN_WHEEL" "$SCAN_SDIST" "$SCAN_OUTPUT"
  exit 0
fi
[[ -z "$SCAN_WHEEL" && -z "$SCAN_SDIST" && -z "$SCAN_OUTPUT" ]] || {
  echo "--wheel, --sdist, and --scan-output require --scan-only" >&2
  exit 2
}

[[ -n "$QUALITY_PY" ]] || { echo "--quality-python is required" >&2; exit 2; }
[[ "$QUALITY_PY" = /* && -x "$QUALITY_PY" ]] || {
  echo "--quality-python must be an absolute executable path: $QUALITY_PY" >&2
  exit 2
}
[[ "$WORK_ROOT" = /* ]] || { echo "--work-root must be an absolute path" >&2; exit 2; }
[[ "$WHEEL_VENV" = /* ]] || {
  echo "--clean-install-venv must be an absolute path" >&2
  exit 2
}
[[ "$WHEELHOUSE" = /* && -d "$WHEELHOUSE" ]] || {
  echo "--wheelhouse must be an existing absolute directory: $WHEELHOUSE" >&2
  exit 2
}
case "$WORK_ROOT" in
  "$ROOT"/runs/*) ;;
  *) echo "--work-root must be under $ROOT/runs" >&2; exit 2 ;;
esac
case "$WHEEL_VENV" in
  "$WORK_ROOT"/*) ;;
  *) echo "--clean-install-venv must be under --work-root" >&2; exit 2 ;;
esac

cd "$ROOT"
DIST_DIR="$WORK_ROOT/dist"
WHEEL_PY="$WHEEL_VENV/bin/python"
PIP_CACHE="$WORK_ROOT/pip-cache"
PIP_TMP="$WORK_ROOT/pip-tmp"
PY_CACHE="$WORK_ROOT/python-cache"
PROVENANCE_DIR="$WORK_ROOT/source-provenance"
QUARANTINE_DIR="$WORK_ROOT/quarantine"

export PIP_CACHE_DIR="$PIP_CACHE"
export TMPDIR="$PIP_TMP"
export PYTHONPYCACHEPREFIX="$PY_CACHE"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1

mkdir -p "$DIST_DIR" "$PIP_CACHE" "$PIP_TMP" "$PY_CACHE" "$PROVENANCE_DIR" "$QUARANTINE_DIR"

echo "== build_environment =="
"$BUILD_PY" - "$PROVENANCE_DIR/build-environment.json" <<'PY'
from importlib import metadata
from pathlib import Path
import json
import re
import sys


def release(value: str) -> tuple[int, ...]:
    """提取版本的数字 release 段。"""
    match = re.match(r"^(\d+(?:\.\d+)*)", value)
    if match is None:
        raise SystemExit(f"cannot parse package version: {value}")
    return tuple(int(part) for part in match.group(1).split("."))


setuptools_version = metadata.version("setuptools")
build_version = metadata.version("build")
if setuptools_version != "77.0.3":
    raise SystemExit(
        f"build environment requires setuptools==77.0.3; observed {setuptools_version}"
    )
if not (release("1.2.2") <= release(build_version) < release("2")):
    raise SystemExit(f"build environment requires build>=1.2.2,<2; observed {build_version}")
import build  # noqa: F401

payload = {
    "build": build_version,
    "python": sys.executable,
    "setuptools": setuptools_version,
}
Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"PASS build_environment: setuptools={setuptools_version} build={build_version}")
PY

quarantine_root_build_artifacts() {
  local phase="$1"
  local artifact
  local target_dir="$QUARANTINE_DIR/root-build-artifacts.$phase.$(date -u +%Y%m%dT%H%M%SZ)"
  for artifact in build autovla.egg-info UNKNOWN.egg-info starVLA.egg-info; do
    if [[ -e "$ROOT/$artifact" ]]; then
      mkdir -p "$target_dir"
      mv "$ROOT/$artifact" "$target_dir/"
      echo "quarantined root build artifact: $artifact -> $target_dir/"
    fi
  done
}

echo "== autovla_build =="
quarantine_root_build_artifacts "before"
"$BUILD_PY" -m build --no-isolation --wheel --sdist --outdir "$DIST_DIR"
quarantine_root_build_artifacts "after"

WHEEL_PATH="$(
  "$BUILD_PY" - "$DIST_DIR" <<'PY'
from pathlib import Path
import sys

paths = sorted(
    Path(sys.argv[1]).glob("*.whl"),
    key=lambda path: (path.stat().st_mtime_ns, path.name),
    reverse=True,
)
if not paths:
    raise SystemExit("no wheel found")
print(paths[0])
PY
)"
SDIST_PATH="$(
  "$BUILD_PY" - "$DIST_DIR" <<'PY'
from pathlib import Path
import sys

paths = sorted(
    Path(sys.argv[1]).glob("*.tar.gz"),
    key=lambda path: (path.stat().st_mtime_ns, path.name),
    reverse=True,
)
if not paths:
    raise SystemExit("no sdist found")
print(paths[0])
PY
)"
echo "PASS build: wheel=$WHEEL_PATH"
echo "PASS build: sdist=$SDIST_PATH"

if [[ -e "$WHEEL_VENV" ]]; then
  QUARANTINED="$QUARANTINE_DIR/clean-install-venv.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$WHEEL_VENV" "$QUARANTINED"
fi
"$QUALITY_PY" -m venv "$WHEEL_VENV"
"$WHEEL_PY" -m pip install --no-index --find-links "$WHEELHOUSE" "$WHEEL_PATH"
"$WHEEL_PY" -m pip check

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
sys.path = [
    entry
    for entry in sys.path
    if (cwd if entry == "" else Path(entry).resolve()) != root
    and not (cwd if entry == "" else Path(entry).resolve()).is_relative_to(root)
    or (cwd if entry == "" else Path(entry).resolve()).is_relative_to(venv)
]

import autovla
from autovla.config.resources import config_resource
from autovla.models.registry import get_model_family_registration

if not config_resource("experiments", "local_debug").is_file():
    raise SystemExit("installed packaged config is missing")
if get_model_family_registration("gr00t_n1d6").spec.family_key != "gr00t_n1d6":
    raise SystemExit("installed GR00T registry inspection failed")
if "torch" in sys.modules:
    raise SystemExit("lightweight installed imports unexpectedly loaded torch")

import numpy
import omegaconf

package_path = Path(autovla.__file__).resolve()
site_packages = [Path(path).resolve() for path in site.getsitepackages()]
if not any(package_path.is_relative_to(path) for path in site_packages):
    raise SystemExit(f"autovla import is not from clean venv: {package_path}")
if not (package_path.parent / "py.typed").is_file():
    raise SystemExit("installed py.typed is missing")
if not isinstance(autovla.__version__, str) or not autovla.__version__:
    raise SystemExit("installed version must be non-empty")
payload = {
    "autovla_file": str(package_path),
    "autovla_version": autovla.__version__,
    "numpy_file": str(Path(numpy.__file__).resolve()),
    "omegaconf_file": str(Path(omegaconf.__file__).resolve()),
    "result": "PASS",
    "torch_lazy": True,
    "venv": str(venv),
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

(
  cd "$WORK_ROOT"
  "$WHEEL_VENV/bin/autovla-train" --help > "$PROVENANCE_DIR/autovla-train-help.txt"
  "$WHEEL_VENV/bin/autovla-inspect-config" --help \
    > "$PROVENANCE_DIR/autovla-inspect-config-help.txt"
  "$WHEEL_VENV/bin/autovla-inspect-config" pkg://experiments/local_debug \
    > "$PROVENANCE_DIR/packaged-local-debug.json.txt"
)
grep -q 'usage: autovla-train' "$PROVENANCE_DIR/autovla-train-help.txt"
grep -q 'usage: autovla-inspect-config' "$PROVENANCE_DIR/autovla-inspect-config-help.txt"
grep -q '"name": "local_debug"' "$PROVENANCE_DIR/packaged-local-debug.json.txt"
grep -q '^fingerprint: ' "$PROVENANCE_DIR/packaged-local-debug.json.txt"

scan_archives "$BUILD_PY" "$WHEEL_PATH" "$SDIST_PATH" \
  "$PROVENANCE_DIR/build-source.json"
echo "PASS autovla_build_verify_project_local"
