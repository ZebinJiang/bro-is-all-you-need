"""M13 Pi0.5 官方源码对齐的单一无权重回归。"""

from __future__ import annotations

import ast
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILY = ROOT / "autovla/models/families/pi0_5"
FIXTURE = ROOT / "tests/model/fixtures/pi0_5_synthetic_contract.json"


class Pi05OfficialSourceAlignmentTest(unittest.TestCase):
    """验证命名空间、固定数值合同和依赖隔离。"""

    def test_official_source_alignment_contract(self) -> None:
        """一个回归覆盖本 wave 接受的图与命名空间缺陷。"""

        config = (FAMILY / "config.py").read_text(encoding="utf-8")
        modeling = (FAMILY / "_openpi_compat/modeling.py").read_text(encoding="utf-8")
        backbone = (FAMILY / "backbone.py").read_text(encoding="utf-8")
        action = (FAMILY / "action_head.py").read_text(encoding="utf-8")
        model = (FAMILY / "model.py").read_text(encoding="utf-8")
        conversion = (FAMILY / "conversion.py").read_text(encoding="utf-8")
        factory = (FAMILY / "factory.py").read_text(encoding="utf-8")
        family = (FAMILY / "family.py").read_text(encoding="utf-8")
        source_map = (FAMILY / "source_map.py").read_text(encoding="utf-8")
        source_map_document = (FAMILY / "SOURCE_MAP.md").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

        self.assertIn("prefix_head_dim: int = 256", config)
        self.assertIn("expert_head_dim: int = 256", config)
        self.assertIn("self.q_proj = nn.Linear", modeling)
        self.assertIn("self.k_proj = nn.Linear", modeling)
        self.assertIn("self.v_proj = nn.Linear", modeling)
        self.assertIn("self.multi_modal_projector", backbone)
        self.assertIn("math.sqrt(self.config.prefix_hidden_size)", backbone)
        self.assertIn("hidden_states=tuple(layer_cache)", backbone)
        self.assertIn("self.action_head = action_head", model)
        self.assertNotIn("self.action_expert = action_expert", model)
        self.assertIn('_VISION_PREFIX = "backbone.vision_tower.vision_model"', conversion)
        self.assertIn('_LANGUAGE_PREFIX = "backbone.language_model"', conversion)
        self.assertIn('_EXPERT_PREFIX = "action_head.gemma_expert.model"', conversion)
        self.assertIn('f"action_head.{name}.weight"', conversion)
        self.assertIn(
            'destination_precisions: tuple[str, ...] = ("float32", "float16")',
            conversion,
        )
        self.assertIn("target_state_metadata", conversion)
        self.assertIn("expected_source_shape", conversion)
        self.assertIn("expected_destination_shape", conversion)
        self.assertIn("AuthorizedModelAsset", factory)
        self.assertIn("PI05_LIFECYCLE_AUTHORIZATION_RECEIPTS_REQUIRED", factory)
        self.assertIn("PI05_FAMILY_AUTHORIZATION_POLICIES_UNREGISTERED", factory)
        prepare_source = ast.get_source_segment(
            factory,
            next(
                node
                for node in ast.walk(ast.parse(factory))
                if isinstance(node, ast.FunctionDef) and node.name == "prepare_training_assembly"
            ),
        )
        assert prepare_source is not None
        self.assertNotIn("resolver.resolve(", prepare_source)
        self.assertIn(
            "verified_apache_2_0_mixed_adapted_and_clean_reimplementation",
            family,
        )
        self.assertIn(
            "mixed_material_adaptation_and_clean_reimplementation",
            source_map,
        )
        for upstream in (
            "src/openpi/models/model.py",
            "src/openpi/models_pytorch/preprocessing_pytorch.py",
            "src/openpi/shared/image_tools.py",
        ):
            self.assertIn(upstream, source_map_document)
        self.assertIn("Both Pi0.5 locks were regenerated", notices)
        self.assertIn(
            "b1338785b2de1c52c318f369987248ea7a0708cf83ed81e64a8bd5b86221fc4e",
            notices,
        )
        self.assertIn(
            "e8bb0ced26973bd9a4858133ca7f24426966e4358648e3dbe510e9c23090dbcb",
            notices,
        )

        action_tree = ast.parse(action)
        time_embedding = next(
            node
            for node in ast.walk(action_tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_time_embedding"
        )
        time_source = ast.get_source_segment(action, time_embedding)
        assert time_source is not None
        self.assertIn("4e-3", time_source)
        self.assertIn("4.0", time_source)
        self.assertIn("2.0 * torch.pi", time_source)
        self.assertEqual(time_source.count("functional.silu"), 2)
        periods = [4e-3 * (4.0 / 4e-3) ** (index / 511) for index in range(512)]
        self.assertTrue(math.isclose(periods[0], 4e-3))
        self.assertTrue(math.isclose(periods[-1], 4.0))
        embedding = [
            function(2.0 * math.pi * 0.5 / period)
            for function in (math.sin, math.cos)
            for period in periods
        ]
        self.assertEqual(len(embedding), 1024)
        self.assertTrue(all(math.isfinite(value) for value in embedding))

        runtime_modules = (
            "config.py",
            "processor.py",
            "_openpi_compat/modeling.py",
            "backbone.py",
            "action_head.py",
            "model.py",
            "factory.py",
            "family.py",
        )
        prohibited = {"jax", "flax", "orbax"}
        for relative in runtime_modules:
            tree = ast.parse((FAMILY / relative).read_text(encoding="utf-8"))
            imported = {
                alias.name.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imported.update(
                node.module.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
            self.assertTrue(prohibited.isdisjoint(imported), relative)

        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIs(fixture["synthetic"], True)
        self.assertEqual(fixture["normalization_semantics"], "none_model_space_values_only")
        self.assertEqual(fixture["expected_state_dict_tensor_count"], 811)
        self.assertEqual(
            fixture["conversion_plan_identity"],
            "edcf1d9b134e46f04e329c20418574b796c359d5964ef168b7dcf0f73e20df8e",
        )
        self.assertEqual(
            fixture["shape"],
            {
                "batch": 2,
                "cameras": 3,
                "image_height": 224,
                "image_width": 224,
                "prompt_tokens": 200,
                "state_dimension": 32,
                "action_horizon": 50,
                "action_dimension": 32,
            },
        )
        self.assertIn("not normalization evidence", fixture["prohibitions"])


if __name__ == "__main__":
    unittest.main()
