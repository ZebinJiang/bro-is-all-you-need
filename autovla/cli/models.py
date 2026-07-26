"""输出模型动物园的轻量、稳定 JSON 状态。"""

from __future__ import annotations

import argparse
import json
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

from autovla.models.errors import (
    DeferredModelFamilyError,
    ModelCatalogError,
    UnknownModelFamilyError,
)
from autovla.models.readiness import (
    CheckpointReadiness,
    DefinitionReadiness,
    DistributedReadiness,
    ForwardReadiness,
    ModelFamilyReadiness,
    ModelFamilyReadinessSnapshot,
    TrainingReadiness,
)
from autovla.models.registry import ModelFamilyCatalogEntry, list_model_family_catalog


class ModelStatusCategory(str, Enum):
    """提供由低到高且不冒充未验证能力的状态类别。"""

    ACTIVE_DEVELOPMENT = "active-development"
    SOURCE_EXECUTABLE = "source-executable"
    CHECKPOINT_VALIDATED = "checkpoint-validated"
    FORWARD_VALIDATED = "forward-validated"
    TRAINING_VALIDATED = "training-validated"
    DISTRIBUTED_VALIDATED = "distributed-validated"


def project_status_categories(
    readiness: ModelFamilyReadiness | ModelFamilyReadinessSnapshot | None,
) -> tuple[ModelStatusCategory, ...]:
    """把正交就绪轴窄投影为累计公共类别。"""

    categories = [ModelStatusCategory.ACTIVE_DEVELOPMENT]
    if readiness is None:
        return tuple(categories)
    if isinstance(readiness, ModelFamilyReadinessSnapshot):
        projection = readiness.projection
        if not projection.source_available:
            return tuple(categories)
        categories.append(ModelStatusCategory.SOURCE_EXECUTABLE)
        if not projection.checkpoint_validated:
            return tuple(categories)
        categories.append(ModelStatusCategory.CHECKPOINT_VALIDATED)
        if not projection.forward_validated:
            return tuple(categories)
        categories.append(ModelStatusCategory.FORWARD_VALIDATED)
        if not projection.training_validated:
            return tuple(categories)
        categories.append(ModelStatusCategory.TRAINING_VALIDATED)
        if projection.distributed_validated:
            categories.append(ModelStatusCategory.DISTRIBUTED_VALIDATED)
        return tuple(categories)
    if readiness.definition is DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE:
        categories.append(ModelStatusCategory.SOURCE_EXECUTABLE)
    else:
        return tuple(categories)
    if readiness.checkpoint in {
        CheckpointReadiness.STRICT_LOADED,
        CheckpointReadiness.RESUME_VALIDATED,
    }:
        categories.append(ModelStatusCategory.CHECKPOINT_VALIDATED)
    else:
        return tuple(categories)
    if readiness.forward is not ForwardReadiness.UNVALIDATED:
        categories.append(ModelStatusCategory.FORWARD_VALIDATED)
    else:
        return tuple(categories)
    if readiness.training in {
        TrainingReadiness.OPTIMIZER_VALIDATED,
        TrainingReadiness.CHECKPOINT_RESUME_VALIDATED,
    }:
        categories.append(ModelStatusCategory.TRAINING_VALIDATED)
    else:
        return tuple(categories)
    if readiness.distributed is not DistributedReadiness.UNVALIDATED:
        categories.append(ModelStatusCategory.DISTRIBUTED_VALIDATED)
    return tuple(categories)


def project_model_status(
    entry: ModelFamilyCatalogEntry,
    readiness: ModelFamilyReadiness | ModelFamilyReadinessSnapshot | None = None,
) -> dict[str, object]:
    """为一个清单项生成不触发家族私有模块导入的状态。"""

    if readiness is not None and readiness.family_key != entry.family_key:
        raise ValueError("readiness family does not match catalog entry")
    categories = (
        project_status_categories(readiness)
        if readiness is not None
        else _catalog_status_categories(entry)
    )
    payload: dict[str, object] = {
        "active": entry.active,
        "category": categories[-1].value,
        "family_key": entry.family_key,
        "asset_gate": entry.asset_gate,
        "accepted_evidence_ids": list(entry.accepted_evidence_ids),
        "runtime_profile_id": entry.runtime_profile_id,
        "validated_categories": [category.value for category in categories],
    }
    if readiness is not None:
        payload["readiness"] = readiness.to_json_dict()
        payload["readiness_fingerprint"] = readiness.fingerprint
        if isinstance(readiness, ModelFamilyReadinessSnapshot):
            payload["readiness_projection"] = readiness.projection.to_json_dict()
    return payload


def _catalog_status_categories(
    entry: ModelFamilyCatalogEntry,
) -> tuple[ModelStatusCategory, ...]:
    """仅按目录历史证据投影源码状态,不生成运行类别。"""

    evidence = set(entry.accepted_evidence_ids)
    categories = [ModelStatusCategory.ACTIVE_DEVELOPMENT]
    source_id = {
        "gr00t_n1d6": "M11_N1D6_EXECUTABLE_SOURCE_ACCEPTED",
        "gr00t_n1d7": "M11_N1D7_EXECUTABLE_SOURCE_ACCEPTED",
        "pi0_5": "M11_PI05_EXECUTABLE_SOURCE_ACCEPTED",
    }.get(entry.family_key)
    if source_id not in evidence:
        return tuple(categories)
    categories.append(ModelStatusCategory.SOURCE_EXECUTABLE)
    return tuple(categories)


def build_status_payload(
    readiness_by_family: (
        Mapping[str, ModelFamilyReadiness | ModelFamilyReadinessSnapshot] | None
    ) = None,
) -> dict[str, object]:
    """稳定列出三个活跃家族,未提供收据时一律不提升状态。"""

    supplied = {} if readiness_by_family is None else dict(readiness_by_family)
    entries = list_model_family_catalog()
    active_keys = tuple(entry.family_key for entry in entries)
    if active_keys != ("gr00t_n1d6", "gr00t_n1d7", "pi0_5"):
        raise ValueError("active model zoo identity drifted from the M11 contract")
    unknown = set(supplied) - set(active_keys)
    if unknown:
        raise ValueError(f"readiness supplied for inactive or unknown families: {sorted(unknown)}")
    return {
        "backend_decision": "NO_BACKEND_WINNER",
        "families": [
            project_model_status(entry, supplied.get(entry.family_key)) for entry in entries
        ],
        "schema_version": "autovla.model_status.v1",
    }


def build_parser() -> argparse.ArgumentParser:
    """构造 list/status/inspect 模型元数据命令。"""

    parser = argparse.ArgumentParser(prog="autovla-models")
    parser.add_argument("--readiness-file", type=Path)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list")
    status = subparsers.add_parser("status")
    status.add_argument("--readiness-file", type=Path)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("family_key")
    return parser


def load_status_readiness(path: Path) -> dict[str, ModelFamilyReadinessSnapshot]:
    """显式读取 readiness 文件并按当前模型族定义核对身份。"""

    from autovla.models.readiness_io import read_readiness_file
    from autovla.models.registry import get_model_family_spec

    definitions = {
        entry.family_key: get_model_family_spec(entry.family_key)
        for entry in list_model_family_catalog()
    }
    return read_readiness_file(path, definitions)


def build_list_payload() -> dict[str, object]:
    """列出三个活跃家族的轻量身份与证据级别。"""

    return {
        "backend_decision": "NO_BACKEND_WINNER",
        "families": [project_model_status(entry) for entry in list_model_family_catalog()],
        "schema_version": "autovla.model_list.v1",
    }


def build_inspect_payload(family_key: str) -> dict[str, object]:
    """按需解析一个家族的定义、工厂、资产包和运行画像。"""

    from autovla.assets import DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY
    from autovla.models.registry import (
        get_model_family_catalog_entry,
        get_model_family_registration,
    )

    try:
        entry = get_model_family_catalog_entry(family_key)
    except KeyError as exc:
        raise UnknownModelFamilyError(family_key) from exc
    if not entry.active:
        raise DeferredModelFamilyError(entry.family_key)
    registration = get_model_family_registration(entry.family_key)
    return {
        "asset_bundle": (
            DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY.require(entry.family_key).to_json_dict()
        ),
        "backend_decision": "NO_BACKEND_WINNER",
        "definition": registration.spec.to_json_dict(),
        "factories": {
            "asset_bundle": (
                None
                if registration.asset_bundle is None
                else registration.asset_bundle.factory_path
            ),
            "checkpoint": (
                None
                if registration.checkpoint_adapter is None
                else registration.checkpoint_adapter.factory_path
            ),
            "family": None if registration.factory is None else registration.factory.factory_path,
            "runtime_bundle": registration.runtime_bundle.factory_path,
        },
        "runtime_profile_id": registration.runtime_profile_id,
        "schema_version": "autovla.model_inspect.v1",
        "status": project_model_status(entry),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """打印稳定 JSON;只有 inspect 会按需导入单个家族元数据。"""

    arguments = build_parser().parse_args(argv)
    command = arguments.command or "status"
    try:
        if command == "inspect":
            payload = build_inspect_payload(arguments.family_key)
        elif command == "list":
            payload = build_list_payload()
        else:
            readiness_path = arguments.readiness_file
            payload = build_status_payload(
                None if readiness_path is None else load_status_readiness(readiness_path)
            )
    except (ModelCatalogError, ValueError) as exc:
        if isinstance(exc, ModelCatalogError):
            error_payload = exc.to_json_dict()
        else:
            error_payload = {
                "code": "READINESS_FILE_INVALID",
                "message": str(exc),
            }
        payload = {
            "backend_decision": "NO_BACKEND_WINNER",
            "error": error_payload,
            "ok": False,
            "schema_version": "autovla.model_error.v1",
        }
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - 由命令行直接触发
    raise SystemExit(main())


__all__ = [
    "ModelStatusCategory",
    "build_inspect_payload",
    "build_list_payload",
    "build_parser",
    "build_status_payload",
    "load_status_readiness",
    "main",
    "project_model_status",
    "project_status_categories",
]
