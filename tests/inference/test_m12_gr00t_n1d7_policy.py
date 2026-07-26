"""M12 N1.7 label-free policy、官方 normalization 与激活门 oracle。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILY = ROOT / "autovla/models/families/gr00t_n1d7"


def _method_source(path: Path, class_name: str, method_name: str) -> str:
    """从源码 AST 返回指定方法, 保持测试 import-safe。"""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name
    )
    method = next(
        item
        for item in class_node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name
    )
    return ast.get_source_segment(source, method) or ""


def test_policy_requires_exact_processor_prediction_and_decode_receipts() -> None:
    """构造 policy 前必须逐项调用共享 M12 ``require_activation``。"""

    path = FAMILY / "policy.py"
    init_source = _method_source(path, "Gr00tN1d7Policy", "__init__")
    assert "RuntimeOperation.PROCESSOR: processor_key" in init_source
    assert "RuntimeOperation.PREDICTION: prediction_key" in init_source
    assert "RuntimeOperation.DECODE: decode_key" in init_source
    assert "key.operation is not operation" in init_source
    assert "require_activation(readiness, key)" in init_source


def test_policy_executes_label_free_prepare_predict_decode_boundary() -> None:
    """预测入口只消费观测, 不构造 actions/action_mask 训练标签。"""

    policy_source = _method_source(FAMILY / "policy.py", "Gr00tN1d7Policy", "predict")
    processor_source = _method_source(
        FAMILY / "processor.py",
        "Gr00tN1d7Processor",
        "prepare_observations",
    )
    assert "prepare_observations(" in policy_source
    assert "model.predict_actions(" in policy_source
    assert "processor.decode_actions(" in policy_source
    assert "actions=" not in processor_source
    assert "action_mask=" not in processor_source
    assert "physical_action_shapes=physical_shapes" in processor_source


def test_processor_consumes_official_modality_and_statistics_nesting() -> None:
    """normalization 必须按 embodiment/modality/joint-group 读取, 不接受扁平 mean/std。"""

    processor_path = FAMILY / "processor.py"
    group_source = _method_source(
        processor_path,
        "Gr00tN1d7Processor",
        "_statistics_group",
    )
    normalization_source = _method_source(
        processor_path,
        "Gr00tN1d7Processor",
        "_normalization_groups",
    )
    normalize_source = _method_source(
        processor_path,
        "Gr00tN1d7Processor",
        "_normalize_tensor",
    )
    decode_source = _method_source(
        processor_path,
        "Gr00tN1d7Processor",
        "_denormalize_tensor",
    )
    assert "self._statistics[embodiment]" in group_source
    assert 'embodiment_statistics["relative_action"]' in group_source
    assert "modality_statistics[group]" in group_source
    for field in ("mean", "std", "q01", "q99", "min", "max"):
        assert f'"{field}"' in normalization_source
    assert "self._modality_keys(embodiment, kind)" in normalization_source
    assert "active = upper != 0" in normalize_source
    assert "normalized = source.clone()" in normalize_source
    assert "self._sin_cos_keys(embodiment, kind)" in normalize_source
    assert "2.0 * (source[..., active] - lower[active])" in normalize_source
    assert "physical = source.clone()" in decode_source
    assert "(source.clamp(-1.0, 1.0) + 1.0) * 0.5" in decode_source


def test_local_only_safetensors_and_exact_cosmos_receipt_are_enforced() -> None:
    """工厂和资产包不得启用远端代码、网络 fallback 或 pickle 权重。"""

    factory = (FAMILY / "factory.py").read_text(encoding="utf-8")
    assets = (FAMILY / "assets.py").read_text(encoding="utf-8")
    checkpoint = (FAMILY / "checkpoint.py").read_text(encoding="utf-8")
    assert "config.cosmos_revision != request.asset_bundle.cosmos_revision" in factory
    assert factory.count("local_files_only=True") == 2
    assert factory.count("trust_remote_code=False") == 2
    assert factory.count('"diffusers"') >= 2
    assert "_UNSAFE_MODEL_SUFFIXES" in assets
    assert 'item.path.endswith(".safetensors")' in assets
    checkpoint_tree = ast.parse(checkpoint)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "torch"
        and node.func.attr == "load"
        for node in ast.walk(checkpoint_tree)
    )
    assert "_FORBIDDEN_SUFFIXES" in checkpoint
