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
    categories = project_status_categories(readiness)
    payload: dict[str, object] = {
        "active": entry.active,
        "category": categories[-1].value,
        "family_key": entry.family_key,
        "validated_categories": [category.value for category in categories],
    }
    if readiness is not None:
        payload["readiness"] = readiness.to_json_dict()
        payload["readiness_fingerprint"] = readiness.fingerprint
    return payload


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
    """构造尚未接入 pyproject 入口的模型状态解析器。"""

    parser = argparse.ArgumentParser(prog="autovla-models")
    parser.add_argument("command", choices=("status",), nargs="?", default="status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """打印稳定 JSON, CLI 入口注册留给后续集成 writer。"""

    build_parser().parse_args(argv)
    print(
        json.dumps(
            build_status_payload(),
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
    "build_parser",
    "build_status_payload",
    "main",
    "project_model_status",
    "project_status_categories",
]
