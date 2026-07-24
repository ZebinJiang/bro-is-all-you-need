"""验证 M13 N1D6 环境请求并生成确定性 contract-fixture 启动证据。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

# 允许 compute wrapper 以 ``python -S path/to/script.py`` 离线执行。
_PROJECT_IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_IMPORT_ROOT))

from autovla.assets import AssetLifecycleEvidence  # noqa: E402
from autovla.runtime_profiles import (  # noqa: E402
    CudaCompatibilityIntent,
    ResolvedRuntimeLock,
    RuntimeEnvironmentReceipt,
)

TASK_ID = "AUTOVLA-M13-ARCHITECTURE-FIRST-OFFICIAL-FAMILY-RUNTIME-REALIZATION-001"
ENVIRONMENT_SCHEMA = "autovla.m13_n1d6_environment_request.v1"
FIXTURE_SCHEMA = "autovla.m13_n1d6_contract_fixture_request.v1"
PROFILE_ID = "gr00t_n1d6_runtime"
ASSET_KEYS = ("gr00t_n1d6", "gr00t_n1d6_eagle_support")
CONTRACT_FIXTURE_CONFIG = "configs/experiments/m13_n1d6_contract_fixture.yaml"
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[a-z0-9][a-z0-9-]{5,63}")


def _load_object(path: Path, label: str) -> dict[str, object]:
    """读取严格 JSON object。"""

    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a real file")
    try:
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) for key in cast("dict[object, object]", payload)
    ):
        raise ValueError(f"{label} must be one JSON object")
    return cast("dict[str, object]", payload)


def _exact_fields(
    payload: Mapping[str, object],
    expected: set[str],
    label: str,
) -> None:
    """要求字段闭集完全一致。"""

    actual = set(payload)
    if actual != expected:
        raise ValueError(
            f"{label} fields mismatch; missing={sorted(expected - actual)}; "
            f"unknown={sorted(actual - expected)}"
        )


def _checkout_relative(root: Path, value: object, label: str) -> tuple[str, Path]:
    """解析 checkout 内无符号链接的规范相对文件。"""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    path = Path(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} must be a canonical checkout-relative path")
    absolute = root / path
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} must not traverse symbolic links")
    if not absolute.is_file():
        raise ValueError(f"{label} file is missing")
    return value, absolute.resolve(strict=True)


def _checkout_relative_directory(root: Path, value: object, label: str) -> Path:
    """解析 checkout 内无符号链接的规范相对目录并返回绝对路径。"""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a checkout-relative directory")
    path = Path(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} must be a canonical checkout-relative directory")
    absolute = root / path
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{label} must not traverse symbolic links")
    if not absolute.is_dir():
        raise ValueError(f"{label} directory is missing")
    return absolute.resolve(strict=True)


def _source_head(root: Path) -> str:
    """读取当前 checkout 的完整提交身份。"""

    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    candidate = result.stdout.strip()
    if result.returncode != 0 or _SOURCE_SHA.fullmatch(candidate) is None:
        raise ValueError("checkout source HEAD is unavailable")
    return candidate


def validate_environment_request(
    request: Mapping[str, object],
    project_root: Path,
) -> dict[str, object]:
    """验证环境动作、源码和 CUDA 意图,明确拒绝 compute 节点联网。"""

    _exact_fields(
        request,
        {
            "schema_version",
            "task_id",
            "action",
            "profile_id",
            "source_head",
            "nonce",
            "cuda_intent",
            "network_on_compute",
        },
        "environment request",
    )
    if request["schema_version"] != ENVIRONMENT_SCHEMA:
        raise ValueError("environment request schema_version mismatch")
    if request["task_id"] != TASK_ID:
        raise ValueError("environment request task_id mismatch")
    if request["action"] not in {"preflight", "materialize", "verify"}:
        raise ValueError("environment request action must be preflight, materialize, or verify")
    if request["profile_id"] != PROFILE_ID:
        raise ValueError("environment request profile_id mismatch")
    source_head = request["source_head"]
    if not isinstance(source_head, str) or _SOURCE_SHA.fullmatch(source_head) is None:
        raise ValueError("environment request source_head must be a full Git SHA")
    if source_head != _source_head(project_root):
        raise ValueError("environment request source_head differs from checkout")
    nonce = request["nonce"]
    if not isinstance(nonce, str) or _NONCE.fullmatch(nonce) is None:
        raise ValueError("environment request nonce is invalid")
    if request["network_on_compute"] is not False:
        raise ValueError("environment request must set network_on_compute=false")
    raw_cuda = request["cuda_intent"]
    if not isinstance(raw_cuda, dict) or any(
        not isinstance(key, str) for key in cast("dict[object, object]", raw_cuda)
    ):
        raise ValueError("cuda_intent must be a JSON object")
    cuda = CudaCompatibilityIntent.from_dict(cast("dict[str, object]", raw_cuda))
    if not cuda.required or "8.0" not in cuda.compute_capabilities:
        raise ValueError("N1D6 A100 environment request requires CUDA capability 8.0")
    return dict(request)


def build_contract_fixture_launch(
    request: Mapping[str, object],
    project_root: Path,
    workspace_root: Path,
) -> dict[str, object]:
    """验证 fixture-only 请求并生成不执行模型的唯一启动 argv。"""

    _exact_fields(
        request,
        {
            "schema_version",
            "task_id",
            "source_head",
            "fixture_kind",
            "fixture_root",
            "fixture_identity",
            "fixture_sample_count",
            "embodiment",
            "backend_decision",
            "max_steps",
            "runtime_lock_receipt",
            "runtime_environment_receipt",
            "asset_evidence",
        },
        "contract fixture request",
    )
    if request["schema_version"] != FIXTURE_SCHEMA or request["task_id"] != TASK_ID:
        raise ValueError("contract fixture request identity mismatch")
    if request["source_head"] != _source_head(project_root):
        raise ValueError("contract fixture source_head differs from checkout")
    if request["fixture_kind"] != "contract_fixture_only":
        raise ValueError("fixture_kind must be contract_fixture_only")
    if request["backend_decision"] != "NO_BACKEND_WINNER":
        raise ValueError("backend_decision must remain NO_BACKEND_WINNER")
    if request["max_steps"] != 1 or type(request["max_steps"]) is not int:
        raise ValueError("contract fixture max_steps must be exact integer 1")
    sample_count = request["fixture_sample_count"]
    if type(sample_count) is not int or sample_count <= 0:
        raise ValueError("fixture_sample_count must be a positive integer")
    fixture_identity = request["fixture_identity"]
    if not isinstance(fixture_identity, str) or _SHA256.fullmatch(fixture_identity) is None:
        raise ValueError("fixture_identity must be a full SHA256")
    fixture = _checkout_relative_directory(project_root, request["fixture_root"], "fixture_root")
    task_root = (project_root / "runs" / "tmp" / TASK_ID).resolve(strict=True)
    try:
        fixture.relative_to(task_root)
    except ValueError as exc:
        raise ValueError("fixture_root must exist below the task-local runs/tmp root") from exc
    _, config_path = _checkout_relative(
        project_root,
        CONTRACT_FIXTURE_CONFIG,
        "contract fixture config",
    )
    _, lock_path = _checkout_relative(
        project_root,
        request["runtime_lock_receipt"],
        "runtime_lock_receipt",
    )
    _, environment_path = _checkout_relative(
        project_root,
        request["runtime_environment_receipt"],
        "runtime_environment_receipt",
    )
    lock = ResolvedRuntimeLock.from_dict(_load_object(lock_path, "runtime lock receipt"))
    environment = RuntimeEnvironmentReceipt.from_dict(
        _load_object(environment_path, "runtime environment receipt")
    )
    environment.validate_lock(lock)
    if environment.source_sha != request["source_head"]:
        raise ValueError("runtime environment receipt source differs from fixture request")
    raw_asset_evidence = request["asset_evidence"]
    if not isinstance(raw_asset_evidence, dict) or any(
        not isinstance(key, str) for key in cast("dict[object, object]", raw_asset_evidence)
    ):
        raise ValueError("asset_evidence must contain exactly the N1D6 base and Eagle keys")
    asset_evidence = cast("dict[str, object]", raw_asset_evidence)
    if set(asset_evidence) != set(ASSET_KEYS):
        raise ValueError("asset_evidence must contain exactly the N1D6 base and Eagle keys")
    evidence_arguments: list[str] = []
    for key in ASSET_KEYS:
        _, path = _checkout_relative(
            project_root,
            asset_evidence[key],
            f"asset_evidence.{key}",
        )
        AssetLifecycleEvidence.from_dict(_load_object(path, f"asset evidence {key}"))
        evidence_arguments.extend(("--asset-evidence", f"{key}={path}"))
    python = workspace_root / environment.environment_path / "bin" / "python"
    command = [
        str(python),
        "-I",
        "-m",
        "autovla.cli.train",
        str(config_path),
        "--runtime-lock-receipt",
        str(lock_path),
        "--runtime-environment-receipt",
        str(environment_path),
        *evidence_arguments,
        "--set",
        f"training.max_steps={request['max_steps']}",
        "--set",
        f"data.datasets[0].root={fixture}",
        "--set",
        f"data.datasets[0].sample_count={sample_count}",
        "--set",
        f"data.datasets[0].embodiment={request['embodiment']}",
    ]
    return {
        "schema_version": "autovla.m13_n1d6_contract_fixture_launch.v1",
        "task_id": TASK_ID,
        "source_head": request["source_head"],
        "fixture_kind": "contract_fixture_only",
        "fixture_identity": fixture_identity,
        "backend_decision": "NO_BACKEND_WINNER",
        "real_data_claim": False,
        "backend_winner_claim": False,
        "model_execution_performed": False,
        "command": command,
    }


def _task_output_path(project_root: Path, path: str | Path) -> Path:
    """解析任务专属 runs/tmp 根内无符号链接的规范相对输出。"""

    path_text = path if isinstance(path, str) else path.as_posix()
    candidate = Path(path_text)
    task_prefix = Path("runs") / "tmp" / TASK_ID
    if (
        candidate.is_absolute()
        or candidate.as_posix() != path_text
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ValueError("output must be a canonical project-relative path")
    try:
        candidate.relative_to(task_prefix)
    except ValueError as exc:
        raise ValueError("output must remain below the task-local runs/tmp root") from exc
    current = project_root
    for part in candidate.parent.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("output must not traverse symbolic links")
        if current.exists():
            if not current.is_dir():
                raise ValueError("output parent must be a real directory")
            continue
        current.mkdir()
    output = project_root / candidate
    if output.is_symlink():
        raise ValueError("output must not be a symbolic link")
    return output


def _same_regular_content(path: Path, content: bytes) -> bool:
    """仅在既有目标为相同内容的普通文件时允许幂等成功。"""

    try:
        return path.is_file() and not path.is_symlink() and path.read_bytes() == content
    except OSError:
        return False


def _write_json(
    project_root: Path,
    path: str | Path,
    payload: Mapping[str, object],
) -> None:
    """以原子、无覆盖方式发布任务专属 JSON 输出。"""

    output = _task_output_path(project_root, path)
    content = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if output.exists():
        if _same_regular_content(output, content):
            return
        raise ValueError("output already exists with unrelated content")
    descriptor, temporary_text = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_text)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError:
            if _same_regular_content(output, content):
                return
            raise ValueError("output was concurrently published with unrelated content") from None
        parent_descriptor = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    """构造两个无模型执行的验证子命令。"""

    parser = argparse.ArgumentParser(prog="m13-n1d6-harness")
    subparsers = parser.add_subparsers(dest="action", required=True)
    environment = subparsers.add_parser("validate-environment-request")
    environment.add_argument("--request", type=Path, required=True)
    environment.add_argument("--project-root", type=Path, required=True)
    environment.add_argument("--output", required=True)
    fixture = subparsers.add_parser("build-contract-launch")
    fixture.add_argument("--request", type=Path, required=True)
    fixture.add_argument("--project-root", type=Path, required=True)
    fixture.add_argument("--workspace-root", type=Path, required=True)
    fixture.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行验证或仅生成启动 argv。"""

    arguments = build_parser().parse_args(argv)
    project_root = arguments.project_root.resolve(strict=True)
    request = _load_object(arguments.request, "runtime request")
    if arguments.action == "validate-environment-request":
        payload = validate_environment_request(request, project_root)
    else:
        workspace_root = arguments.workspace_root.resolve(strict=True)
        payload = build_contract_fixture_launch(
            request,
            project_root,
            workspace_root,
        )
    _write_json(project_root, arguments.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
