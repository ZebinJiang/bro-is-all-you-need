"""Pi0.5 三操作 promotion 激活边界的 no-Torch 源码测试。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "autovla/models/families/pi0_5/policy.py"


def _method_source(class_name: str, method_name: str) -> str:
    """返回指定方法的原始源码而不导入 Torch family。"""

    source = POLICY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    return ast.get_source_segment(source, method) or ""


def test_pi05_policy_requires_exact_processor_prediction_decode_promotions() -> None:
    """prediction-only receipt 不得构造 Pi0.5 production policy。"""

    source = _method_source("Pi05PolicyBundle", "__post_init__")
    assert "RuntimeOperation.PROCESSOR: self.processor_key" in source
    assert "RuntimeOperation.PREDICTION: self.prediction_key" in source
    assert "RuntimeOperation.DECODE: self.decode_key" in source
    assert "promotion = self.promotions.get(operation)" in source
    assert "require_activation(" in source
