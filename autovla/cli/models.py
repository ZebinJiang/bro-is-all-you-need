"""输出模型动物园的轻量、稳定 JSON 状态。"""

from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import Mapping, Sequence

from autovla.models.readiness import (
    CheckpointReadiness,
    DefinitionReadiness,
    DistributedReadiness,
    ForwardReadiness,
    ModelFamilyReadiness,
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
    readiness: ModelFamilyReadiness | None,
) -> tuple[ModelStatusCategory, ...]:
    """把正交就绪轴窄投影为累计公共类别。"""

    categories = [ModelStatusCategory.ACTIVE_DEVELOPMENT]
    if readiness is None:
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
    readiness: ModelFamilyReadiness | None = None,
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
    return payload


def _catalog_status_categories(
    entry: ModelFamilyCatalogEntry,
) -> tuple[ModelStatusCategory, ...]:
    """仅按目录中接受的证据身份投影公共累计状态。"""

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
    if "C2R7_ONE_A100_STRICT_CHECKPOINT_LOAD_ACCEPTED" not in evidence:
        return tuple(categories)
    categories.append(ModelStatusCategory.CHECKPOINT_VALIDATED)
    return tuple(categories)


def build_status_payload(
    readiness_by_family: Mapping[str, ModelFamilyReadiness] | None = None,
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
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list")
    subparsers.add_parser("status")
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("family_key")
    return parser


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

    entry = get_model_family_catalog_entry(family_key)
    if not entry.active:
        raise ValueError("model inspect accepts only active M11 families")
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
    if command == "inspect":
        payload = build_inspect_payload(arguments.family_key)
    elif command == "list":
        payload = build_list_payload()
    else:
        payload = build_status_payload()
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
    "main",
    "project_model_status",
    "project_status_categories",
]
