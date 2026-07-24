"""把已提交的 uv.lock 解析为 M12 精确运行时 lock。"""

from __future__ import annotations

import ast
import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

try:
    import tomllib as _toml_parser  # pyright: ignore[reportMissingImports]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 使用项目 dev 依赖
    try:
        import tomli as _toml_parser  # pyright: ignore[reportMissingImports]
    except ModuleNotFoundError:  # pragma: no cover - resolve 会返回稳定错误
        _toml_parser: Any | None = None

from autovla.runtime_profiles.contracts import (
    CudaCompatibilityIntent,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeProfileSpec,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

_PEP440_VERSION = re.compile(
    r"""
    v?
    (?:(?P<epoch>[0-9]+)!)?
    (?P<release>[0-9]+(?:\.[0-9]+)*)
    (?:
        [-_.]?
        (?P<pre_label>a|b|c|rc|alpha|beta|pre|preview)
        [-_.]?
        (?P<pre_number>[0-9]+)?
    )?
    (?:
        -(?P<post_number_implicit>[0-9]+)
        |
        [-_.]?
        (?P<post_label>post|rev|r)
        [-_.]?
        (?P<post_number>[0-9]+)?
    )?
    (?:
        [-_.]?
        dev
        [-_.]?
        (?P<dev_number>[0-9]+)?
    )?
    (?:\+(?P<local>[a-z0-9]+(?:[-_.][a-z0-9]+)*))?
    """,
    re.IGNORECASE | re.VERBOSE,
)
_WHEEL_TAG = re.compile(r"[A-Za-z0-9_.]+")
_WHEEL_BUILD = re.compile(r"[0-9][A-Za-z0-9_.]*")
_DEPENDENCY_FIELDS = frozenset({"extra", "marker", "name", "source", "version"})


def _numeric_version(value: str, *, marker: str) -> tuple[int, ...]:
    """把 Python marker 版本转换为可精确比较的数字元组。"""

    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_MARKER_UNSUPPORTED",
            f"unsupported dependency marker: {marker}",
        )
    return tuple(int(part) for part in value.split("."))


def _compare_marker_value(
    variable: str,
    actual: str,
    operator: str,
    expected: str,
    marker: str,
) -> bool:
    """比较 marker 原子表达式,拒绝平台字符串排序等模糊语义。"""

    if variable in {"python_version", "python_full_version", "implementation_version"}:
        if expected.endswith(".*"):
            if operator not in {"==", "!="}:
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_MARKER_UNSUPPORTED",
                    f"unsupported dependency marker: {marker}",
                )
            prefix = _numeric_version(expected[:-2], marker=marker)
            matched = _numeric_version(actual, marker=marker)[: len(prefix)] == prefix
            return matched if operator == "==" else not matched
        left = _numeric_version(actual, marker=marker)
        right = _numeric_version(expected, marker=marker)
        width = max(len(left), len(right))
        left += (0,) * (width - len(left))
        right += (0,) * (width - len(right))
        comparisons = {
            "==": left == right,
            "!=": left != right,
            "<": left < right,
            "<=": left <= right,
            ">": left > right,
            ">=": left >= right,
        }
        if operator not in comparisons:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_MARKER_UNSUPPORTED",
                f"unsupported dependency marker: {marker}",
            )
        return comparisons[operator]
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    raise RuntimeEnvironmentError(
        "RUNTIME_LOCK_MARKER_UNSUPPORTED",
        f"unsupported dependency marker: {marker}",
    )


def _evaluate_marker_node(
    node: ast.expr,
    *,
    environment: Mapping[str, str],
    marker: str,
) -> bool:
    """仅求值布尔组合和单一字符串比较,其余 AST 一律拒绝。"""

    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        values = [
            _evaluate_marker_node(value, environment=environment, marker=marker)
            for value in node.values
        ]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if (
        not isinstance(node, ast.Compare)
        or len(node.ops) != 1
        or len(node.comparators) != 1
        or not isinstance(node.left, ast.Name)
        or not isinstance(node.comparators[0], ast.Constant)
        or not isinstance(node.comparators[0].value, str)
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_MARKER_UNSUPPORTED",
            f"unsupported dependency marker: {marker}",
        )
    operators: tuple[tuple[type[ast.cmpop], str], ...] = (
        (ast.Eq, "=="),
        (ast.NotEq, "!="),
        (ast.Lt, "<"),
        (ast.LtE, "<="),
        (ast.Gt, ">"),
        (ast.GtE, ">="),
    )
    operator = next(
        (text for operator_type, text in operators if isinstance(node.ops[0], operator_type)),
        None,
    )
    actual = environment.get(node.left.id)
    if operator is None or actual is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_MARKER_UNSUPPORTED",
            f"unsupported dependency marker: {marker}",
        )
    return _compare_marker_value(
        node.left.id,
        actual,
        operator,
        node.comparators[0].value,
        marker,
    )


def _target_environment(profile: RuntimeProfileSpec) -> dict[str, str]:
    """把支持的平台画像展开为稳定 PEP 508 环境。"""

    if (
        profile.platform_intent != "linux-x86_64"
        or profile.python_implementation != "CPython"
        or not re.fullmatch(r"[0-9]+\.[0-9]+", profile.requested_python_version)
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PLATFORM_MISMATCH",
            "lock resolution supports Linux x86_64 CPython profiles only",
        )
    python_full_version = f"{profile.requested_python_version}.0"
    return {
        "implementation_name": "cpython",
        "implementation_version": python_full_version,
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_python_implementation": "CPython",
        "platform_system": "Linux",
        "python_full_version": python_full_version,
        "python_version": profile.requested_python_version,
        "sys_platform": "linux",
    }


def _marker_matches(marker: object, environment: Mapping[str, str]) -> bool:
    """严格验证并求值一个 marker。"""

    if not isinstance(marker, str) or not marker:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_MARKER_UNSUPPORTED", "dependency marker must be non-empty text"
        )
    try:
        expression = ast.parse(marker, mode="eval")
    except SyntaxError as exc:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_MARKER_UNSUPPORTED",
            f"unsupported dependency marker: {marker}",
        ) from exc
    return _evaluate_marker_node(expression.body, environment=environment, marker=marker)


def _marker_list_matches(
    value: object,
    *,
    environment: Mapping[str, str],
    field: str,
) -> bool:
    """把 uv marker 列表解释为候选分支的析取。"""

    if not isinstance(value, list) or not value:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", f"uv.lock {field} must be a non-empty text list"
        )
    markers = cast("list[object]", value)
    results = [_marker_matches(marker, environment) for marker in markers]
    return any(results)


def _validate_target_markers(
    lock_mapping: Mapping[str, object],
    environment: Mapping[str, str],
) -> None:
    """校验全局 marker 语法并确认 lock 声明覆盖目标平台。"""

    resolution_markers = lock_mapping.get("resolution-markers")
    if resolution_markers is not None and not _marker_list_matches(
        resolution_markers,
        environment=environment,
        field="resolution-markers",
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PLATFORM_MISMATCH",
            "uv.lock resolution-markers does not cover the target platform",
        )
    for field in ("supported-markers", "required-markers"):
        markers = lock_mapping.get(field)
        if markers is not None and not _marker_list_matches(
            markers,
            environment=environment,
            field=field,
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_PLATFORM_MISMATCH",
                f"uv.lock {field} does not cover the target platform",
            )


def _sha256(path: Path) -> str:
    """流式计算 lock 摘要。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normal_name(name: str) -> str:
    """按 Python distribution 规则统一名称。"""

    return name.lower().replace("_", "-").replace(".", "-")


def _canonical_pep440_version(version: str) -> str:
    """验证并规范化 wheel 文件名中的 PEP 440 版本。"""

    match = _PEP440_VERSION.fullmatch(version)
    if match is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel filename does not contain a valid PEP 440 version",
        )
    pieces: list[str] = []
    epoch = match.group("epoch")
    if epoch is not None:
        pieces.append(f"{int(epoch)}!")
    pieces.append(match.group("release"))
    pre_label = match.group("pre_label")
    if pre_label is not None:
        normalized_pre = {
            "alpha": "a",
            "beta": "b",
            "c": "rc",
            "pre": "rc",
            "preview": "rc",
        }.get(pre_label.lower(), pre_label.lower())
        pieces.append(f"{normalized_pre}{int(match.group('pre_number') or '0')}")
    post_number = match.group("post_number_implicit") or match.group("post_number")
    if match.group("post_label") is not None or post_number is not None:
        pieces.append(f".post{int(post_number or '0')}")
    if match.group("dev_number") is not None or ".dev" in version.lower():
        pieces.append(f".dev{int(match.group('dev_number') or '0')}")
    local = match.group("local")
    if local is not None:
        pieces.append(f"+{re.sub(r'[-_]+', '.', local.lower())}")
    return "".join(pieces)


def _direct_wheel_version(
    raw_package: Mapping[str, object],
    *,
    raw_name: str,
    table_version: str,
    source: Mapping[object, object],
) -> str:
    """校验 direct-wheel 文件名,并保留其 METADATA 派生的表版本。"""

    source_url = source.get("url")
    if source_url is None:
        return table_version
    if not isinstance(source_url, str) or not source_url:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock direct source URL must be non-empty text"
        )
    filename = unquote(Path(urlsplit(source_url).path).name)
    if not filename.lower().endswith(".whl"):
        return table_version
    stem = filename[:-4]
    try:
        prefix, python_tag, abi_tag, platform_tag = stem.rsplit("-", 3)
    except ValueError as exc:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID", "direct wheel filename is malformed"
        ) from exc
    if not all(_WHEEL_TAG.fullmatch(tag) for tag in (python_tag, abi_tag, platform_tag)):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID", "direct wheel tags are malformed"
        )
    escaped_name = re.sub(r"[-_.]+", "_", raw_name).lower()
    name_prefix = f"{escaped_name}-"
    if not prefix.lower().startswith(name_prefix):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel distribution name does not match the lock record",
        )
    version_and_build = prefix[len(name_prefix) :]
    version_parts = version_and_build.split("-")
    if len(version_parts) == 1:
        wheel_version_text = version_parts[0]
    elif len(version_parts) == 2 and _WHEEL_BUILD.fullmatch(version_parts[1]):
        wheel_version_text = version_parts[0]
    else:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID", "direct wheel version or build tag is malformed"
        )
    wheel_version = _canonical_pep440_version(wheel_version_text)
    lock_version = _canonical_pep440_version(table_version)
    wheel_public_version = wheel_version.partition("+")[0]
    if wheel_public_version != lock_version.partition("+")[0] or (
        "+" in lock_version and wheel_version != lock_version
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel version does not match the lock table identity",
        )
    wheels = raw_package.get("wheels")
    if not isinstance(wheels, list):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel record must contain exactly one wheel artifact",
        )
    wheel_artifacts = cast("list[object]", wheels)
    if len(wheel_artifacts) != 1:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel record must contain exactly one wheel artifact",
        )
    artifact = wheel_artifacts[0]
    if (
        not isinstance(artifact, dict)
        or cast("dict[object, object]", artifact).get("url") != source_url
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID",
            "direct wheel source and artifact URLs must match exactly",
        )
    return table_version


def _artifact_hashes(package: Mapping[str, object]) -> tuple[str, ...]:
    """收集一个已选 package 记录的全部 sdist/wheel SHA256。"""

    artifacts: list[object] = []
    sdist = package.get("sdist")
    if sdist is not None:
        artifacts.append(sdist)
    wheels = package.get("wheels", [])
    if not isinstance(wheels, list):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package wheels must be an object list"
        )
    artifacts.extend(cast("list[object]", wheels))
    hashes: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock artifacts must be objects"
            )
        raw_hash = cast("dict[object, object]", artifact).get("hash")
        if not isinstance(raw_hash, str) or not raw_hash.startswith("sha256:"):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock artifacts require sha256 hashes"
            )
        hashes.add(raw_hash.removeprefix("sha256:"))
    return tuple(sorted(hashes))


def _package_from_record(
    raw_package: Mapping[str, object],
    *,
    source_distribution_version: str,
) -> ResolvedPackage | None:
    """把单个 uv package 记录转换为 distribution;virtual 项目不安装。"""

    raw_name = raw_package.get("name")
    source = raw_package.get("source")
    if not isinstance(raw_name, str) or not raw_name:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package name must be non-empty text"
        )
    if not isinstance(source, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package source must be an object"
        )
    source_mapping = cast("dict[object, object]", source)
    if "virtual" in source_mapping:
        return None
    raw_version = raw_package.get("version")
    if raw_version is None and _normal_name(raw_name) == "autovla":
        raw_version = source_distribution_version
    if not isinstance(raw_version, str) or not raw_version:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID",
            f"installed distribution {raw_name!r} has no exact version",
        )
    resolved_version = _direct_wheel_version(
        raw_package,
        raw_name=raw_name,
        table_version=raw_version,
        source=source_mapping,
    )
    return ResolvedPackage(
        name=_normal_name(raw_name),
        version=resolved_version,
        artifact_sha256=_artifact_hashes(raw_package),
    )


def _record_matches_target(
    raw_package: Mapping[str, object],
    environment: Mapping[str, str],
) -> bool:
    """判断 package variant 的 resolution marker 是否覆盖目标。"""

    markers = raw_package.get("resolution-markers")
    if markers is None:
        return True
    return _marker_list_matches(markers, environment=environment, field="package markers")


def _dependency_target(
    dependency: object,
    *,
    candidates: Mapping[str, list[Mapping[str, object]]],
    environment: Mapping[str, str],
) -> Mapping[str, object] | None:
    """按 marker、版本和 source 精确选择一个依赖记录。"""

    if not isinstance(dependency, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependencies must contain objects"
        )
    values = cast("dict[str, object]", dependency)
    if set(values) - _DEPENDENCY_FIELDS:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependency contains unsupported fields"
        )
    raw_name = values.get("name")
    if not isinstance(raw_name, str) or not raw_name:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependency name must be non-empty text"
        )
    marker = values.get("marker")
    if marker is not None and not _marker_matches(marker, environment):
        return None
    extras = values.get("extra")
    if extras is not None and (
        not isinstance(extras, list)
        or not extras
        or not all(isinstance(extra, str) and extra for extra in cast("list[object]", extras))
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependency extras must be non-empty text"
        )
    raw_version = values.get("version")
    if raw_version is not None and (not isinstance(raw_version, str) or not raw_version):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependency version must be exact text"
        )
    raw_source = values.get("source")
    if raw_source is not None and not isinstance(raw_source, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock dependency source must be an object"
        )
    choices = list(candidates.get(_normal_name(raw_name), ()))
    if raw_version is not None:
        choices = [choice for choice in choices if choice.get("version") == raw_version]
    if raw_source is not None:
        choices = [choice for choice in choices if choice.get("source") == raw_source]
    choices = [choice for choice in choices if _record_matches_target(choice, environment)]
    if len(choices) != 1:
        versions = sorted(
            {
                cast("str", choice.get("version") or "<unversioned>")
                for choice in candidates.get(_normal_name(raw_name), ())
            }
        )
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_DISTRIBUTION_AMBIGUOUS",
            f"{_normal_name(raw_name)} has no unique target distribution among: "
            f"{', '.join(versions) or '<missing>'}",
        )
    return choices[0]


def _reachable_records(
    raw_packages: list[object],
    *,
    environment: Mapping[str, str],
) -> list[Mapping[str, object]]:
    """从唯一虚拟项目根遍历目标平台可达的 package 图。"""

    candidates: dict[str, list[Mapping[str, object]]] = {}
    roots: list[Mapping[str, object]] = []
    for raw_package in raw_packages:
        if not isinstance(raw_package, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock package inventory must contain objects"
            )
        package = cast("dict[str, object]", raw_package)
        raw_name = package.get("name")
        source = package.get("source")
        if not isinstance(raw_name, str) or not raw_name:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock package name must be non-empty text"
            )
        if not isinstance(source, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock package source must be an object"
            )
        candidates.setdefault(_normal_name(raw_name), []).append(package)
        if cast("dict[object, object]", source).get("virtual") == ".":
            roots.append(package)
    if len(roots) != 1:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PROJECT_ROOT_AMBIGUOUS",
            "uv.lock must contain exactly one virtual project root",
        )

    reachable: list[Mapping[str, object]] = []
    selected: dict[str, Mapping[str, object]] = {}
    pending = [roots[0]]
    processed: set[int] = set()
    while pending:
        record = pending.pop()
        identity = id(record)
        if identity in processed:
            continue
        processed.add(identity)
        reachable.append(record)
        dependencies = record.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_GRAPH_INVALID", "uv.lock package dependencies must be an object list"
            )
        for dependency in cast("list[object]", dependencies):
            target = _dependency_target(
                dependency,
                candidates=candidates,
                environment=environment,
            )
            if target is None:
                continue
            target_name = _normal_name(cast("str", target["name"]))
            previous = selected.get(target_name)
            if previous is not None and previous is not target:
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_DISTRIBUTION_AMBIGUOUS",
                    f"{target_name} resolves to conflicting target distributions",
                )
            selected[target_name] = target
            pending.append(target)
    return reachable


def resolve_uv_lock(
    *,
    checkout_root: Path,
    profile: RuntimeProfileSpec,
    cuda_compatibility: CudaCompatibilityIntent,
    source_distribution_version: str,
) -> ResolvedRuntimeLock:
    """解析提交内 uv.lock,选择目标画像的唯一 distribution 清单并校验身份。

    输入是不可变 checkout、画像、源码 distribution 版本和显式 CUDA 观测意图;
    输出沿用 M12 ``ResolvedRuntimeLock.v2``,不访问网络也不修改 lock。
    """

    lock_path = checkout_root / profile.uv_project / "uv.lock"
    if not lock_path.is_file() or lock_path.is_symlink():
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_FILE_MISSING", "profile uv.lock must be a regular non-symlink file"
        )
    lock_sha256 = _sha256(lock_path)
    if profile.lock_sha256 is None or lock_sha256 != profile.lock_sha256:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_FILE_MISMATCH", "committed uv.lock does not match the profile digest"
        )
    if _toml_parser is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_UNAVAILABLE",
            "uv.lock resolution requires Python tomllib or the project tomli backport",
        )
    try:
        with lock_path.open("rb") as handle:
            payload = cast(object, _toml_parser.load(handle))
    except (OSError, _toml_parser.TOMLDecodeError) as exc:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "profile uv.lock is not valid TOML"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "profile uv.lock must contain one TOML document"
        )
    lock_mapping = cast("dict[str, object]", payload)
    expected_python = f"=={profile.requested_python_version}.*"
    if lock_mapping.get("requires-python") != expected_python:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PLATFORM_MISMATCH",
            "uv.lock requires-python does not match the runtime profile",
        )
    raw_packages = lock_mapping.get("package")
    if not isinstance(raw_packages, list):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package inventory must be an object list"
        )
    environment = _target_environment(profile)
    _validate_target_markers(lock_mapping, environment)
    reachable = _reachable_records(cast("list[object]", raw_packages), environment=environment)

    packages: list[ResolvedPackage] = []
    for raw_package in reachable:
        package = _package_from_record(
            raw_package,
            source_distribution_version=source_distribution_version,
        )
        if package is not None:
            packages.append(package)
    packages.sort(key=lambda package: package.name)

    if profile.resolver_version is None or profile.upstream_revision is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PROFILE_INCOMPLETE",
            "profile resolver version and upstream revision are required",
        )
    resolved = ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name=profile.resolver_name,
        resolver_version=profile.resolver_version,
        upstream_revision=profile.upstream_revision,
        lock_sha256=lock_sha256,
        packages=tuple(packages),
        cuda_compatibility=cuda_compatibility,
    )
    resolved.validate_profile(profile)
    return resolved


__all__ = ["resolve_uv_lock"]
