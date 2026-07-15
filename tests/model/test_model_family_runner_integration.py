"""生产模型族 registry 的兼容别名与轻量导入测试。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from autovla.models.registry import get_model_family_spec


def test_gr00t_compatibility_alias_preserves_definition_identity() -> None:
    """旧连字符键警告并返回同一规范定义对象。"""

    canonical = get_model_family_spec("gr00t_n1d6")
    with pytest.warns(DeprecationWarning):
        alias = get_model_family_spec("gr00t-n1d6")
    assert alias is canonical


def test_fresh_registry_process_avoids_heavy_runtime_imports() -> None:
    """新进程检查 registry 后仍不加载任何模型运行时。"""

    script = """
import sys
from autovla.models.registry import get_model_family_spec
assert get_model_family_spec('gr00t_n1d6').family_key == 'gr00t_n1d6'
blocked = {'torch', 'transformers', 'jax', 'flax'}
loaded = {name.split('.', 1)[0] for name in sys.modules}
assert not blocked & loaded, blocked & loaded
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
