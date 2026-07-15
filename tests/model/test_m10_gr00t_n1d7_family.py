"""M10 GR00T N1.7 家族契约和失败关闭测试。"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from autovla.data.transforms import SE3RelativeActionTransform
from autovla.models.assembly import ModelFactory, ModelRuntimeSupportError, resolve_model_assembly
from autovla.models.capabilities import (
    ImageResolutionPolicy,
    RuntimeSupportLevel,
    TopologySupport,
)
from autovla.models.families.gr00t_n1d7 import (
    CosmosReason2VisionLanguageBackbone,
    Gr00tN1d7ActionHead,
    Gr00tN1d7AssetBundle,
    Gr00tN1d7CheckpointAdapter,
    Gr00tN1d7Config,
    Gr00tN1d7FamilyDefinition,
    Gr00tN1d7Model,
    Gr00tN1d7ModelFactory,
    Gr00tN1d7Processor,
)
from autovla.models.families.gr00t_n1d7.family import GR00T_N1D7_FAMILY
from autovla.models.families.gr00t_n1d7.source_map import SOURCE_MAP


def _artifact_payload() -> dict[str, object]:
    """返回 checkpoint 实现值而非源码默认值。"""

    return {
        "select_layer": 16,
        "num_layers": 32,
        "vl_self_attention_layers": 4,
        "load_bf16": True,
        "state_dropout_prob": 0.2,
        "max_state_dim": 132,
        "max_action_dim": 132,
        "action_horizon": 40,
    }


def _config() -> Gr00tN1d7Config:
    """返回使用测试固定 Cosmos revision 的 artifact 配置。"""

    return Gr00tN1d7Config.from_artifact_mapping(
        _artifact_payload(),
        cosmos_revision="a" * 40,
    )


def _checkpoint_root(root: Path, *, unsafe_pickle: bool = False) -> Path:
    """构造不含真实权重内容的最小本地索引 fixture。"""

    root.mkdir()
    (root / "LICENSE").write_text("fixture license metadata\n", encoding="utf-8")
    (root / "config.json").write_text(json.dumps(_artifact_payload()), encoding="utf-8")
    for name in ("embodiment_id.json", "processor_config.json", "statistics.json"):
        (root / name).write_text("{}", encoding="utf-8")
    shard = "model-00001-of-00001.safetensors"
    (root / shard).write_bytes(b"")
    index = {
        "weight_map": {
            "model.backbone.language.weight": shard,
            "model.action_head.diffusion.weight": shard,
        }
    }
    (root / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    if unsafe_pickle:
        (root / "pytorch_model.bin").write_bytes(b"not-a-real-pickle")
    return root


def test_package_exposes_exact_nine_public_classes_and_stays_lightweight() -> None:
    """包入口只暴露指定九类且不隐式加载重型运行时。"""

    import autovla.models.families.gr00t_n1d7 as package

    assert set(package.__all__) == {
        "CosmosReason2VisionLanguageBackbone",
        "Gr00tN1d7ActionHead",
        "Gr00tN1d7AssetBundle",
        "Gr00tN1d7CheckpointAdapter",
        "Gr00tN1d7Config",
        "Gr00tN1d7FamilyDefinition",
        "Gr00tN1d7Model",
        "Gr00tN1d7ModelFactory",
        "Gr00tN1d7Processor",
    }
    script = """
import sys
import autovla.models.families.gr00t_n1d7
assert not {'torch', 'transformers', 'safetensors'} & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_artifact_config_overrides_source_defaults_and_closes_shapes() -> None:
    """artifact 的 16/32/BF16/dropout 与 132/40 契约不可静默回退。"""

    config = _config()
    assert config.retained_language_layers == 16
    assert config.diffusion_layers == 32
    assert (config.max_state_dim, config.max_action_dim, config.action_horizon) == (
        132,
        132,
        40,
    )
    assert config.load_bf16 is True
    assert config.local_files_only is True
    assert config.trust_remote_code is False
    source_defaults = dict(_artifact_payload())
    source_defaults.update(select_layer=12, num_layers=16, load_bf16=False)
    with pytest.raises(ValueError, match="artifact"):
        Gr00tN1d7Config.from_artifact_mapping(
            source_defaults,
            cosmos_revision="a" * 40,
        )


def test_family_definition_is_distinct_typed_and_asset_gated() -> None:
    """N1.7 定义声明动态图像和精确形状但不声明运行时就绪。"""

    definition = Gr00tN1d7FamilyDefinition()
    assert definition == GR00T_N1D7_FAMILY
    assert definition.family_key == "gr00t_n1d7"
    assert definition.shape.to_tuple() == (40, 132, 132)
    assert definition.inputs.image_resolution_policy is ImageResolutionPolicy.PROCESSOR_MANAGED
    assert definition.runtime_supported is False
    assert definition.assembly_requirements is not None
    assert definition.assembly_requirements.runtime_level is RuntimeSupportLevel.ASSET_GATED
    assert definition.assembly_requirements.topologies == (TopologySupport.METADATA_ONLY,)
    assert definition.assembly_requirements.evidence.source_architecture_complete is True
    assert definition.assembly_requirements.evidence.official_asset_bundle_available is False
    assert SOURCE_MAP["backend_decision"] == "NO_BACKEND_WINNER"


def test_processor_projects_dynamic_grid_and_relative_eef_to_canonical_se3() -> None:
    """动态图像与 XYZ_ROT6D 元数据使用共享 SE(3) 计划。"""

    processor = Gr00tN1d7Processor(_config())
    projection = processor.project_contract(
        image_keys=("camera.rgb_0", "camera.rgb_1"),
        state_keys=("state.eef_pose",),
        action_configs=(
            {
                "key": "action.eef_pose",
                "state_key": "state.eef_pose",
                "type": "eef",
                "representation": "relative",
                "format": "xyz_rot6d",
                "indices": tuple(range(9)),
                "canonical_pose_indices": (0, 1, 2, 3, 4, 5),
                "state_pose_indices": (0, 1, 2, 3, 4, 5),
            },
        ),
        image_grid_thw=((1, 32, 48), (1, 24, 24)),
    )
    assert projection.image_grid_thw == ((1, 32, 48), (1, 24, 24))
    assert projection.left_padding and projection.images_before_language
    plan = processor.transform_plan(projection)
    assert len(plan.stages) == 1
    assert isinstance(plan.stages[0], SE3RelativeActionTransform)
    assert plan.stages[0].descriptor.reversible is True
    processor.validate_padded_shapes(
        state_width=132,
        action_shape=(40, 132),
        state_mask_width=132,
        action_mask_shape=(40, 132),
    )
    with pytest.raises(ValueError, match="padded"):
        processor.validate_padded_shapes(
            state_width=131,
            action_shape=(40, 132),
            state_mask_width=132,
            action_mask_shape=(40, 132),
        )


def test_architecture_components_share_config_and_explicit_tuning_defaults() -> None:
    """骨干、动作头和组合模型共享配置且默认冻结/调优无歧义。"""

    config = _config()
    backbone = CosmosReason2VisionLanguageBackbone(config)
    action_head = Gr00tN1d7ActionHead(config)
    model = Gr00tN1d7Model(config, backbone, action_head)
    assert backbone.dynamic_image_grid is True
    assert backbone.tune_freeze_defaults == {
        "language_trainable": False,
        "visual_trainable": False,
        "top_language_layers": 0,
        "remaining_language_frozen": True,
        "rotary_buffers_trainable": False,
    }
    assert action_head.tune_freeze_defaults == {
        "action_head_trainable": True,
        "embodiment_projectors_trainable": True,
    }
    assert model.tensor_contract["actions"] == "[B,40,132]"
    assert model.tensor_contract["image_grid_thw"] == "int[N,3]"


def test_license_and_gated_cosmos_requirements_fail_closed_before_receipts() -> None:
    """许可冲突和 gated Cosmos 缺失分别在资产访问前失败。"""

    with pytest.raises(RuntimeError, match="license conflict"):
        Gr00tN1d7AssetBundle()
    with pytest.raises(RuntimeError, match="gated Cosmos"):
        Gr00tN1d7AssetBundle(checkpoint_license_resolved=True)


def test_local_checkpoint_inspection_maps_only_safetensors_without_readiness(
    tmp_path: Path,
) -> None:
    """本地索引可审计映射但不得声称 checkpoint 或 CUDA 已就绪。"""

    root = _checkpoint_root(tmp_path / "checkpoint")
    evidence = Gr00tN1d7CheckpointAdapter().inspect(root, config=_config())
    assert evidence.executable_ready is False
    assert evidence.key_mapping == {
        "model.backbone.language.weight": "backbone.language.weight",
        "model.action_head.diffusion.weight": "action_head.diffusion.weight",
    }
    assert evidence.shard_files == ("model-00001-of-00001.safetensors",)
    assert "checkpoint_tensor_shapes_not_validated" in evidence.blockers
    with pytest.raises(RuntimeError, match="tensor loading is blocked"):
        Gr00tN1d7CheckpointAdapter().load_local(root)


def test_checkpoint_rejects_pickle_and_unknown_namespaces(tmp_path: Path) -> None:
    """任意 pickle 和未知参数命名空间都不能进入检查证据。"""

    unsafe = _checkpoint_root(tmp_path / "unsafe", unsafe_pickle=True)
    with pytest.raises(ValueError, match="pickle"):
        Gr00tN1d7CheckpointAdapter().inspect(unsafe, config=_config())
    unknown = _checkpoint_root(tmp_path / "unknown")
    index_path = unknown / "model.safetensors.index.json"
    index_path.write_text(
        json.dumps(
            {
                "weight_map": {
                    "model.backbone.weight": "model-00001-of-00001.safetensors",
                    "model.optimizer.state": "model-00001-of-00001.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unsupported checkpoint namespace"):
        Gr00tN1d7CheckpointAdapter().inspect(unknown, config=_config())


def test_factory_has_shared_request_result_surface_but_no_false_success() -> None:
    """工厂满足共享可调用面且家族 resolver 在资产前关闭。"""

    factory = Gr00tN1d7ModelFactory()
    assert isinstance(factory, ModelFactory)
    signature = inspect.signature(factory.__call__)
    assert "request" in signature.parameters
    assert "ModelAssemblyResult" in str(signature.return_annotation)
    with pytest.raises((KeyError, ModelRuntimeSupportError)):
        resolve_model_assembly("gr00t_n1d7")
