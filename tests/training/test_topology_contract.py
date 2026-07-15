"""生产训练拓扑解析与 Data 投影 source-contract 测试。"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest


def _load_topology_contract() -> tuple[type[object], object]:
    """从生产源码提取纯拓扑定义,避免触发 Torch runtime import。"""

    session_tree = ast.parse(Path("autovla/training/session.py").read_text(encoding="utf-8"))
    session_nodes: list[ast.stmt] = [
        node
        for node in session_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        and getattr(node, "name", "") in {"_require_exact_non_negative_int", "TrainingTopology"}
    ]
    namespace: dict[str, object] = {"dataclass": dataclass}
    exec(compile(ast.Module(session_nodes, type_ignores=[]), "session.py", "exec"), namespace)

    strategy_tree = ast.parse(
        Path("autovla/training/strategy/distributed_data_parallel.py").read_text(encoding="utf-8")
    )
    parser_nodes: list[ast.stmt] = [
        node
        for node in strategy_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "_parse_decimal",
            "_parse_slurm_local_world_size",
            "_parse_master_endpoint",
            "_parse_distributed_topology",
        }
    ]
    namespace["Mapping"] = Mapping
    exec(compile(ast.Module(parser_nodes, type_ignores=[]), "ddp.py", "exec"), namespace)
    return (
        cast(type[object], namespace["TrainingTopology"]),
        namespace["_parse_distributed_topology"],
    )


def _parse(environment: Mapping[str, str], *, strategy: str) -> object:
    """调用提取的生产 parser。"""

    _, parser = _load_topology_contract()
    return parser(environment, strategy=strategy)  # type: ignore[operator]


def test_torchrun_same_node_topology_is_exact() -> None:
    """验证 torchrun 同节点 rank/node/local-world 身份。"""

    topology = _parse(
        {
            "RANK": "1",
            "WORLD_SIZE": "4",
            "LOCAL_RANK": "1",
            "LOCAL_WORLD_SIZE": "4",
            "GROUP_RANK": "0",
            "MASTER_ADDR": "node-a",
            "MASTER_PORT": "29500",
        },
        strategy="distributed_data_parallel",
    )

    assert topology.to_dict() == {  # type: ignore[attr-defined]
        "rank": 1,
        "local_rank": 1,
        "world_size": 4,
        "backend": "nccl",
        "device_index": 1,
        "node_rank": 0,
        "local_world_size": 4,
        "launcher": "torchrun",
        "strategy": "distributed_data_parallel",
        "master_addr": "node-a",
        "master_port": 29500,
        "launch_run_id": None,
    }


def test_slurm_cross_node_like_topology_is_exact() -> None:
    """验证 Slurm 跨节点样式拓扑和 DeepSpeed 身份。"""

    topology = _parse(
        {
            "SLURM_PROCID": "3",
            "SLURM_NTASKS": "4",
            "SLURM_LOCALID": "1",
            "SLURM_NODEID": "1",
            "SLURM_NTASKS_PER_NODE": "2(x2)",
            "SLURM_JOB_ID": "12345",
            "MASTER_ADDR": "node-a",
            "MASTER_PORT": "29500",
        },
        strategy="deepspeed",
    )

    assert topology.node_rank == 1  # type: ignore[attr-defined]
    assert topology.local_world_size == 2  # type: ignore[attr-defined]
    assert topology.launcher == "slurm"  # type: ignore[attr-defined]
    assert topology.strategy == "deepspeed"  # type: ignore[attr-defined]
    assert topology.master_addr == "node-a"  # type: ignore[attr-defined]
    assert topology.master_port == 29500  # type: ignore[attr-defined]
    assert topology.launch_run_id == "12345"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"MASTER_ADDR": "127.0.0.1"}, "loopback"),
        ({"SLURM_JOB_ID": ""}, "stable launcher run id"),
        ({"MASTER_PORT": "0"}, "must be in"),
    ),
)
def test_cross_node_launcher_metadata_fails_closed(
    changes: dict[str, str],
    message: str,
) -> None:
    """验证跨节点 rendezvous 缺失、回环或非法端口均立即失败。"""

    environment = {
        "SLURM_PROCID": "0",
        "SLURM_NTASKS": "4",
        "SLURM_LOCALID": "0",
        "SLURM_NODEID": "0",
        "SLURM_NTASKS_PER_NODE": "2(x2)",
        "SLURM_JOB_ID": "12345",
        "MASTER_ADDR": "node-a",
        "MASTER_PORT": "29500",
    }
    environment.update(changes)

    with pytest.raises(ValueError, match=message):
        _parse(environment, strategy="distributed_data_parallel")


def test_checkpoint_topology_identity_is_rank_neutral() -> None:
    """验证同一作业不同 rank 共享恢复身份而保留各自运行元数据。"""

    topology_type, _ = _load_topology_contract()
    common = {
        "world_size": 4,
        "backend": "nccl",
        "local_world_size": 2,
        "launcher": "torchrun",
        "strategy": "distributed_data_parallel",
        "master_addr": "node-a",
        "master_port": 29500,
        "launch_run_id": "run-1",
    }
    rank_zero = topology_type(
        rank=0,
        local_rank=0,
        device_index=0,
        node_rank=0,
        **common,
    )
    rank_three = topology_type(
        rank=3,
        local_rank=1,
        device_index=1,
        node_rank=1,
        **common,
    )

    assert rank_zero.to_dict() != rank_three.to_dict()  # type: ignore[attr-defined]
    assert rank_zero.checkpoint_identity() == rank_three.checkpoint_identity()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"rank": 4}, "rank is out of range"),
        ({"local_rank": 2}, "local rank is out of range"),
        ({"node_rank": 2}, "node rank is out of range"),
        ({"rank": 2, "node_rank": 0}, "rank does not match"),
        ({"local_world_size": 3}, "uniform local world sizes"),
    ),
)
def test_topology_rejects_invalid_ranges(changes: dict[str, object], message: str) -> None:
    """验证 canonical topology 对所有索引关系 fail closed。"""

    topology_type, _ = _load_topology_contract()
    values: dict[str, object] = {
        "rank": 3,
        "local_rank": 1,
        "world_size": 4,
        "backend": "nccl",
        "device_index": 1,
        "node_rank": 1,
        "local_world_size": 2,
        "launcher": "torchrun",
        "strategy": "distributed_data_parallel",
    }
    values.update(changes)

    with pytest.raises(ValueError, match=message):
        topology_type(**values)


def test_engine_projects_all_topology_fields_without_data_training_import() -> None:
    """验证 Engine 精确投影且 Data 包不依赖 Training。"""

    engine = Path("autovla/training/engine.py").read_text(encoding="utf-8")
    for field in (
        "rank",
        "local_rank",
        "world_size",
        "node_rank",
        "local_world_size",
        "launcher",
        "strategy",
    ):
        assert f"{field}=topology.{field}" in engine
    assert "self._partition_from_topology(topology)" in engine
    for path in Path("autovla/data").rglob("*.py"):
        assert "autovla.training" not in path.read_text(encoding="utf-8")


def test_ddp_prepare_transaction_covers_all_post_init_failures() -> None:
    """源码契约要求 setup 后每个失败点统一进入 session.close 回滚。"""

    source = Path("autovla/training/strategy/distributed_data_parallel.py").read_text(
        encoding="utf-8"
    )
    prepare = source[source.index("    def prepare(", source.index("class Distributed")) :]
    begin = prepare.index("try:")
    close = prepare.index("session.close()")
    for operation in (
        "session.setup()",
        "session.prepare_model(model)",
        "optimizer_factory(prepared)",
        "scheduler_factory(optimizer, batches_per_epoch)",
        "session.bind(prepared, optimizer, scheduler)",
    ):
        assert begin < prepare.index(operation) < close
    assert "except BaseException:" in prepare[:close]
