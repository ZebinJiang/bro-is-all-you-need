"""M11 N1.7 checkpoint 流式边界与模型 CLI 错误契约测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import pytest

from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config

ROOT = Path(__file__).resolve().parents[2]

_Event = (
    tuple[Literal["to"], object, object]
    | tuple[Literal["destination_slice"], tuple[slice, ...]]
    | tuple[Literal["copy"]]
    | tuple[Literal["shape"], str]
    | tuple[Literal["payload"], str, tuple[slice, ...]]
    | tuple[Literal["open"], str]
)


def _available_module_spec(name: str) -> object:
    """为假可选依赖返回稳定的非空模块描述。"""

    del name
    return object()


def _config() -> Gr00tN1d7Config:
    """构造与本地假 artifact 一致的 N1.7 配置。"""

    return Gr00tN1d7Config.from_artifact_mapping(
        {
            "select_layer": 16,
            "num_layers": 32,
            "vl_self_attention_layers": 4,
            "load_bf16": True,
            "state_dropout_prob": 0.2,
            "max_state_dim": 132,
            "max_action_dim": 132,
            "action_horizon": 40,
        },
        cosmos_revision="a" * 40,
    )


def _checkpoint_root(root: Path) -> Path:
    """创建仅含空 shard 占位符的本地 checkpoint fixture。"""

    root.mkdir()
    payload = {
        "select_layer": 16,
        "num_layers": 32,
        "vl_self_attention_layers": 4,
        "load_bf16": True,
        "state_dropout_prob": 0.2,
        "max_state_dim": 132,
        "max_action_dim": 132,
        "action_horizon": 40,
    }
    (root / "LICENSE").write_text("fixture\n", encoding="utf-8")
    (root / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    for name in ("embodiment_id.json", "processor_config.json", "statistics.json"):
        (root / name).write_text("{}", encoding="utf-8")
    shard = "model-00001-of-00001.safetensors"
    (root / shard).write_bytes(b"x" * 1024)
    (root / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "model.backbone.weight": shard,
                    "model.action_head.weight": shard,
                }
            }
        ),
        encoding="utf-8",
    )
    return root


class _FakeTensor:
    """记录假 tensor 的传输和 mutation 次序。"""

    def __init__(self, shape: tuple[int, ...], events: list[_Event]) -> None:
        """保存 shape 和共享事件流。"""

        self.shape = shape
        self._events = events

    def is_floating_point(self) -> bool:
        """假载荷均视作浮点。"""

        return True

    def to(self, *, device: object = None, dtype: object = None) -> _FakeTensor:
        """记录受控 dtype/device 迁移。"""

        self._events.append(("to", device, dtype))
        return self

    def __getitem__(self, region: tuple[slice, ...]) -> _FakeTensor:
        """返回共享记录器的目标切片。"""

        self._events.append(("destination_slice", region))
        return self

    def copy_(self, payload: _FakeTensor) -> None:
        """记录严格审计后的原位复制。"""

        assert isinstance(payload, _FakeTensor)
        self._events.append(("copy",))


class _FakeSlice:
    """提供不物化 shape 审计和显式切片载荷。"""

    def __init__(self, key: str, shape: tuple[int, ...], events: list[_Event]) -> None:
        """绑定键、shape 和事件流。"""

        self._key = key
        self._shape = shape
        self._events = events

    def get_shape(self) -> tuple[int, ...]:
        """只记录 metadata shape 访问。"""

        self._events.append(("shape", self._key))
        return self._shape

    def get_dtype(self) -> str:
        """返回固定 F32 dtype。"""

        return "F32"

    def __getitem__(self, region: tuple[slice, ...]) -> _FakeTensor:
        """记录 mutation 阶段的单切片物化。"""

        self._events.append(("payload", self._key, region))
        return _FakeTensor(self._shape, self._events)


class _FakeHandle:
    """模拟只读 safetensors shard 句柄。"""

    def __init__(self, events: list[_Event]) -> None:
        """初始化两个参数的固定 shard。"""

        self._events = events
        self._shapes = {
            "model.backbone.weight": (400,),
            "model.action_head.weight": (1, 4),
        }

    def keys(self) -> tuple[str, ...]:
        """返回固定参数顺序。"""

        return tuple(self._shapes)

    def get_slice(self, key: str) -> _FakeSlice:
        """返回零载荷切片描述。"""

        return _FakeSlice(key, self._shapes[key], self._events)

    def get_tensor(self, key: str) -> _FakeTensor:
        """标量专用路径在本 fixture 中不得调用。"""

        raise AssertionError(f"unexpected full tensor read: {key}")


class _FakeModule:
    """提供 checkpoint adapter 要求的最小 torch 模块。"""

    def __init__(self, config: Gr00tN1d7Config, events: list[_Event]) -> None:
        """创建匹配 checkpoint 的目标 tensor。"""

        self.config = config
        self._state = {
            "backbone.weight": _FakeTensor((400,), events),
            "action_head.weight": _FakeTensor((1, 4), events),
        }

    def state_dict(self) -> dict[str, _FakeTensor]:
        """返回可原位复制的目标引用。"""

        return self._state


def test_n1d7_audits_cpu_metadata_before_bounded_payload_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """shape 审计不触达目标设备,mutation 仅按切片读取并及时释放。"""

    root = _checkpoint_root(tmp_path / "checkpoint")
    events: list[_Event] = []
    handle = _FakeHandle(events)

    def safe_open(filename: str, *, framework: str, device: str) -> nullcontext[_FakeHandle]:
        """验证 adapter 始终以本地 CPU metadata 方式打开 shard。"""

        assert Path(filename).parent == root
        assert framework == "pt"
        assert device == "cpu"
        events.append(("open", device))
        return nullcontext(handle)

    fake_torch = SimpleNamespace(nn=SimpleNamespace(Module=_FakeModule), no_grad=nullcontext)
    real_import_module = __import__("importlib").import_module

    def fake_import_module(name: str) -> object:
        """只替换本测试需要的 torch/safetensors 模块。"""

        if name == "torch":
            return fake_torch
        if name == "safetensors":
            return SimpleNamespace(safe_open=safe_open)
        return real_import_module(name)

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("importlib.import_module", fake_import_module)
    monkeypatch.setattr("importlib.util.find_spec", _available_module_spec)
    checkpoint_module = real_import_module("autovla.models.families.gr00t_n1d7.checkpoint")
    report = checkpoint_module.Gr00tN1d7CheckpointAdapter().load_local(
        _FakeModule(_config(), events),
        root,
        device="cuda:0",
        config=_config(),
    )
    first_payload = next(index for index, event in enumerate(events) if event[0] == "payload")
    assert all(event[0] in {"open", "shape"} for event in events[:first_payload])
    assert [event for event in events if event[0] == "open"] == [
        ("open", "cpu"),
        ("open", "cpu"),
    ]
    payload_events = [event for event in events if event[0] == "payload"]
    assert len(payload_events) == 5
    backbone_regions = [event[2] for event in payload_events if event[1] == "model.backbone.weight"]
    assert len(backbone_regions) == 4
    assert all(
        (region[0].stop - region[0].start) * 4 <= (1024 - 1) // 2 for region in backbone_regions
    )
    assert report.provenance["strict_audit_before_mutation"] is True
    assert report.provenance["max_live_tensor_payload_bytes"] == 64 * 1024 * 1024
    assert report.provenance["live_payload_bound"] == "min(64MiB, shard_file_size-1)"


def test_n1d7_rejects_absent_indexed_source_before_payload_or_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """索引声明但 shard 缺失的 source 必须在任何载荷或复制前稳定失败。"""

    root = _checkpoint_root(tmp_path / "checkpoint")
    index_path = root / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    shard = "model-00001-of-00001.safetensors"
    index["weight_map"]["model.backbone.unused"] = shard
    index_path.write_text(json.dumps(index), encoding="utf-8")
    events: list[_Event] = []
    handle = _FakeHandle(events)

    def safe_open(filename: str, *, framework: str, device: str) -> nullcontext[_FakeHandle]:
        """以 CPU metadata 句柄模拟缺少索引 source 的物理 shard。"""

        assert Path(filename).parent == root
        assert framework == "pt"
        assert device == "cpu"
        events.append(("open", device))
        return nullcontext(handle)

    fake_torch = SimpleNamespace(nn=SimpleNamespace(Module=_FakeModule), no_grad=nullcontext)
    real_import_module = __import__("importlib").import_module

    def fake_import_module(name: str) -> object:
        """只替换严格失败回归所需的 torch/safetensors 模块。"""

        if name == "torch":
            return fake_torch
        if name == "safetensors":
            return SimpleNamespace(safe_open=safe_open)
        return real_import_module(name)

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("importlib.import_module", fake_import_module)
    monkeypatch.setattr("importlib.util.find_spec", _available_module_spec)
    checkpoint_module = real_import_module("autovla.models.families.gr00t_n1d7.checkpoint")
    with pytest.raises(
        ValueError,
        match=(
            r"^checkpoint index/physical key mismatch: "
            r"missing_indexed_sources=\['model\.backbone\.unused'\], "
            r"unindexed_sources=\[\]$"
        ),
    ):
        checkpoint_module.Gr00tN1d7CheckpointAdapter().load_local(
            _FakeModule(_config(), events),
            root,
            device="cuda:0",
            config=_config(),
        )
    assert not any(event[0] in {"payload", "copy"} for event in events)


@pytest.mark.parametrize(
    ("family_key", "code"),
    [("not_registered", "UNKNOWN_MODEL_FAMILY"), ("pi0", "MODEL_FAMILY_DEFERRED")],
)
def test_model_inspect_rejections_are_typed_lightweight_json(
    family_key: str,
    code: str,
) -> None:
    """unknown/deferred inspect 非零退出且不导入私有或重运行时模块。"""

    script = f"""
import json
import sys
from autovla.cli.models import main
result = main(['inspect', {family_key!r}])
assert result == 2
forbidden = {{'torch', 'transformers', 'deepspeed', 'jax', 'flax', 'orbax'}}
assert not forbidden & set(sys.modules)
private_prefixes = (
    'autovla.models.families.gr00t_n1d6',
    'autovla.models.families.gr00t_n1d7',
    'autovla.models.families.pi0_5',
    'autovla.models.families.pi0.',
    'autovla.models.families.pi0_fast',
)
assert not any(name.startswith(private_prefixes) for name in sys.modules)
raise SystemExit(result)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "backend_decision": "NO_BACKEND_WINNER",
        "error": {
            "code": code,
            "family_key": family_key,
            "message": (
                "unknown model family"
                if code == "UNKNOWN_MODEL_FAMILY"
                else "model family is deferred by user priority"
            ),
        },
        "ok": False,
        "schema_version": "autovla.model_error.v1",
    }
    assert "Traceback" not in result.stderr
