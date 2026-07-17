"""M11 模型运行包、就绪轴和轻量状态投影测试。"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from autovla.cli.models import (
    ModelStatusCategory,
    build_status_payload,
    project_status_categories,
)
from autovla.models.assembly import (
    ModelAssemblyResult,
    ModelRuntimeAssetEvidence,
    ModelRuntimeBundle,
)
from autovla.models.readiness import (
    AssetReadiness,
    CheckpointReadiness,
    ConstructionReadiness,
    DataBindingReadiness,
    DefinitionReadiness,
    DistributedReadiness,
    EvidenceValidationKind,
    ForwardReadiness,
    ModelFamilyReadiness,
    PredictionReadiness,
    ReadinessAxis,
    ReadinessEvidenceReceipt,
    TrainingReadiness,
)
from autovla.models.registry import get_model_family_spec

ROOT = Path(__file__).resolve().parents[2]


def test_n1d7_dynamic_component_targets_exist_without_runtime_imports() -> None:
    """以 AST 核对 N1.7 注册目标,不导入 Torch 家族模块。"""

    family_path = ROOT / "autovla/models/families/gr00t_n1d7/family.py"
    family_tree = ast.parse(family_path.read_text(encoding="utf-8"), filename=str(family_path))
    factory_targets: dict[str, str] = {}
    for statement in family_tree.body:
        if not isinstance(statement, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "_FACTORIES"
            for target in statement.targets
        ):
            continue
        if not isinstance(statement.value, ast.Call):
            raise AssertionError("N1.7 _FACTORIES must remain a direct constructor call")
        factory_targets = {
            keyword.arg: ast.literal_eval(keyword.value)
            for keyword in statement.value.keywords
            if keyword.arg is not None
        }
        break

    expected_symbols = {"backbone": "_build_backbone", "action_head": "_build_action_head"}
    for component, expected_symbol in expected_symbols.items():
        module_name, symbol = factory_targets[component].split(":", maxsplit=1)
        assert symbol == expected_symbol
        source_path = ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
        source_tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        defined_names = {
            statement.name
            for statement in source_tree.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assert symbol in defined_names


def _definition():  # type: ignore[no-untyped-def]
    """返回现有唯一规范定义,不复制模型族定义栈。"""

    return get_model_family_spec("gr00t_n1d7")


def _receipt(
    evidence_id: str,
    axis: ReadinessAxis,
    state: object,
    validation_kind: EvidenceValidationKind,
    fingerprint_character: str,
) -> ReadinessEvidenceReceipt:
    """构造绑定同一规范定义的最小证据收据。"""

    definition = _definition()
    return ReadinessEvidenceReceipt(
        evidence_id=evidence_id,
        family_key=definition.family_key,
        definition_fingerprint=definition.fingerprint,
        axis=axis,
        state=cast(object, state),  # type: ignore[arg-type]
        validation_kind=validation_kind,
        artifact_fingerprint=fingerprint_character * 64,
    )


def _validated_readiness() -> ModelFamilyReadiness:
    """构造仅由测试收据提升的多轴就绪快照。"""

    return ModelFamilyReadiness.derive(
        _definition(),
        (
            _receipt(
                "source-complete",
                ReadinessAxis.DEFINITION,
                DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE,
                EvidenceValidationKind.SOURCE,
                "1",
            ),
            _receipt(
                "checkpoint-strict",
                ReadinessAxis.CHECKPOINT,
                CheckpointReadiness.STRICT_LOADED,
                EvidenceValidationKind.RUNTIME,
                "2",
            ),
            _receipt(
                "construct-source",
                ReadinessAxis.CONSTRUCTION,
                ConstructionReadiness.SOURCE_CONSTRUCTIBLE,
                EvidenceValidationKind.SOURCE,
                "3",
            ),
            _receipt(
                "forward-contract",
                ReadinessAxis.FORWARD,
                ForwardReadiness.CONTRACT_BATCH_VALIDATED,
                EvidenceValidationKind.RUNTIME,
                "4",
            ),
            _receipt(
                "training-optimizer",
                ReadinessAxis.TRAINING,
                TrainingReadiness.OPTIMIZER_VALIDATED,
                EvidenceValidationKind.RUNTIME,
                "5",
            ),
            _receipt(
                "distributed-ddp",
                ReadinessAxis.DISTRIBUTED,
                DistributedReadiness.DDP_VALIDATED,
                EvidenceValidationKind.RUNTIME,
                "6",
            ),
        ),
    )


def test_exact_readiness_axes_and_config_strings_do_not_promote_state() -> None:
    """闭集值必须精确,历史配置字符串不得自行提升任何证据轴。"""

    assert tuple(item.value for item in DefinitionReadiness) == (
        "absent",
        "architecture_defined",
        "executable_source_complete",
    )
    assert tuple(item.value for item in AssetReadiness) == (
        "unresolved",
        "manifest_verified",
        "complete_local_bundle",
    )
    assert tuple(item.value for item in CheckpointReadiness) == (
        "unresolved",
        "mapped",
        "strict_loaded",
        "resume_validated",
    )
    assert tuple(item.value for item in ConstructionReadiness) == (
        "unavailable",
        "source_constructible",
        "cuda_constructed",
    )
    assert tuple(item.value for item in ForwardReadiness) == (
        "unvalidated",
        "contract_batch_validated",
        "real_data_validated",
    )
    assert tuple(item.value for item in TrainingReadiness) == (
        "unvalidated",
        "backward_validated",
        "optimizer_validated",
        "checkpoint_resume_validated",
    )
    assert tuple(item.value for item in PredictionReadiness) == (
        "unvalidated",
        "deterministic_input_validated",
        "decoded_action_validated",
    )
    assert tuple(item.value for item in DataBindingReadiness) == (
        "none",
        "contract_fixture_only",
        "explicit_projection",
        "exact_real_dataset",
    )
    assert tuple(item.value for item in DistributedReadiness) == (
        "unvalidated",
        "ddp_validated",
        "zero1_validated",
        "zero2_validated",
        "zero3_validated",
        "cross_node_validated",
    )
    readiness = ModelFamilyReadiness.derive(_definition())
    assert readiness.definition is DefinitionReadiness.ARCHITECTURE_DEFINED
    assert readiness.assets is AssetReadiness.UNRESOLVED
    assert readiness.checkpoint is CheckpointReadiness.UNRESOLVED
    assert readiness.construction is ConstructionReadiness.UNAVAILABLE
    assert readiness.validation.to_json_dict() == {"runtime": [], "source": [], "static": []}
    absent = ModelFamilyReadiness.absent("unregistered_family")
    assert absent.definition is DefinitionReadiness.ABSENT
    assert absent.family_definition is None


def test_receipts_validate_axis_kind_identity_and_impossible_states() -> None:
    """错轴、错证据种类、身份漂移和无构造运行证据均关闭。"""

    with pytest.raises(TypeError, match="state type"):
        _receipt(
            "wrong-axis",
            ReadinessAxis.ASSETS,
            CheckpointReadiness.MAPPED,
            EvidenceValidationKind.STATIC,
            "7",
        )
    with pytest.raises(ValueError, match="requires runtime evidence"):
        _receipt(
            "wrong-kind",
            ReadinessAxis.FORWARD,
            ForwardReadiness.CONTRACT_BATCH_VALIDATED,
            EvidenceValidationKind.STATIC,
            "8",
        )
    checkpoint = _receipt(
        "strict-without-source",
        ReadinessAxis.CHECKPOINT,
        CheckpointReadiness.STRICT_LOADED,
        EvidenceValidationKind.RUNTIME,
        "9",
    )
    with pytest.raises(ValueError, match="executable source"):
        ModelFamilyReadiness.derive(_definition(), (checkpoint,))
    receipts = (
        _receipt(
            "source",
            ReadinessAxis.DEFINITION,
            DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE,
            EvidenceValidationKind.SOURCE,
            "a",
        ),
        _receipt(
            "construct",
            ReadinessAxis.CONSTRUCTION,
            ConstructionReadiness.SOURCE_CONSTRUCTIBLE,
            EvidenceValidationKind.SOURCE,
            "b",
        ),
        _receipt(
            "real-forward",
            ReadinessAxis.FORWARD,
            ForwardReadiness.REAL_DATA_VALIDATED,
            EvidenceValidationKind.RUNTIME,
            "c",
        ),
    )
    with pytest.raises(ValueError, match="real-data forward"):
        ModelFamilyReadiness.derive(_definition(), receipts)
    baseline = ModelFamilyReadiness.derive(_definition())
    with pytest.raises(ValueError, match="not derived"):
        ModelFamilyReadiness(
            family_key=baseline.family_key,
            family_definition=baseline.family_definition,
            definition=DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE,
            assets=baseline.assets,
            checkpoint=baseline.checkpoint,
            construction=baseline.construction,
            forward=baseline.forward,
            training=baseline.training,
            prediction=baseline.prediction,
            data_binding=baseline.data_binding,
            distributed=baseline.distributed,
            validation=baseline.validation,
            receipts=(),
        )


def test_evidence_derivation_serialization_and_fingerprint_are_stable() -> None:
    """输入顺序不得影响收据排序、JSON 或指纹。"""

    readiness = _validated_readiness()
    reversed_readiness = ModelFamilyReadiness.derive(
        _definition(), tuple(reversed(readiness.receipts))
    )
    assert readiness == reversed_readiness
    assert readiness.to_json() == reversed_readiness.to_json()
    assert readiness.fingerprint == reversed_readiness.fingerprint
    assert json.loads(readiness.to_json()) == readiness.to_json_dict()
    assert readiness.validation.source == ("construct-source", "source-complete")
    assert readiness.validation.runtime == (
        "checkpoint-strict",
        "distributed-ddp",
        "forward-contract",
        "training-optimizer",
    )


def test_status_category_projection_is_monotonic_and_active_zoo_is_exact() -> None:
    """公共类别只按已提供证据累计,默认动物园不得扩展或提升。"""

    assert project_status_categories(None) == (ModelStatusCategory.ACTIVE_DEVELOPMENT,)
    categories = project_status_categories(_validated_readiness())
    assert categories == tuple(ModelStatusCategory)
    payload = build_status_payload()
    assert payload["backend_decision"] == "NO_BACKEND_WINNER"
    families = cast(list[dict[str, object]], payload["families"])
    assert [item["family_key"] for item in families] == [
        "gr00t_n1d6",
        "gr00t_n1d7",
        "pi0_5",
    ]
    assert [item["category"] for item in families] == [
        "checkpoint-validated",
        "source-executable",
        "source-executable",
    ]
    assert [item["asset_gate"] for item in families] == [
        "BLOCKED_C3_DATA",
        "BLOCKED_LICENSE",
        "BLOCKED_LICENSE",
    ]


def test_runtime_bundle_projects_the_canonical_assembly_result_without_copying() -> None:
    """运行包必须沿用同一装配结果中的处理器、模型和证据对象。"""

    definition = _definition()
    result = cast(
        ModelAssemblyResult[object, object, object, object, object, object],
        object.__new__(ModelAssemblyResult),
    )
    processor = object()
    model = object()
    checkpoint_adapter = object()
    checkpoint_evidence = object()
    tuning_plan = object()
    asset_fingerprint = "d" * 64
    object.__setattr__(
        result,
        "plan",
        SimpleNamespace(
            definition=definition,
            asset_bundle_fingerprint=asset_fingerprint,
        ),
    )
    object.__setattr__(result, "processor", processor)
    object.__setattr__(result, "model", model)
    object.__setattr__(result, "checkpoint_adapter", checkpoint_adapter)
    object.__setattr__(result, "checkpoint_load", checkpoint_evidence)
    object.__setattr__(result, "tuning_freeze", tuning_plan)
    bundle = ModelRuntimeBundle(
        assembly_result=result,
        family_definition=definition,
        runtime_profile_identity="model-gr00t-n1d7@locked",
        asset_evidence=ModelRuntimeAssetEvidence(
            asset_bundle_fingerprint=asset_fingerprint,
            manifest_fingerprint="e" * 64,
            evidence_ids=("manifest-verified",),
        ),
    )
    assert bundle.processor is processor
    assert bundle.model is model
    assert bundle.checkpoint_adapter is checkpoint_adapter
    assert bundle.checkpoint_evidence is checkpoint_evidence
    assert bundle.tuning_freeze_plan is tuning_plan


def test_model_metadata_and_cli_status_imports_remain_lightweight() -> None:
    """列状态不得导入重运行时或任一模型族私有模块。"""

    script = """
import json
import subprocess
import sys
import autovla.models.readiness
import autovla.models.assembly.runtime
from autovla.cli.models import build_status_payload
payload = build_status_payload()
assert [item['family_key'] for item in payload['families']] == [
    'gr00t_n1d6', 'gr00t_n1d7', 'pi0_5'
]
forbidden = {'torch', 'transformers', 'deepspeed', 'jax', 'flax', 'orbax'}
assert not forbidden & set(sys.modules)
private_prefixes = (
    'autovla.models.families.gr00t_n1d6',
    'autovla.models.families.gr00t_n1d7',
    'autovla.models.families.pi0_5',
)
assert not any(name.startswith(private_prefixes) for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
