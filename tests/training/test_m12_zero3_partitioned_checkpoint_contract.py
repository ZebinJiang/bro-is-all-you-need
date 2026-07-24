"""M12 ZeRO-3 官方 checkpoint 分区加载的无 Torch 源码合同测试。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEEPSPEED = ROOT / "autovla/training/strategy/deepspeed.py"
CONTRACTS = ROOT / "autovla/models/assembly/contracts.py"
SESSION = ROOT / "autovla/training/session.py"
RECEIPTS = ROOT / "autovla/training/distributed_receipts.py"
FAMILIES = ("gr00t_n1d6", "gr00t_n1d7", "pi0_5")


def _source(path: Path) -> str:
    """读取工作树内 Python 源码。"""

    return path.read_text(encoding="utf-8")


def _method_source(path: Path, class_name: str, method_name: str) -> str:
    """通过 AST 精确截取一个类方法。"""

    source = _source(path)
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == method_name
            ):
                segment = ast.get_source_segment(source, item)
                if segment is None:
                    raise AssertionError(f"cannot recover {class_name}.{method_name}")
                return segment
    raise AssertionError(f"missing {class_name}.{method_name}")


def test_zero3_never_gathers_or_loads_the_whole_model() -> None:
    """策略禁止全模型参数 gather、state_dict mutation 和普通 loader 旁路。"""

    boundary = _method_source(DEEPSPEED, "DeepSpeedStrategy", "load_official_checkpoint")
    assert "tuple(model.parameters())" not in boundary
    assert "list(model.parameters())" not in boundary
    assert "model.load_state_dict" not in boundary
    assert "GatheredParameters((parameter,), modifier_rank=0)" in boundary
    assert boundary.count("GatheredParameters((parameter,), modifier_rank=0)") == 1
    assert "_logical_parameter_shape(parameter)" in boundary
    assert "return loader()" in boundary
    zero3_branch, local_branch = boundary.rsplit("return loader()", maxsplit=1)
    assert "partitioned_loader is None" in zero3_branch
    assert "family-owned partitioned adapter" in zero3_branch
    assert local_branch.strip() == ""


def test_zero3_groups_are_singleton_rank0_mutations_with_explicit_buffer_sync() -> None:
    """每组上界为一,mutation 由 rank0 action 包围,buffer 单独广播。"""

    source = _source(DEEPSPEED)
    boundary = _method_source(DEEPSPEED, "DeepSpeedStrategy", "load_official_checkpoint")
    assert "len(parameter_names) < 2" in boundary
    assert "strict model subsets" in boundary
    assert "action=lambda name=name, parameter=parameter: sink.load_tensor(" in boundary
    assert "modifier_rank=0" in boundary
    assert "action=lambda name=name, buffer=buffer: sink.load_tensor(name, buffer)" in boundary
    assert "_collectives.broadcast(buffer, src=0)" in boundary
    assert boundary.index("sink.load_tensor(name, buffer)") < boundary.index(
        "_collectives.broadcast(buffer, src=0)"
    )
    assert "def _run_rank_zero_action(" in source
    rank_zero_action = source[source.index("def _run_rank_zero_action(") :]
    assert "if rank == 0:" in rank_zero_action
    assert "_collectives.broadcast_object_list(status, src=0)" in rank_zero_action


def test_local_ddp_and_zero12_keep_the_direct_strict_loader() -> None:
    """非 ZeRO-3 路径继续直接调用原 family loader。"""

    local = _method_source(
        CONTRACTS,
        "LocalInitializationContextFactory",
        "load_official_checkpoint",
    )
    strategy_factory = _method_source(
        SESSION,
        "StrategyInitializationContextFactory",
        "load_official_checkpoint",
    )
    deepspeed = _method_source(DEEPSPEED, "DeepSpeedStrategy", "load_official_checkpoint")
    assert "return loader()" in local
    assert "return loader()" in strategy_factory
    assert "if self._deepspeed_config.zero_stage == 3:" in deepspeed
    assert deepspeed.rstrip().endswith("return loader()")


def test_all_active_families_use_the_shared_partition_sink_boundary() -> None:
    """三个 active family 均从同一 request 边界交付 family-owned sink。"""

    protocol = _source(CONTRACTS)
    for method in (
        "prepare",
        "audit_tensor",
        "complete_audit",
        "load_tensor",
        "finish",
        "restore_result",
    ):
        assert f"def {method}(" in protocol
    for family in FAMILIES:
        factory = _source(ROOT / f"autovla/models/families/{family}/factory.py")
        checkpoint = _source(ROOT / f"autovla/models/families/{family}/checkpoint.py")
        assert factory.count("partitioned_loader=") == 1
        assert ".partitioned_load(" in factory
        assert "def partitioned_load(" in checkpoint
        for method in (
            "prepare",
            "audit_tensor",
            "complete_audit",
            "load_tensor",
            "finish",
            "restore_result",
        ):
            assert f"def {method}(" in checkpoint


def test_partition_sinks_use_bounded_safe_open_without_full_state_materialization() -> None:
    """ZeRO-3 sink 只保留 metadata plan,不构造完整 checkpoint tensor dict。"""

    sink_classes = {
        "gr00t_n1d6": "_Gr00tN1d6PartitionedLoadSink",
        "gr00t_n1d7": "_Gr00tN1d7PartitionedLoadSink",
        "pi0_5": "_Pi05PartitionedLoadSink",
    }
    for family, class_name in sink_classes.items():
        path = ROOT / f"autovla/models/families/{family}/checkpoint.py"
        source = _source(path)
        tree = ast.parse(source)
        sink = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        segment = ast.get_source_segment(source, sink)
        if segment is None:
            raise AssertionError(f"cannot recover {class_name}")
        assert "load_file" not in segment
        assert "state.update" not in segment
        assert "dict[str, torch.Tensor]" not in segment
        assert "safe_open" in source
        assert "_iter_chunk_regions(" in segment
        assert "max_slice_bytes=" in segment
        assert "_MAX_TENSOR_SLICE_BYTES" in source
        factory = _source(ROOT / f"autovla/models/families/{family}/factory.py")
        assert "model.state_dict()" not in factory


def test_receipts_remain_declared_payloads_only() -> None:
    """静态收据不能被本修复升级为 GPU runtime evidence。"""

    source = _source(RECEIPTS)
    assert 'DECLARED_PAYLOAD_SCOPE = "DECLARED_PAYLOADS_ONLY"' in source
    assert "GPU_RUNTIME_VERIFIED" not in source
    assert "cannot claim runtime observation" in source


def test_candidate_ruff_regressions_are_removed() -> None:
    """候选的 RUF003 全角分号和三个常量 setattr 不再存在。"""

    changed_sources = (
        DEEPSPEED,
        ROOT / "tests/training/test_m12_deepspeed_glue.py",
    )
    ambiguous_semicolon = chr(0xFF1B)
    assert all(ambiguous_semicolon not in _source(path) for path in changed_sources)
    glue = _source(ROOT / "tests/training/test_m12_deepspeed_glue.py")
    for field in ("_deepspeed_config", "_initialization", "_deepspeed_module"):
        assert f'setattr(strategy, "{field}"' not in glue
