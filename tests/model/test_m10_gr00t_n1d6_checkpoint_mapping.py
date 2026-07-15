"""GR00T N1.6 官方 checkpoint 到本地 action-head 的聚焦映射测试。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest


def _official_attention_group(
    torch: object,
    *,
    block: int,
    width: int,
    source_width: int,
) -> Mapping[str, object]:
    """构造一个官方 diffusers 风格的 Q/K/V 合成参数组。"""

    zeros = torch.zeros
    prefix = f"action_head.model.transformer_blocks.{block}.attn1"
    return {
        f"{prefix}.to_q.weight": zeros(width, width),
        f"{prefix}.to_k.weight": zeros(width, source_width),
        f"{prefix}.to_v.weight": zeros(width, source_width),
        f"{prefix}.to_q.bias": zeros(width),
        f"{prefix}.to_k.bias": zeros(width),
        f"{prefix}.to_v.bias": zeros(width),
    }


def test_official_representative_names_and_cross_attention_qkv_map_exactly() -> None:
    """交叉注意力保留分立权重,同时把三个 bias 合成 packed bias。"""

    torch = pytest.importorskip("torch")
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    state = dict(_official_attention_group(torch, block=0, width=4, source_width=6))
    state.update(
        {
            "action_head.model.timestep_encoder.timestep_embedder.linear_1.weight": torch.zeros(
                4, 2
            ),
            "action_head.model.transformer_blocks.0.attn1.to_out.0.weight": torch.zeros(4, 4),
            "action_head.model.transformer_blocks.0.ff.net.0.proj.weight": torch.zeros(8, 4),
            "action_head.model.transformer_blocks.0.ff.net.2.weight": torch.zeros(4, 4),
        }
    )
    converted = Gr00tN1d6CheckpointAdapter().convert_state_dict(state)

    assert converted["action_head.model.transformer_blocks.0.attn1.q_proj_weight"].shape == (
        4,
        4,
    )
    assert converted["action_head.model.transformer_blocks.0.attn1.k_proj_weight"].shape == (
        4,
        6,
    )
    assert converted["action_head.model.transformer_blocks.0.attn1.in_proj_bias"].shape == (12,)
    assert "action_head.model.time_encoder.linear1.weight" in converted
    assert "action_head.model.transformer_blocks.0.attn1.out_proj.weight" in converted
    assert "action_head.model.transformer_blocks.0.ff.proj_in.weight" in converted
    assert "action_head.model.transformer_blocks.0.ff.proj_out.weight" in converted


def test_official_self_attention_qkv_weights_and_biases_are_packed_in_qkv_order() -> None:
    """自注意力按 Q、K、V 顺序生成 PyTorch packed in_proj 参数。"""

    torch = pytest.importorskip("torch")
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    state = dict(_official_attention_group(torch, block=1, width=2, source_width=2))
    for index, name in enumerate("qkv", start=1):
        state[f"action_head.model.transformer_blocks.1.attn1.to_{name}.weight"].fill_(index)
    converted = Gr00tN1d6CheckpointAdapter().convert_state_dict(state)

    packed = converted["action_head.model.transformer_blocks.1.attn1.in_proj_weight"]
    assert packed.shape == (6, 2)
    assert torch.equal(packed[:, 0], torch.tensor([1, 1, 2, 2, 3, 3]))
    assert converted["action_head.model.transformer_blocks.1.attn1.in_proj_bias"].shape == (6,)


def test_mapping_rejects_collisions_and_incomplete_projection_groups() -> None:
    """本地目标碰撞和不完整 Q/K/V 组都必须 fail closed。"""

    torch = pytest.importorskip("torch")
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    adapter = Gr00tN1d6CheckpointAdapter()
    with pytest.raises(ValueError, match="collision"):
        adapter.convert_state_dict(
            {
                "action_head.model.transformer_blocks.0.attn1.to_out.0.weight": torch.zeros(1),
                "action_head.model.transformer_blocks.0.attn1.out_proj.weight": torch.zeros(1),
            }
        )
    with pytest.raises(ValueError, match="incomplete"):
        adapter.convert_state_dict(
            {"action_head.model.transformer_blocks.0.attn1.to_q.weight": torch.zeros(2, 2)}
        )


def test_official_position_embedding_shape_matches_pinned_architecture() -> None:
    """官方 1024 长度位置表必须成为本地严格期望形状。"""

    from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config

    official = Gr00tN1d6Config()
    assert official.max_sequence_length == 1024
    assert official.action_horizon == 50
    source = Path("autovla/models/families/gr00t_n1d6/action_head.py").read_text(encoding="utf-8")
    assert "config.max_sequence_length" in source


def test_strict_load_reports_missing_unexpected_and_shape_mismatch_before_write() -> None:
    """严格加载在任何参数写入前同时报告三类不兼容。"""

    torch = pytest.importorskip("torch")
    from autovla.models.families.gr00t_n1d6.checkpoint import Gr00tN1d6CheckpointAdapter

    class SyntheticAdapter(Gr00tN1d6CheckpointAdapter):
        """仅为测试提供内存 state dict,不读取真实 checkpoint。"""

        def _iter_state_dicts(self, report: object, *, device: object):
            """返回一个含 unexpected 和错误 shape 的合成 shard。"""
            del report, device
            yield {
                "weight": torch.zeros(3),
                "unexpected": torch.zeros(1),
            }

    root = pytest.MonkeyPatch()
    adapter = SyntheticAdapter()

    class LayoutOnlyModel:
        """提供参数布局并拒绝任何实际写入。"""

        def state_dict(self):
            """返回严格审计所需的两个合成参数。"""
            return {"weight": torch.zeros(2, 2), "bias": torch.zeros(2)}

        def load_state_dict(self, state: object, *, strict: bool):
            """严格审计失败时不得进入写入阶段。"""
            del state, strict
            raise AssertionError("strict audit must fail before parameter writes")

    model = LayoutOnlyModel()
    compatibility = type(
        "Compatibility",
        (),
        {
            "compatible": True,
            "root": ".",
            "weight_format": "safetensors",
            "weight_files": (),
            "missing_files": (),
        },
    )()
    root.setattr(adapter, "_inspect_source", lambda source: compatibility)
    root.setattr(
        adapter,
        "_checkpoint_source",
        lambda path: type("Source", (), {"resolved_asset": None})(),
    )
    try:
        with pytest.raises(ValueError) as error:
            adapter.load_local(model, ".", strictness="strict")
    finally:
        root.undo()
    message = str(error.value)
    assert "missing=['bias']" in message
    assert "unexpected=['unexpected']" in message
    assert "shapes=['weight']" in message
