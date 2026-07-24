"""M12 N1.7 官方源码架构、配置和 checkpoint namespace oracle。"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config

ROOT = Path(__file__).resolve().parents[2]
FAMILY = ROOT / "autovla/models/families/gr00t_n1d7"
ORACLE = ROOT / "tests/model/oracles/gr00t_n1d7/official_action_head_state_dict.txt"
COSMOS_REVISION = "1234567890abcdef1234567890abcdef12345678"


def _nested_artifact() -> dict[str, object]:
    """返回 checkpoint 保存的嵌套 action/VL 配置结构。"""

    return {
        "model_config": {
            "model_name": "nvidia/Cosmos-Reason2-2B",
            "model_revision": COSMOS_REVISION,
            "select_layer": 16,
            "load_bf16": True,
            "state_dropout_prob": 0.2,
            "max_state_dim": 132,
            "max_action_dim": 132,
            "action_horizon": 40,
            "max_num_embodiments": 32,
            "backbone_embedding_dim": 2048,
            "hidden_size": 1024,
            "input_embedding_dim": 1536,
            "state_history_length": 1,
            "max_seq_len": 1024,
            "attend_text_every_n_blocks": 2,
            "diffusion_model_cfg": {
                "num_layers": 32,
                "num_attention_heads": 32,
                "attention_head_dim": 48,
                "output_dim": 1024,
                "dropout": 0.2,
                "attention_bias": True,
                "final_dropout": True,
                "norm_eps": 1e-5,
                "positional_embeddings": None,
                "max_num_positional_embeddings": 512,
            },
            "vl_self_attention_cfg": {
                "num_layers": 4,
                "num_attention_heads": 32,
                "attention_head_dim": 64,
                "dropout": 0.1,
                "attention_bias": True,
                "final_dropout": True,
                "positional_embeddings": "sinusoidal",
                "max_num_positional_embeddings": 512,
            },
        }
    }


def _class_source(path: Path, class_name: str) -> str:
    """从 import-safe AST 返回指定类源码。"""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name
    )
    return ast.get_source_segment(source, node) or ""


def test_nested_artifact_closes_exact_official_dimensions_and_cosmos_revision() -> None:
    """嵌套 artifact 必须驱动 1536/1024/2048 参数图和精确 Cosmos pin。"""

    config = Gr00tN1d7Config.from_artifact_mapping(
        _nested_artifact(),
        cosmos_revision=COSMOS_REVISION,
    )
    assert (
        config.diffusion_layers,
        config.action_attention_heads,
        config.action_attention_head_dim,
        config.action_model_width,
        config.diffusion_output_dim,
    ) == (32, 32, 48, 1536, 1024)
    assert (
        config.vl_self_attention_layers,
        config.vl_attention_heads,
        config.vl_attention_head_dim,
        config.backbone_hidden_size,
    ) == (4, 32, 64, 2048)
    assert config.cosmos_revision == COSMOS_REVISION
    drifted = _nested_artifact()
    model_config = drifted["model_config"]
    assert isinstance(model_config, dict)
    model_config["model_revision"] = "a" * 40
    with pytest.raises(ValueError, match="Cosmos revision"):
        Gr00tN1d7Config.from_artifact_mapping(
            drifted,
            cosmos_revision=COSMOS_REVISION,
        )


def test_official_embodiment_aliases_share_only_declared_projectors() -> None:
    """同一物理 embodiment 别名复用固定 projector, 其他组保持分离。"""

    config = Gr00tN1d7Config.from_artifact_mapping(
        _nested_artifact(),
        cosmos_revision=COSMOS_REVISION,
    )
    assert {
        config.embodiment_ids[name]
        for name in ("new_embodiment", "robocasa_panda_omron", "robocasa_gr1_tabletop")
    } == {10}
    assert {
        config.embodiment_ids[name]
        for name in (
            "real_r1_pro_sharpa_relative_eef",
            "real_r1_pro_sharpa_relative_eef_human",
            "real_r1_pro_sharpa_relative_eef_maxinsights",
            "real_r1_pro_sharpa_relative_eef_mecka",
        )
    } == {26}
    assert config.embodiment_ids["simpler_env_google"] != config.embodiment_ids["libero_sim"]


def test_adapted_modules_preserve_full_upstream_attribution() -> None:
    """每个复制适配文件保留 SPDX、版权、revision、path 和 blob。"""

    expected = {
        "_nvidia/dit.py": (
            "gr00t/model/modules/dit.py",
            "4bb9994d3c89a738a830c5af927b1cd24d2854a5",
        ),
        "_nvidia/embodiment.py": (
            "gr00t/model/modules/embodiment_conditioned_mlp.py",
            "504785d57cc33a87613dd775cc415cc88574c2ee",
        ),
        "action_head.py": (
            "gr00t/model/gr00t_n1d7/gr00t_n1d7.py",
            "346b597a4b9a115a9a5b1053621f47f07833da09",
        ),
    }
    for relative, (source_path, blob) in expected.items():
        text = (FAMILY / relative).read_text(encoding="utf-8")
        assert (
            "# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES." in text
        )
        assert "# SPDX-License-Identifier: Apache-2.0" in text
        assert "9c7e746b2cd37a810070a98ef41d290a07e806c2" in text
        assert source_path in text
        assert blob in text


def test_attention_and_feed_forward_use_exact_pinned_diffusers_primitives() -> None:
    """Q/K/V/out 与 FF 参数不得合并、改名或成为未使用占位。"""

    dit_path = FAMILY / "_nvidia/dit.py"
    block = _class_source(dit_path, "BasicTransformerBlock")
    timestep = _class_source(dit_path, "TimestepEncoder")
    text = dit_path.read_text(encoding="utf-8")
    assert "Source dependency: diffusers==0.35.1" in text
    assert "from diffusers.models.attention import Attention, FeedForward" in text
    assert "nn.MultiheadAttention" not in text
    assert "self.attn1 = Attention(" in block
    assert "self.ff = FeedForward(" in block
    assert "self.final_dropout = nn.Dropout(dropout)" in block
    assert "attended = self.final_dropout(attended)" in block
    assert "self.pos_embed = (" in block and "self.pos_embed(normalized)" in block
    assert "self.time_proj =" in timestep and "self.time_proj(" in timestep
    assert "self.timestep_embedder =" in timestep and "self.timestep_embedder(" in timestep


def test_alternate_vldit_preserves_exact_interleaving_masks_and_output_adanorm() -> None:
    """偶数 cross block 按 text/text/image/image 周期, 奇数 block 只做 self-attn。"""

    source = _class_source(FAMILY / "_nvidia/dit.py", "AlternateVLDiT")
    assert "image_attention_mask = image_mask & backbone_attention_mask" in source
    assert "non_image_attention_mask = (~image_mask) & backbone_attention_mask" in source
    assert "if index % 2:" in source
    assert "index % (2 * self.attend_text_every_n_blocks) == 0" in source
    assert "self.proj_out_1(F.silu(condition)).chunk(2, dim=1)" in source
    assert "normalized * (1.0 + scale[:, None]) + shift[:, None]" in source
    assert "self.proj_out_2(normalized)" in source


def test_checkpoint_namespace_oracle_covers_all_official_parameter_families() -> None:
    """oracle 固定官方 state/action/DiT/VL 参数前缀, 而非仅检查类名。"""

    keys = tuple(line for line in ORACLE.read_text(encoding="utf-8").splitlines() if line.strip())
    assert len(keys) == len(set(keys)) >= 45
    required = (
        "action_head.model.timestep_encoder.timestep_embedder.linear_1.weight",
        "action_head.model.transformer_blocks.0.attn1.to_q.weight",
        "action_head.model.transformer_blocks.0.ff.net.0.proj.weight",
        "action_head.state_encoder.layer1.W",
        "action_head.action_encoder.W2.W",
        "action_head.action_decoder.layer2.W",
        "action_head.vl_self_attention.transformer_blocks.0.attn1.to_out.0.weight",
        "action_head.position_embedding.weight",
    )
    assert all(item in keys for item in required)
    assert not any("in_proj_weight" in item or "projectors." in item for item in keys)


def test_runtime_bundle_requires_caller_supplied_runtime_identity_and_asset_evidence() -> None:
    """family 不得猜测运行 profile 或复用隐藏常量。"""

    from autovla.models.families.gr00t_n1d7.factory import Gr00tN1d7ModelFactory

    signature = inspect.signature(Gr00tN1d7ModelFactory.runtime_bundle)
    assert tuple(signature.parameters) == (
        "result",
        "runtime_profile_identity",
        "asset_evidence",
    )
    assert signature.parameters["runtime_profile_identity"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["runtime_profile_identity"].default is inspect.Parameter.empty
    assert signature.parameters["asset_evidence"].default is inspect.Parameter.empty
