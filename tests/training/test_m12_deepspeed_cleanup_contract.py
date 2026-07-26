"""M12 ZeRO 初始化首异常与可重试 ownership 的无 Torch 测试。"""

from __future__ import annotations

import ast
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType

import pytest

DEEPSPEED_SOURCE = Path("autovla/training/strategy/deepspeed.py")
_EXTRACTED_NAMES = {
    "_ZeroInitializationTransaction",
    "_append_cleanup_note",
    "_destroy_initialization_process_group",
    "_retry_owned_initialization_process_group",
    "_ZeroInitializationContext",
}


class _FakeDistributed:
    """注入可控 process-group 销毁失败。"""

    def __init__(self, *, fail_destroy: bool) -> None:
        """保存失败开关和调用计数。"""

        self.initialized = True
        self.fail_destroy = fail_destroy
        self.destroy_calls = 0

    def is_initialized(self) -> bool:
        """返回模拟进程组状态。"""

        return self.initialized

    def destroy_process_group(self) -> None:
        """按需失败,否则把组标为已销毁。"""

        self.destroy_calls += 1
        if self.fail_destroy:
            raise RuntimeError("destroy failed")
        self.initialized = False


class _InjectedContext(AbstractContextManager[None]):
    """注入 enter 或 exit 失败的官方上下文替身。"""

    def __init__(
        self, *, enter_error: BaseException | None = None, exit_error: BaseException | None = None
    ) -> None:
        """保存失败注入。"""

        self.enter_error = enter_error
        self.exit_error = exit_error

    def __enter__(self) -> None:
        """按需在 enter 抛错。"""

        if self.enter_error is not None:
            raise self.enter_error
        return None

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """按需在 exit 抛错。"""

        del error_type, error, traceback
        if self.exit_error is not None:
            raise self.exit_error
        return False


def _load_cleanup_contract(dist: _FakeDistributed) -> dict[str, object]:
    """只编译实际策略中的无 Torch cleanup 定义。"""

    tree = ast.parse(DEEPSPEED_SOURCE.read_text(encoding="utf-8"))
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in _EXTRACTED_NAMES
    ]
    module = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__",
                names=[ast.alias(name="annotations")],
                level=0,
            ),
            *selected,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {
        "AbstractContextManager": AbstractContextManager,
        "TracebackType": TracebackType,
        "dist": dist,
    }
    exec(compile(module, str(DEEPSPEED_SOURCE), "exec"), namespace)
    return namespace


def test_model_error_survives_exit_and_destroy_failures_then_cleanup_retries() -> None:
    """模型主异常保持 primary,exit/destroy 只记 note,ownership 可重试。"""

    dist = _FakeDistributed(fail_destroy=True)
    contract = _load_cleanup_contract(dist)
    transaction = contract["_ZeroInitializationTransaction"](required=True)
    transaction.issue()
    context = contract["_ZeroInitializationContext"](
        transaction,
        _InjectedContext(exit_error=LookupError("exit failed")),
        process_group_preexisting=False,
    )

    with pytest.raises(ValueError, match="model construction failed") as failure:
        with context:
            raise ValueError("model construction failed")

    assert transaction.owns_process_group is True
    assert dist.destroy_calls == 1
    notes = getattr(
        failure.value,
        "__notes__",
        getattr(failure.value, "_autovla_cleanup_notes", ()),
    )
    assert any("zero.Init exit failed: LookupError" in note for note in notes)
    assert any("process-group cleanup failed: RuntimeError" in note for note in notes)

    dist.fail_destroy = False
    contract["_retry_owned_initialization_process_group"](transaction)
    assert transaction.owns_process_group is False
    assert dist.destroy_calls == 2


def test_enter_failure_remains_primary_and_preexisting_group_is_never_destroyed() -> None:
    """enter 首异常不被 cleanup 遮蔽,预存进程组不归策略所有。"""

    dist = _FakeDistributed(fail_destroy=False)
    contract = _load_cleanup_contract(dist)
    transaction = contract["_ZeroInitializationTransaction"](required=True)
    transaction.issue()
    context = contract["_ZeroInitializationContext"](
        transaction,
        _InjectedContext(enter_error=KeyError("enter failed")),
        process_group_preexisting=True,
    )

    with pytest.raises(KeyError, match="enter failed"):
        context.__enter__()

    assert transaction.owns_process_group is False
    assert dist.destroy_calls == 0


def test_strategy_source_preserves_retryable_group_ownership_until_success() -> None:
    """源码合同禁止 destroy 失败后无条件清空 ownership。"""

    source = DEEPSPEED_SOURCE.read_text(encoding="utf-8")
    assert "self._closed = not self._owns_process_group" in source
    assert "transaction.release_process_group()" in source
    assert "DeepSpeed zero.Init exit failed:" in source
    assert "DeepSpeed process-group cleanup failed:" in source
