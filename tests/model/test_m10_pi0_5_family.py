"""M10 Pi0.5 家族适配器的聚焦 fail-closed 测试。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from autovla.models.capabilities import CheckpointFormat, RuntimeSupportLevel
from autovla.models.families import M10_MODEL_ZOO_CONTRACT
from autovla.models.families.pi0_5 import (
    Pi05CheckpointAdapter,
    Pi05CheckpointConverter,
    Pi05Config,
    Pi05FamilyDefinition,
    Pi05Processor,
    Pi05VisionLanguageBackbone,
)
from autovla.models.families.pi0_5.family import PI05_SPEC
from autovla.models.registry import get


def _processor(*, horizon: int = 2) -> Pi05Processor:
    """返回小 horizon、固定 32 维统计的处理器。"""

    config = Pi05Config(action_horizon=horizon)
    return Pi05Processor(config, np.zeros(32, dtype=np.float32), np.full(32, 2.0, np.float32))


def test_public_surface_and_family_contract_are_closed() -> None:
    """公开类、来源、能力、资产门和后端结论不得漂移。"""

    import autovla.models.families.pi0_5 as package

    expected = {
        "Pi05Config",
        "Pi05Processor",
        "Pi05VisionLanguageBackbone",
        "Pi05ActionExpert",
        "Pi05Model",
        "Pi05ModelFactory",
        "Pi05CheckpointAdapter",
        "Pi05AssetBundle",
        "Pi05CheckpointConverter",
        "Pi05FamilyDefinition",
    }
    assert set(package.__all__) == expected
    assert all(isinstance(getattr(package, name), type) for name in expected)
    assert isinstance(PI05_SPEC, Pi05FamilyDefinition)
    assert get("pi0_5") is PI05_SPEC
    requirements = PI05_SPEC.assembly_requirements
    assert requirements is not None
    assert requirements.runtime_level is RuntimeSupportLevel.ASSET_GATED
    assert requirements.checkpoint.checkpoint_format is CheckpointFormat.SAFETENSORS
    assert requirements.checkpoint.conversion_required
    assert requirements.evidence.source_architecture_complete
    assert not requirements.evidence.official_checkpoint_load_validated
    assert M10_MODEL_ZOO_CONTRACT.backend_decision == "NO_BACKEND_WINNER"


def test_import_is_lightweight_and_conversion_dependencies_are_not_runtime() -> None:
    """生产包导入不得加载 Torch、JAX、Flax、Orbax 或修改 Transformers。"""

    script = """
import sys
import autovla.models.families.pi0_5
assert not {'torch', 'jax', 'flax', 'orbax', 'transformers'} & set(sys.modules)
from autovla.models.families.pi0_5.family import PI05_SPEC
items = PI05_SPEC.assembly_requirements.dependencies.items
classes = {item.module: item.dependency_class.value for item in items}
assert classes['jax'] == classes['flax'] == classes['orbax'] == 'conversion_only'
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_strict_image_masks_and_200_token_limit_fail_closed() -> None:
    """图像必须按三相机 NCHW 排列,mask 与 token mask 必须是严格 bool。"""

    processor = _processor()
    images = {name: np.zeros((2, 3, 224, 224), dtype=np.float32) for name in processor.camera_order}
    masks = {name: np.ones(2, dtype=np.bool_) for name in processor.camera_order}
    stacked, image_mask = processor.validate_images(images, masks)
    assert stacked.shape == (2, 3, 3, 224, 224)
    assert image_mask.shape == (2, 3)
    bad_masks = dict(masks)
    bad_masks["base_0_rgb"] = np.ones(2, dtype=np.int64)
    with pytest.raises(TypeError, match="strict bool"):
        processor.validate_images(images, bad_masks)
    with pytest.raises(ValueError, match="200-token"):
        processor.validate_prompt_state_tokens(
            np.zeros((1, 201), dtype=np.int64), np.ones((1, 201), dtype=np.bool_)
        )
    with pytest.raises(TypeError, match="strict bool"):
        processor.validate_prompt_state_tokens(
            np.zeros((1, 200), dtype=np.int64), np.ones((1, 200), dtype=np.int64)
        )


def test_quantile_inverse_runs_before_semantic_inverse_and_preserves_masks() -> None:
    """反 quantile 必须先于语义逆变换,非活动动作必须保持输入值。"""

    processor = _processor()
    actions = np.ones((1, 2, 32), dtype=np.float32)
    mask = np.ones_like(actions, dtype=np.bool_)
    mask[..., -1] = False
    events: list[str] = []

    def to_model(value: np.ndarray) -> np.ndarray:
        """模拟数据集动作语义正变换。"""

        events.append("semantic_forward")
        return value + np.float32(0.25)

    def to_physical(value: np.ndarray) -> np.ndarray:
        """验证输入已完成反 quantile 后再恢复物理语义。"""

        events.append("semantic_inverse_after_quantile")
        assert np.allclose(value[..., :-1], 1.25, atol=2e-6)
        return value - np.float32(0.25)

    normalized = processor.normalize_actions(actions, mask, to_model_semantics=to_model)
    restored = processor.denormalize_actions(normalized, mask, to_physical_semantics=to_physical)
    assert events == ["semantic_forward", "semantic_inverse_after_quantile"]
    assert np.allclose(restored[..., :-1], actions[..., :-1], atol=2e-6)
    assert np.allclose(normalized[..., -1], actions[..., -1])


def test_prefix_cache_is_owned_and_suffix_assembly_never_mutates_it() -> None:
    """NumPy cache 不得与源数组别名,也不得接受值写入或被 suffix 拼接改写。"""

    backbone = Pi05VisionLanguageBackbone(Pi05Config(action_horizon=2))
    key = np.arange(12, dtype=np.float32).reshape(1, 2, 3, 2)
    value = key + 1
    cache = backbone.build_prefix_cache((key,), (value,), np.ones((1, 3), dtype=np.bool_))
    fingerprint = cache["fingerprint"]
    key[...] = -1
    value[...] = -2
    cached_key = cache["keys"][0]
    cached_value = cache["values"][0]
    assert np.all(np.asarray(cached_key) >= 0)
    assert np.all(np.asarray(cached_value) >= 1)
    assert not cached_key.flags.writeable
    assert not cached_value.flags.writeable
    assert not cache["mask"].flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        cached_key[...] = 0
    with pytest.raises(ValueError, match="read-only"):
        cached_value[...] = 0
    before_key = cached_key.copy()
    before_value = cached_value.copy()
    suffix = np.zeros((1, 2, 1, 2), dtype=np.float32)
    combined_keys, combined_values = backbone.joint_attention_inputs(cache, (suffix,), (suffix,))
    assert combined_keys[0].shape[-2] == 4
    assert combined_values[0].shape[-2] == 4
    assert np.array_equal(cache["keys"][0], before_key)
    assert np.array_equal(cache["values"][0], before_value)
    assert cache["keys"][0].shape[-2] == 3
    assert cache["fingerprint"] == fingerprint
    with pytest.raises(TypeError):
        cache["keys"] = ()


def test_injected_cache_backend_is_clone_owned_but_not_claimed_immutable() -> None:
    """注入张量后端必须切断源别名,但 cache 不伪装后端值本身只读。"""

    class CloneableTensor:
        """模拟保留原生可变性的外部张量后端。"""

        def __init__(self, value: int) -> None:
            """保存可变载荷与 K/V 形状。"""

            self.value = value
            self.shape = (1, 2, 3, 2)

        def clone(self) -> CloneableTensor:
            """返回独立拥有载荷的后端副本。"""

            return CloneableTensor(self.value)

    backbone = Pi05VisionLanguageBackbone(Pi05Config(action_horizon=2))
    source = CloneableTensor(7)
    cache = backbone.build_prefix_cache((source,), (source,), np.ones((1, 3), dtype=np.bool_))
    source.value = -1
    cached = cache["keys"][0]
    assert isinstance(cached, CloneableTensor)
    assert cached is not source
    assert cached.value == 7
    cached.value = 9
    assert cached.value == 9


def test_conversion_manifest_has_full_accounting_and_rejects_drift() -> None:
    """转换清单必须覆盖两侧键、shape、dtype、hash,并拒绝缺失与碰撞。"""

    converter = Pi05CheckpointConverter()
    source = {"params/expert/kernel": np.arange(6, dtype=np.float32).reshape(2, 3)}
    rules = {
        "params/expert/kernel": {
            "destination_key": "action_expert.weight",
            "permutation": (1, 0),
            "shape": (3, 2),
            "dtype": "float32",
        }
    }
    tensors, manifest = converter.convert(source, rules, source_manifest_sha256="a" * 64)
    assert tensors["action_expert.weight"].shape == (3, 2)
    record = manifest["records"][0]
    assert set(record) == {
        "source_key",
        "destination_key",
        "source_shape",
        "destination_shape",
        "source_dtype",
        "destination_dtype",
        "source_sha256",
        "destination_sha256",
    }
    assert manifest["accounting"] == {
        "source_count": 1,
        "destination_count": 1,
        "missing_count": 0,
        "unexpected_count": 0,
        "collision_count": 0,
    }
    with pytest.raises(ValueError, match="missing"):
        converter.convert({}, rules, source_manifest_sha256="a" * 64)
    collision_rules = {
        "a": {"destination_key": "same", "permutation": (), "shape": (1,), "dtype": "float32"},
        "b": {"destination_key": "same", "permutation": (), "shape": (1,), "dtype": "float32"},
    }
    with pytest.raises(ValueError, match="collisions"):
        converter.convert(
            {"a": np.ones(1, np.float32), "b": np.ones(1, np.float32)},
            collision_rules,
            source_manifest_sha256="b" * 64,
        )


def test_conversion_hashes_canonical_little_endian_bytes() -> None:
    """同值大端与小端来源必须得到相同来源 hash、目标值与目标 hash。"""

    converter = Pi05CheckpointConverter()
    little = np.arange(6, dtype="<f4").reshape(2, 3)
    big = little.astype(">f4")
    rules = {
        "kernel": {
            "destination_key": "weight",
            "permutation": (1, 0),
            "shape": (3, 2),
            "dtype": "float32",
        }
    }
    little_tensors, little_manifest = converter.convert(
        {"kernel": little}, rules, source_manifest_sha256="c" * 64
    )
    big_tensors, big_manifest = converter.convert(
        {"kernel": big}, rules, source_manifest_sha256="c" * 64
    )
    assert (
        little_manifest["records"][0]["source_sha256"]
        == big_manifest["records"][0]["source_sha256"]
    )
    assert (
        little_manifest["records"][0]["destination_sha256"]
        == big_manifest["records"][0]["destination_sha256"]
    )
    assert np.array_equal(little_tensors["weight"], big_tensors["weight"])
    assert little_tensors["weight"].flags.c_contiguous
    assert big_tensors["weight"].dtype.byteorder in {"<", "="}


@pytest.mark.parametrize(
    ("rule_update", "error", "message"),
    [
        ({"destination_key": 1}, TypeError, "destination_key"),
        ({"dtype": np.str_("float32")}, TypeError, "dtype"),
        ({"permutation": [1, 0]}, TypeError, "permutation"),
        ({"permutation": (True, 0)}, TypeError, "permutation"),
        ({"permutation": (0, 0)}, ValueError, "invalid permutation"),
        ({"shape": [3, 2]}, TypeError, "shape"),
        ({"shape": (3, True)}, TypeError, "shape"),
        ({"shape": (3, 0)}, ValueError, "positive"),
    ],
)
def test_conversion_rejects_malformed_rule_values(
    rule_update: dict[str, object], error: type[Exception], message: str
) -> None:
    """规则值不得通过字符串、列表、布尔或 NumPy 标量隐式归一化。"""

    converter = Pi05CheckpointConverter()
    rule: dict[str, object] = {
        "destination_key": "weight",
        "permutation": (1, 0),
        "shape": (3, 2),
        "dtype": "float32",
    }
    rule.update(rule_update)
    with pytest.raises(error, match=message):
        converter.convert(
            {"kernel": np.ones((2, 3), dtype=np.float32)},
            {"kernel": rule},
            source_manifest_sha256="d" * 64,
        )


def test_conversion_rejects_malformed_rule_containers_and_keys() -> None:
    """规则映射、精确字段及两侧键必须保持严格容器契约。"""

    converter = Pi05CheckpointConverter()
    source = {"kernel": np.ones((2, 3), dtype=np.float32)}
    with pytest.raises(TypeError, match="must be a mapping"):
        converter.convert(source, {"kernel": []}, source_manifest_sha256="d" * 64)  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="fields must be exact"):
        converter.convert(
            source,
            {
                "kernel": {
                    "destination_key": "weight",
                    "permutation": (1, 0),
                    "shape": (3, 2),
                    "dtype": "float32",
                    "extra": None,
                }
            },
            source_manifest_sha256="d" * 64,
        )
    valid_rule = {
        "destination_key": "weight",
        "permutation": (1, 0),
        "shape": (3, 2),
        "dtype": "float32",
    }
    with pytest.raises(TypeError, match="keys must be exact"):
        converter.convert(
            {1: np.ones((2, 3), dtype=np.float32)},  # type: ignore[dict-item]
            {"kernel": valid_rule},
            source_manifest_sha256="d" * 64,
        )


@pytest.mark.parametrize(
    "source",
    [
        [[1.0, 2.0]],
        np.array([[object()]], dtype=object),
        np.array([["1", "2"]]),
        np.array([[True, False]]),
        np.array([[1 + 2j]], dtype=np.complex64),
    ],
)
def test_conversion_rejects_unsupported_or_non_numeric_sources(source: object) -> None:
    """来源必须是有限实数 NumPy 张量,不得静默接收容器或不支持 dtype。"""

    converter = Pi05CheckpointConverter()
    rules = {
        "kernel": {
            "destination_key": "weight",
            "permutation": (),
            "shape": (1, int(np.asarray(source).size)),
            "dtype": "float32",
        }
    }
    with pytest.raises((TypeError, ValueError), match=r"NumPy array|finite numeric"):
        converter.convert({"kernel": source}, rules, source_manifest_sha256="e" * 64)


def test_checkpoint_and_deferred_family_boundaries_are_fail_closed(tmp_path: Path) -> None:
    """运行时只接受 safetensors;Pi0/Pi0-FAST 保持延后且工厂不自动执行。"""

    adapter = Pi05CheckpointAdapter()
    unsafe = tmp_path / "model.bin"
    unsafe.write_bytes(b"pickle-like")
    with pytest.raises(ValueError, match="safetensors"):
        adapter.validate_path(unsafe)
    missing = tmp_path / "model.safetensors"
    with pytest.raises(ValueError, match="existing"):
        adapter.validate_path(missing)
    assert get("pi0").runtime_support.value == "architecture_defined_runtime_deferred"
    assert get("pi0_fast").runtime_support.value == "architecture_defined_runtime_deferred"
    assert PI05_SPEC.factories.model.endswith(":Pi05ModelFactory")
    assert "pi0_5" in PI05_SPEC.factories.model
    assert all(
        "pi0_fast" not in value for value in PI05_SPEC.factories.to_json_dict().values() if value
    )
