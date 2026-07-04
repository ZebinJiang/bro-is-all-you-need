"""模型族 registry 与 runner 集成测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from autovla.training.runner import DryRunConfig, run_training_dry_run


def test_runner_should_use_gr00t_registry_adapter_without_heavy_imports(tmp_path: Path) -> None:
    """验证 runner 通过 registry 使用 GR00T dry-run adapter 且不导入重型运行时。"""
    heavy_roots = {"torch", "transformers", "gr00t", "jax", "flax", "wandb", "huggingface_hub"}
    before = set(sys.modules)

    result = run_training_dry_run(
        DryRunConfig(
            family_key="gr00t-n1d6",
            fixture="tiny",
            output_dir=tmp_path,
            run_id="model-integration",
            seed=5,
            steps=1,
        )
    )

    loaded = set(sys.modules) - before
    assert result.model_input.metadata["family_key"] == "gr00t-n1d6"
    for root in heavy_roots:
        assert root not in loaded
        assert not any(module.startswith(f"{root}.") for module in loaded)
