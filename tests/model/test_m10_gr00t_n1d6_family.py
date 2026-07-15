"""M10 GR00T N1.6.1 家族适配器的 fail-closed 契约测试。"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest

from autovla.models.capabilities import RuntimeSupportLevel, TopologySupport
from autovla.models.families import M10_MODEL_ZOO_CONTRACT
from autovla.models.families.gr00t_n1d6.specification import (
    GR00T_N1D6_SPEC,
    Gr00tN1d6FamilyDefinition,
)

if TYPE_CHECKING:
    from autovla.models.outputs import CheckpointLoadReport


class _FakeTensor:
    """提供不依赖 torch 的确定性张量元素数量。"""

    def __init__(self, element_count: int) -> None:
        """保存测试指定的元素数量。"""

        self._element_count = element_count

    def numel(self) -> int:
        """返回测试张量元素数量。"""

        return self._element_count


class _FakeModel:
    """提供 checkpoint 证据测试所需的最小状态映射。"""

    def state_dict(self) -> dict[str, _FakeTensor]:
        """返回两个键但共十个元素的模型状态。"""

        return {"backbone.weight": _FakeTensor(6), "action_head.bias": _FakeTensor(4)}


def _checkpoint_report(*, mapped_keys: tuple[str, ...]) -> CheckpointLoadReport:
    """构造不访问资产或权重的本地 checkpoint 报告。"""

    return cast(
        "CheckpointLoadReport",
        SimpleNamespace(
            mapped_keys=mapped_keys,
            missing_keys=(),
            unexpected_keys=(),
            shape_mismatches=(),
            strictness="allow_known_optional",
        ),
    )


def _write(path: Path, payload: object) -> None:
    """写入小型本地 JSON fixture。"""

    path.write_text(json.dumps(payload), encoding="utf-8")


def _identity_statistics(dimension: int):
    """构造维度显式的 identity mean/std 统计。"""

    from autovla.core.semantics import AlignmentMode, AlignmentPolicy, TensorLayout
    from autovla.data.normalization import ConstantFeaturePolicy, FeatureStatistics

    return FeatureStatistics(
        method="mean_std",
        layout=TensorLayout.feature(dimension),
        mean=np.zeros(dimension, dtype=np.float32),
        std=np.ones(dimension, dtype=np.float32),
        constant_feature_policy=ConstantFeaturePolicy.IDENTITY,
        alignment=AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES),
    )


def test_required_public_classes_and_evidence_bounded_definition() -> None:
    """九个公开类齐全,运行时与后端声明保持证据边界。"""

    required = {
        "config.py": "Gr00tN1d6Config",
        "processor.py": "Gr00tN1d6Processor",
        "backbone.py": "EagleVisionLanguageBackbone",
        "action_head.py": "Gr00tN1d6ActionHead",
        "model.py": "Gr00tN1d6Model",
        "factory.py": "Gr00tN1d6ModelFactory",
        "checkpoint.py": "Gr00tN1d6CheckpointAdapter",
        "assets.py": "Gr00tN1d6AssetBundle",
        "specification.py": "Gr00tN1d6FamilyDefinition",
    }
    root = Path("autovla/models/families/gr00t_n1d6")
    for filename, class_name in required.items():
        tree = ast.parse((root / filename).read_text(encoding="utf-8"))
        assert class_name in {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    assert type(GR00T_N1D6_SPEC) is Gr00tN1d6FamilyDefinition
    requirements = GR00T_N1D6_SPEC.assembly_requirements
    assert requirements is not None
    assert requirements.runtime_level is RuntimeSupportLevel.ASSET_GATED
    assert requirements.evidence.source_architecture_complete
    assert not requirements.evidence.official_checkpoint_load_validated
    assert not requirements.evidence.single_gpu_validated
    assert TopologySupport.SINGLE_GPU in requirements.topologies
    assert TopologySupport.DEEPSPEED_ZERO_3 in requirements.topologies
    assert not requirements.evidence.deepspeed_zero_3_validated
    assert M10_MODEL_ZOO_CONTRACT.backend_decision == "NO_BACKEND_WINNER"


def test_checkpoint_evidence_counts_loaded_tensor_elements_and_rejects_unknown_keys() -> None:
    """两个映射键计为十个元素,报告未知键时严格失败。"""

    from autovla.models.families.gr00t_n1d6.factory import _loaded_tensor_element_count

    model = _FakeModel()
    report = _checkpoint_report(mapped_keys=("backbone.weight", "action_head.bias"))
    assert _loaded_tensor_element_count(model, report) == 10

    inconsistent = _checkpoint_report(mapped_keys=("backbone.weight", "unknown.weight"))
    with pytest.raises(ValueError, match="inconsistent with post-load model state"):
        _loaded_tensor_element_count(model, inconsistent)


def test_official_metadata_projects_camera_sincos_normalization_and_action_config(
    tmp_path: Path,
) -> None:
    """官方 metadata 驱动 per-embodiment 输入、归一化和相对关节策略。"""

    pytest.importorskip("torch")
    from autovla.models.components.relative_actions import (
        RelativeActionKind,
        RelativeActionPolicy,
    )
    from autovla.models.families.gr00t_n1d6.checkpoint import (
        Gr00tN1d6CheckpointAdapter,
    )

    root = tmp_path / "metadata"
    root.mkdir()
    _write(
        root / "config.json",
        {
            "action_horizon": 50,
            "max_state_dim": 128,
            "max_action_dim": 128,
            "max_num_embodiments": 32,
            "model_name": "nvidia/Eagle-Block2A-2B-v2",
        },
    )
    _write(root / "embodiment_id.json", {"gr1": 20})
    _write(
        root / "processor_config.json",
        {
            "processor_kwargs": {
                "max_action_horizon": 50,
                "max_state_dim": 128,
                "max_action_dim": 128,
                "use_percentiles": False,
                "clip_outliers": True,
                "use_relative_action": True,
                "apply_sincos_state_encoding": True,
                "modality_configs": {
                    "gr1": {
                        "video": {"modality_keys": ["camera.front"]},
                        "state": {
                            "modality_keys": ["joint"],
                            "sin_cos_embedding_keys": ["joint"],
                            "mean_std_embedding_keys": [],
                        },
                        "action": {
                            "modality_keys": ["joint", "gripper"],
                            "mean_std_embedding_keys": ["gripper"],
                            "action_configs": [
                                {
                                    "rep": "relative",
                                    "type": "non_eef",
                                    "format": "default",
                                    "state_key": "joint",
                                },
                                {
                                    "rep": "absolute",
                                    "type": "non_eef",
                                    "format": "default",
                                },
                            ],
                        },
                    }
                },
            }
        },
    )
    _write(
        root / "statistics.json",
        {
            "gr1": {
                "state": {
                    "joint": {
                        "mean": [0.0, 0.0],
                        "std": [1.0, 1.0],
                        "min": [-3.14, -3.14],
                        "max": [3.14, 3.14],
                    }
                },
                "action": {
                    "joint": {
                        "mean": [0.0, 0.0],
                        "std": [1.0, 1.0],
                        "min": [-2.0, -4.0],
                        "max": [2.0, 4.0],
                    },
                    "gripper": {
                        "mean": [0.5],
                        "std": [0.25],
                        "min": [0.0],
                        "max": [1.0],
                    },
                },
            }
        },
    )

    config = Gr00tN1d6CheckpointAdapter().parse_official_metadata(
        root,
        eagle_asset_path=tmp_path / "unused-local-path",
    )
    metadata = config.statistics["gr1"]
    assert metadata.camera_order == ("camera.front",)
    assert metadata.sin_cos_state_slices == ((0, 2),)
    assert metadata.state.dimension == 4
    assert metadata.mean_std_action_modalities == ("gripper",)
    assert metadata.relative_action_policies == (
        RelativeActionPolicy(RelativeActionKind.JOINT, 0, 0, 2),
    )
    assert config.tune_top_llm_layers == 4


def test_eef_relative_action_uses_canonical_se3_stage_only() -> None:
    """EEF 变换进入规范 TransformPlan,processor 不保留私有 kernel。"""

    pytest.importorskip("torch")
    from autovla.data.transforms import SE3RelativeActionStage
    from autovla.models.components.relative_actions import (
        EndEffectorRepresentation,
        RelativeActionKind,
        RelativeActionPolicy,
    )
    from autovla.models.families.gr00t_n1d6.config import (
        EmbodimentStatistics,
        Gr00tN1d6Config,
    )

    statistics = EmbodimentStatistics(
        state=_identity_statistics(6),
        action=_identity_statistics(6),
        relative_action_policies=(
            RelativeActionPolicy(
                RelativeActionKind.END_EFFECTOR,
                0,
                0,
                6,
                EndEffectorRepresentation.XYZ_ROTVEC,
            ),
        ),
        source_fingerprint="fixture-canonical-se3",
    )
    config = Gr00tN1d6Config(
        embodiment_ids={"eef": 0},
        statistics={"eef": statistics},
        use_relative_actions=True,
    )
    plan = config.transform_plan("eef", state_shape=(1, 6), action_shape=(16, 6))
    assert isinstance(plan.stages[0], SE3RelativeActionStage)
    source = Path("autovla/models/families/gr00t_n1d6/processor.py").read_text(encoding="utf-8")
    assert "_apply_eef" not in source


def test_checkpoint_and_assembly_boundaries_are_strict_and_local() -> None:
    """pickle 权重不能成为候选,组合工厂只接受共享请求。"""

    checkpoint_source = Path("autovla/models/families/gr00t_n1d6/checkpoint.py").read_text(
        encoding="utf-8"
    )
    assert 'getattr(torch, "load"' not in checkpoint_source
    assert "pytorch_model.bin" not in checkpoint_source
    assert "model.pt" not in checkpoint_source
    factory_source = Path("autovla/models/families/gr00t_n1d6/factory.py").read_text(
        encoding="utf-8"
    )
    assert "request: ModelAssemblyRequest" in factory_source
    assert "ModelAssemblyResult(" in factory_source
