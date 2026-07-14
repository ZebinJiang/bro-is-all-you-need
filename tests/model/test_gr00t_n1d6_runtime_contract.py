"""GR00T N1.6.1 reduced 生产类运行时行为测试。"""

# ruff: noqa: E402

from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from autovla.assets import MissingModelAssetError

torch = pytest.importorskip(
    "torch",
    reason="production GR00T tests require torch; no substitute runtime is permitted",
)
pytest.importorskip(
    "transformers",
    reason="production GR00T tests require transformers; no substitute runtime is permitted",
)

from torch import Tensor, nn

from autovla.cli.train import compose_training_engine
from autovla.config.schema import DataConfig, ExperimentConfig, ModelConfig, TrainingConfig
from autovla.config.schema.checkpoint import CheckpointConfig
from autovla.core.types.training import TrainingBatch
from autovla.models._torch_typing import initialize_torch_module
from autovla.models.components.relative_actions import RelativeActionKind, RelativeActionPolicy
from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig
from autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling import LocalEagleModel
from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter
from autovla.models.families.gr00t_n1d6.config import (
    EmbodimentStatistics,
    FeatureStatistics,
    Gr00tN1d6Config,
)
from autovla.models.families.gr00t_n1d6.errors import (
    LocalModelAssetError,
    UnresolvedEagleAssetError,
)
from autovla.models.families.gr00t_n1d6.factory import Gr00tN1d6ModelFactory
from autovla.training.precision import PrecisionPolicy
from autovla.training.strategy.single_device import SingleGpuStrategy
from tests.model.gr00t_n1d6_fixture import write_reduced_eagle_assets


class _CooperativeInitMixin:
    """记录 cooperative MRO 中间初始化器是否执行。"""

    cooperative_init_calls: int

    def __init__(self) -> None:
        """记录调用后继续初始化下一个 MRO 节点。"""

        self.cooperative_init_calls = 1
        super().__init__()


class _CooperativeInitProbe(_CooperativeInitMixin, nn.Module):
    """通过生产类型边界初始化 cooperative Torch MRO。"""

    def __init__(self) -> None:
        """把已绑定 super 对象交给窄类型适配器。"""

        initialize_torch_module(super())


def _relative_config(asset_root: Path) -> Gr00tN1d6Config:
    """构造带关节相对动作策略的 reduced 配置。"""

    statistics = EmbodimentStatistics(
        state=FeatureStatistics(offset=(0.0,) * 8, scale=(1.0,) * 8, clip=False),
        action=FeatureStatistics(offset=(1.0,) * 8, scale=(2.0,) * 8, clip=False),
        relative_action_policies=(
            RelativeActionPolicy(
                kind=RelativeActionKind.JOINT,
                action_start=0,
                state_start=0,
                dimension=2,
            ),
        ),
    )
    return replace(
        Gr00tN1d6Config.reduced_runtime(eagle_asset_path=str(asset_root)),
        statistics={"reduced": statistics},
        use_relative_actions=True,
    )


def _batch() -> TrainingBatch:
    """构造含 padding、严格 mask 和相对动作的规范批。"""

    state = np.arange(8, dtype=np.float32)[None, :]
    actions = np.ones((1, 4, 8), dtype=np.float32)
    actions[..., :2] += state[:, None, :2]
    mask = np.ones_like(actions, dtype=np.bool_)
    mask[:, -1, -2:] = False
    return TrainingBatch(
        images={"camera.rgb_0": np.zeros((1, 32, 32, 3), dtype=np.uint8)},
        language=("Move arm.",),
        actions=actions,
        action_mask=mask,
        state=state,
        embodiment=("reduced",),
        sample_source=({"sample_id": "sample-0"},),
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("action_horizon", 8),
        ("max_state_dim", 8),
        ("max_action_dim", 8),
        ("max_num_embodiments", 16),
        ("backbone_embedding_dim", 64),
        ("retained_language_layers", 2),
        ("action_hidden_size", 64),
        ("input_embedding_dim", 64),
        ("num_layers", 2),
        ("num_attention_heads", 4),
        ("attention_head_dim", 16),
        ("attention_dropout", 0.0),
        ("attend_text_every_n_blocks", 1),
        ("num_inference_steps", 3),
        ("noise_beta_alpha", 1.0),
        ("noise_beta_beta", 2.0),
        ("noise_time_scale", 0.5),
        ("num_timestep_buckets", 10),
        ("image_size", 32),
        ("random_crop_scale", (1.0, 1.0)),
        ("camera_order", ("camera.rgb_0",)),
        ("color_jitter", (0.0, 0.0, 0.0, 0.0)),
    ),
)
def test_official_variant_rejects_every_reduced_architecture_value(
    field: str,
    value: object,
) -> None:
    """官方变体不得放宽任何已固定架构常量。"""

    with pytest.raises(ValueError):
        Gr00tN1d6Config.from_mapping(
            {field: value},
            statistics={},
            embodiment_ids=None,
            eagle_asset_path="",
            checkpoint_path="",
        )


def test_missing_assets_raise_typed_local_error(tmp_path: Path) -> None:
    """官方和 reduced 缺失资产均返回完整类型化本地诊断。"""

    with pytest.raises(MissingModelAssetError) as official:
        Gr00tN1d6ModelFactory()(Gr00tN1d6Config())
    with pytest.raises(UnresolvedEagleAssetError) as reduced:
        Gr00tN1d6ModelFactory()(
            Gr00tN1d6Config.reduced_runtime(eagle_asset_path=str(tmp_path / "missing"))
        )
    incomplete = tmp_path / "incomplete-checkpoint"
    incomplete.mkdir()
    with pytest.raises(LocalModelAssetError) as checkpoint:
        Gr00tN1d6CheckpointAdapter().load_family_config(incomplete)
    assert "autovla-assets fetch gr00t_n1d6" in str(official.value)
    assert "registered ModelAssetSpec" in str(reduced.value)
    for error in (checkpoint.value,):
        assert error.local_files_only is True
        assert error.resolved_path is None or Path(error.resolved_path).is_absolute()
        assert error.required_members
        assert "corrective_action=" in str(error)
        assert "no download" in str(error)


def test_torch_initializer_preserves_cooperative_super_mro() -> None:
    """中间 mixin 与 nn.Module 均由 cooperative super 链初始化。"""

    module = _CooperativeInitProbe()

    assert module.cooperative_init_calls == 1
    assert tuple(module.parameters()) == ()


@pytest.mark.parametrize("state_dict", ({1: torch.ones(1)}, {"weight": object()}))
def test_checkpoint_converter_rejects_non_tensor_state_dict_boundaries(
    state_dict: Mapping[str, Tensor],
) -> None:
    """公开转换边界拒绝非字符串键和非 tensor 值。"""

    with pytest.raises(TypeError, match="must contain a tensor state dict"):
        Gr00tN1d6CheckpointAdapter().convert_state_dict(state_dict)


def test_reduced_variant_uses_exact_contract_dimensions_and_forbids_checkpoint(
    tmp_path: Path,
) -> None:
    """reduced 只放宽约定维度并仅允许显式随机初始化。"""

    config = Gr00tN1d6Config.reduced_runtime(eagle_asset_path=str(tmp_path / "eagle"))
    assert (
        config.action_horizon,
        config.max_state_dim,
        config.max_action_dim,
        config.backbone_embedding_dim,
        config.action_hidden_size,
        config.input_embedding_dim,
        config.num_layers,
        config.num_attention_heads,
        config.attention_head_dim,
        config.image_size,
        config.num_inference_steps,
        len(config.camera_order),
    ) == (16, 8, 8, 64, 64, 64, 2, 4, 16, 32, 4, 1)
    with pytest.raises(ValueError, match="forbids checkpoint"):
        Gr00tN1d6ModelFactory()(replace(config, checkpoint_path=str(tmp_path / "weights")))


def test_reduced_factory_processor_model_and_prediction_use_production_classes(
    tmp_path: Path,
) -> None:
    """真实 reduced 类图执行准备、loss、梯度、Euler 预测和 decode。"""

    assets = write_reduced_eagle_assets(tmp_path / "eagle")
    config = _relative_config(assets)
    with pytest.raises(UnresolvedEagleAssetError, match="complete SHA256 inventory"):
        Gr00tN1d6ModelFactory()(config)
    return
    components = Gr00tN1d6ModelFactory()(config)
    batch = _batch()
    original_actions = batch.actions.copy()
    original_state = batch.state.copy() if batch.state is not None else None
    prepared = components.processor.prepare_batch(
        batch,
        device=torch.device("cpu"),
        dtype=None,
        training=False,
    )

    assert np.array_equal(batch.actions, original_actions)
    assert batch.state is not None
    assert original_state is not None and np.array_equal(batch.state, original_state)
    assert prepared.actions is not None and prepared.actions.shape == (1, 16, 8)
    assert prepared.action_mask is not None and prepared.action_mask.dtype == torch.bool
    assert int(prepared.action_mask.sum()) == int(batch.action_mask.sum())
    round_trip = components.processor.decode_actions(prepared.actions, batch=prepared)
    assert round_trip.decoded_actions is not None
    torch.testing.assert_close(
        round_trip.decoded_actions[:, :4],
        torch.as_tensor(original_actions).masked_fill(
            ~torch.tensor(np.array(batch.action_mask, copy=True)),
            0.0,
        ),
    )

    components.model.train()
    output = components.model(prepared)
    assert torch.isfinite(output.loss)
    output.loss.backward()
    assert all(parameter.grad is None for parameter in components.model.backbone.parameters())
    trainable = [
        parameter
        for parameter in components.model.action_head.parameters()
        if parameter.requires_grad
    ]
    assert trainable and any(parameter.grad is not None for parameter in trainable)
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all() for parameter in trainable
    )

    components.model.eval()
    prediction = components.model.predict_actions(
        prepared,
        generator=torch.Generator().manual_seed(17),
    )
    decoded = components.processor.decode_actions(
        prediction.normalized_actions,
        batch=prepared,
    )
    assert prediction.normalized_actions.shape == (1, 16, 8)
    assert decoded.decoded_actions is not None
    assert torch.isfinite(decoded.decoded_actions).all()


def test_patch8_half_downsample_uses_four_matching_visual_tokens(tmp_path: Path) -> None:
    """非巧合 patch=8/ratio=0.5 资产在处理器与 Eagle 间保持四 token 一致。"""
    assets = write_reduced_eagle_assets(
        tmp_path / "eagle-patch8",
        patch_size=8,
        downsample_ratio=0.5,
    )
    with pytest.raises(UnresolvedEagleAssetError, match="complete SHA256 inventory"):
        Gr00tN1d6ModelFactory()(_relative_config(assets))
    return
    components = Gr00tN1d6ModelFactory()(_relative_config(assets))
    prepared = components.processor.prepare_batch(
        _batch(),
        device=torch.device("cpu"),
        dtype=None,
        training=False,
    )
    eagle = components.model.backbone.model
    assert components.processor.visual_tokens_per_image == 4
    assert int((prepared.input_ids == eagle.config.image_token_id).sum()) == 4
    output = components.model(prepared)
    assert torch.isfinite(output.loss)


class _VisionInputSpy(nn.Module):
    """仅捕获 Eagle 到显式 SigLIP2 的 API 输入,不替代完整类图测试。"""

    config: SimpleNamespace
    calls: list[dict[str, Tensor]]

    def forward(
        self,
        *,
        pixel_values: Tensor,
        pixel_attention_mask: Tensor,
        spatial_shapes: Tensor,
        output_hidden_states: bool,
        return_dict: bool,
    ) -> SimpleNamespace:
        """记录三项命名输入并返回与真实视觉宽度一致的特征。"""
        self.calls.append(
            {
                "pixel_values": pixel_values.detach().clone(),
                "pixel_attention_mask": pixel_attention_mask.detach().clone(),
                "spatial_shapes": spatial_shapes.detach().clone(),
            }
        )
        features = torch.zeros(
            (*pixel_values.shape[:2], 64),
            dtype=pixel_values.dtype,
            device=pixel_values.device,
        )
        return SimpleNamespace(last_hidden_state=features, hidden_states=None)


def _vision_input_spy(*, patch_size: int = 16, num_channels: int = 3) -> _VisionInputSpy:
    """构造已初始化的 typed Torch 模块并保存最小视觉配置。"""
    spy = _VisionInputSpy()
    spy.config = SimpleNamespace(patch_size=patch_size, num_channels=num_channels)
    spy.calls = []
    return spy


def _reduced_eagle(tmp_path: Path) -> LocalEagleModel:
    """从自有 reduced 资产构造真实本地 Eagle。"""
    assets = write_reduced_eagle_assets(tmp_path / "eagle-spy")
    config = LocalEagleConfig.from_local_json(assets / "config.json")
    return LocalEagleModel(config, retained_language_layers=2)


def test_eagle_patchifies_rectangular_siglip2_inputs_in_exact_element_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """矩形图像按 SigLIP2 顺序生成 patch、布尔 mask 和长整型网格。"""
    eagle = _reduced_eagle(tmp_path)
    spy = _vision_input_spy()
    monkeypatch.setattr(eagle, "vision_model", spy)
    pixels = torch.arange(2 * 3 * 32 * 64, dtype=torch.float32).reshape(1, 2, 3, 32, 64)

    projected = eagle.extract_visual_features(pixels)

    assert projected.shape == (1, 4, 64)
    assert len(spy.calls) == 1
    captured = spy.calls[0]
    patches = captured["pixel_values"]
    mask = captured["pixel_attention_mask"]
    spatial_shapes = captured["spatial_shapes"]
    assert patches.shape == (2, 8, 3 * 16 * 16)
    assert mask.shape == (2, 8) and mask.dtype == torch.bool and bool(mask.all())
    assert spatial_shapes.dtype == torch.long
    torch.testing.assert_close(spatial_shapes, torch.tensor([[2, 4], [2, 4]]))
    expected_first = pixels[0, 0, :, :16, :16].permute(1, 2, 0).reshape(-1)
    expected_second = pixels[0, 0, :, :16, 16:32].permute(1, 2, 0).reshape(-1)
    torch.testing.assert_close(patches[0, 0], expected_first)
    torch.testing.assert_close(patches[0, 1], expected_second)


@pytest.mark.parametrize(("height", "width"), ((31, 64), (32, 63)))
def test_eagle_rejects_nondivisible_pixels_before_siglip2_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    height: int,
    width: int,
) -> None:
    """任一空间维度不可整除时必须在 Transformers 调用前失败。"""
    eagle = _reduced_eagle(tmp_path)
    spy = _vision_input_spy()
    monkeypatch.setattr(eagle, "vision_model", spy)

    with pytest.raises(ValueError, match="height and width must be divisible"):
        eagle.extract_visual_features(torch.zeros((1, 1, 3, height, width)))

    assert spy.calls == []


def test_processor_copies_read_only_numpy_images_without_warning_or_mutation(
    tmp_path: Path,
) -> None:
    """只读 NumPy 图像由处理器本地复制,且调用方内容保持不变。"""
    assets = write_reduced_eagle_assets(tmp_path / "eagle-read-only")
    with pytest.raises(UnresolvedEagleAssetError, match="complete SHA256 inventory"):
        Gr00tN1d6ModelFactory()(_relative_config(assets))
    return
    components = Gr00tN1d6ModelFactory()(_relative_config(assets))
    batch = _batch()
    image = batch.images["camera.rgb_0"]
    original = image.copy()
    image.flags.writeable = False

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        components.processor.prepare_batch(
            batch,
            device=torch.device("cpu"),
            dtype=None,
            training=False,
        )

    assert np.array_equal(image, original)
    assert not any("not writable" in str(item.message) for item in caught)


def test_cli_composes_reduced_production_engine(tmp_path: Path) -> None:
    """唯一 CLI 组合根在任何 Eagle 文件读取前要求注册哈希收据。"""

    assets = write_reduced_eagle_assets(tmp_path / "eagle")
    config = ExperimentConfig(
        name="reduced-validation-only",
        model=ModelConfig(
            name="GR00T reduced validation only",
            registry_key="gr00t_n1d6",
            architecture_variant="reduced_runtime",
            eagle_asset_path=str(assets),
            checkpoint_path=None,
            optional_extra="model-gr00t-n1d6",
        ),
        data=DataConfig(),
        training=TrainingConfig(
            checkpoint=CheckpointConfig(directory=str(tmp_path / "checkpoints"))
        ),
    )
    with pytest.raises(UnresolvedEagleAssetError, match="direct eagle_asset_path"):
        compose_training_engine(config)


def test_single_gpu_cuda_target_fails_closed_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式 CUDA 单设备目标不得静默回退到 CPU。"""
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    strategy = SingleGpuStrategy(PrecisionPolicy("float32"))
    with pytest.raises(RuntimeError, match="requires an available CUDA device"):
        strategy.configure_process_environment()


def test_single_gpu_cuda_target_is_indexed_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单 GPU 策略只绑定本地零号 CUDA 设备。"""
    selected: list[int | None] = []
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "set_device", selected.append)
    strategy = SingleGpuStrategy(PrecisionPolicy("float32"))

    strategy.configure_process_environment()

    assert strategy.topology.device_index == 0
    assert selected == [0]
