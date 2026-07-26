"""M12 DeepSpeed 双版本与确定生成配置的无 Torch 合同测试。"""

from dataclasses import replace

import pytest

from autovla.config.schema.distributed import (
    DEEPSPEED_ENGINE_PUBLIC_API_SURFACE,
    DEEPSPEED_MODULE_PUBLIC_API_SURFACE,
    DEEPSPEED_PUBLIC_API_SURFACE,
    SUPPORTED_DEEPSPEED_VERSIONS,
    DeepSpeedConfig,
    validate_deepspeed_engine_public_api,
    validate_deepspeed_public_api,
)


class _FakeZero:
    """提供两个受支持版本共同依赖的 ZeRO 公共入口。"""

    @staticmethod
    def Init() -> None:
        """模拟公开构造上下文入口。"""

    @staticmethod
    def GatheredParameters() -> None:
        """模拟公开参数协调入口。"""


class _FakeDeepSpeed:
    """提供 exact 版本与共同模块级公共 API。"""

    zero = _FakeZero()

    def __init__(self, version: str) -> None:
        """保存模拟安装版本。"""

        self.__version__ = version

    @staticmethod
    def initialize() -> None:
        """模拟公开 engine 初始化入口。"""


class _FakeEngine:
    """提供两个 exact 版本共同依赖的 engine 公共 API。"""

    module = object()
    global_steps = 0
    micro_steps = 0
    skipped_steps = 0

    def __call__(self) -> None:
        """模拟 engine 前向入口。"""

    def backward(self) -> None:
        """模拟 engine backward。"""

    def is_gradient_accumulation_boundary(self) -> bool:
        """模拟累积边界查询。"""

        return True

    def step(self) -> None:
        """模拟 engine step。"""

    def zero_grad(self) -> None:
        """模拟 engine zero_grad。"""

    def save_checkpoint(self) -> None:
        """模拟 engine checkpoint 保存。"""

    def load_checkpoint(self) -> None:
        """模拟 engine checkpoint 恢复。"""


@pytest.mark.parametrize("version", SUPPORTED_DEEPSPEED_VERSIONS)
def test_supported_deepspeed_versions_share_one_validated_public_api(version: str) -> None:
    """0.17.6 与 0.19.2 必须通过同一 exact 公共 API 合同。"""

    diagnostic = validate_deepspeed_public_api(
        _FakeDeepSpeed(version),
        selected_version=version,
    )

    assert diagnostic == {
        "selected_version": version,
        "installed_version": version,
        "validation_status": "exact_version_and_module_api_validated_engine_api_deferred",
        "validated_public_api_surface": DEEPSPEED_MODULE_PUBLIC_API_SURFACE,
        "deferred_public_api_surface": DEEPSPEED_ENGINE_PUBLIC_API_SURFACE,
    }
    engine_diagnostic = validate_deepspeed_engine_public_api(
        _FakeEngine(),
        selected_version=version,
        installed_version=version,
    )
    assert engine_diagnostic["validation_status"] == ("exact_version_and_full_public_api_validated")
    assert engine_diagnostic["validated_public_api_surface"] == DEEPSPEED_PUBLIC_API_SURFACE
    assert engine_diagnostic["deferred_public_api_surface"] == ()
    assert "deepspeed.initialize" in DEEPSPEED_PUBLIC_API_SURFACE
    assert "deepspeed.zero.Init" in DEEPSPEED_PUBLIC_API_SURFACE
    assert "DeepSpeedEngine.load_checkpoint" in DEEPSPEED_PUBLIC_API_SURFACE


def test_deepspeed_exact_version_and_missing_api_fail_closed() -> None:
    """诊断同时报告 selected/installed,并拒绝缺失公共 API。"""

    with pytest.raises(
        RuntimeError,
        match=r"selected='0\.17\.6', installed='0\.19\.2'",
    ):
        validate_deepspeed_public_api(
            _FakeDeepSpeed("0.19.2"),
            selected_version="0.17.6",
        )

    incomplete = _FakeDeepSpeed("0.19.2")
    incomplete.zero = object()
    with pytest.raises(RuntimeError, match=r"deepspeed\.zero\.Init"):
        validate_deepspeed_public_api(
            incomplete,
            selected_version="0.19.2",
        )


@pytest.mark.parametrize("stage", (1, 2, 3))
def test_generated_deepspeed_config_contains_only_determined_positive_buckets(
    stage: int,
) -> None:
    """ZeRO-1/2/3 emitted bucket/lifecycle 值均为严格正整数。"""

    config = DeepSpeedConfig(zero_stage=stage)
    payload = config.to_deepspeed_dict(
        micro_batch_size_per_gpu=2,
        gradient_accumulation_steps=4,
        data_parallel_world_size=8,
        gradient_clipping=1.0,
    )
    zero = payload["zero_optimization"]
    assert isinstance(zero, dict)
    emitted = {
        key: value
        for key, value in zero.items()
        if "bucket_size" in key
        or key
        in {
            "stage3_param_persistence_threshold",
            "stage3_max_live_parameters",
            "stage3_max_reuse_distance",
        }
    }
    assert emitted
    assert all(type(value) is int and value > 0 for value in emitted.values())
    assert "auto" not in repr(payload)


@pytest.mark.parametrize(
    "field",
    (
        "reduce_bucket_size",
        "allgather_bucket_size",
        "stage3_prefetch_bucket_size",
        "stage3_parameter_persistence_threshold",
        "stage3_max_live_parameters",
        "stage3_max_reuse_distance",
    ),
)
@pytest.mark.parametrize("invalid", (True, "1", 0, -1))
def test_deepspeed_bucket_and_lifecycle_fields_reject_ambiguous_values(
    field: str,
    invalid: object,
) -> None:
    """所有确定性 bucket/lifecycle 字段拒绝 bool、str 和非正数。"""

    with pytest.raises(ValueError):
        replace(DeepSpeedConfig(), **{field: invalid})
