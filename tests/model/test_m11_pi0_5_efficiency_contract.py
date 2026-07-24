"""M11 Pi0.5 效率与静态质量回归契约。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELING = ROOT / "autovla/models/families/pi0_5/_openpi_compat/modeling.py"
PROCESSOR = ROOT / "autovla/models/families/pi0_5/processor.py"
RUNTIME_PROFILE_TEST = ROOT / "tests/config/test_m11_runtime_profiles.py"
PHYSICAL_BINDING_TEST = ROOT / "tests/data/test_m11_physical_batch_binding.py"


def _parse(path: Path) -> tuple[str, ast.Module]:
    """读取并解析 Python 文件,不导入 Torch 依赖模块。"""

    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source)


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """按名称返回唯一函数节点。"""

    matches = [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]


def _call_name(call: ast.Call) -> str:
    """把调用目标压平为便于静态断言的点分名称。"""

    parts: list[str] = []
    current = call.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def test_attention_uses_native_sdpa_gqa_without_physical_kv_expansion() -> None:
    """注意力必须由 SDPA 原生处理 GQA,不能复制 K/V 头。"""

    source, tree = _parse(MODELING)
    assert "repeat_interleave" not in source
    assert "_expand_kv" not in source
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    sdpa_calls = [
        call for call in calls if _call_name(call).endswith("scaled_dot_product_attention")
    ]
    assert len(sdpa_calls) == 1
    enable_gqa = next(
        (keyword.value for keyword in sdpa_calls[0].keywords if keyword.arg == "enable_gqa"),
        None,
    )
    assert isinstance(enable_gqa, ast.Constant) and enable_gqa.value is True
    assert "num_heads % num_kv_heads" in source


def test_prefix_key_rotation_allocates_no_dummy_query() -> None:
    """两条前缀 K/V 路径必须直接旋转 key,不能分配虚拟 query。"""

    source, tree = _parse(MODELING)
    assert "dummy" not in source.lower()
    assert source.count("key = _rotate_key(key, positions, theta=self.rope_theta)") == 2
    for name in ("project_kv", "prefix_kv"):
        function = _function(tree, name)
        calls = [_call_name(node) for node in ast.walk(function) if isinstance(node, ast.Call)]
        assert "torch.zeros" not in calls


def test_processor_keeps_scalar_decisions_on_host_without_unconditional_copy() -> None:
    """图像范围和 jitter 必须在上传前于主机决定,且不得强制 NumPy 复制。"""

    _, tree = _parse(PROCESSOR)
    function = _function(tree, "_prepare_image")
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    call_names = [_call_name(call) for call in calls]
    assert "np.array" not in call_names
    assert "float" not in call_names
    assert not any(name.endswith(".item") for name in call_names)
    assert "np.max" in call_names
    assert "np.greater" in call_names
    tensor_transfer = next(call for call in calls if _call_name(call) == "torch.as_tensor")
    host_decisions = [call for call in calls if _call_name(call) in {"np.max", "torch.empty"}]
    assert host_decisions and all(call.lineno < tensor_transfer.lineno for call in host_decisions)
    cpu_empty = next(call for call in calls if _call_name(call) == "torch.empty")
    device = next(keyword.value for keyword in cpu_empty.keywords if keyword.arg == "device")
    assert isinstance(device, ast.Constant) and device.value == "cpu"


def test_protocol_method_has_ellipsis_body() -> None:
    """Tokenizer Protocol 方法必须有合法省略号方法体。"""

    _, tree = _parse(PROCESSOR)
    tokenizer = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_Tokenizer"
    )
    encode = next(
        node
        for node in tokenizer.body
        if isinstance(node, ast.FunctionDef) and node.name == "encode"
    )
    assert any(
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
        for statement in encode.body
    )


def test_machine_headers_preserve_source_truth_without_stale_wave_wording() -> None:
    """机器头必须保留来源,并如实记录尚未完成的运行证据。"""

    source, _ = _parse(MODELING)
    assert "# SPDX-License-Identifier: Apache-2.0" in source
    assert "# Source: https://github.com/Physical-Intelligence/openpi/tree/" in source
    assert "exact pin receipt awaits Wave 4" not in source
    assert "family-local clean PyTorch compatibility" not in source
    assert "architecture contract only" not in source
    assert "已记录 OpenPI Apache-2.0 源码与精确 pin 证据" in source
    assert "数值一致性与官方 checkpoint 运行仍未验证" in source


def test_candidate_flagged_inner_helpers_have_chinese_docstrings() -> None:
    """候选验证点名的三个内层 helper 必须补齐中文说明。"""

    _, runtime_tree = _parse(RUNTIME_PROFILE_TEST)
    _, binding_tree = _parse(PHYSICAL_BINDING_TEST)
    helpers = (
        _function(runtime_tree, "forbidden_runner"),
        _function(runtime_tree, "fake_runner"),
        _function(binding_tree, "project"),
    )
    for helper in helpers:
        docstring = ast.get_docstring(helper)
        assert docstring is not None
        assert any("\u4e00" <= character <= "\u9fff" for character in docstring)
