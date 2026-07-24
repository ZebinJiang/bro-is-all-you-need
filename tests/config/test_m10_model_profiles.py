"""M10 模型配置和手动环境画像的聚焦测试。"""

from __future__ import annotations

import pytest

from autovla.config import load_yaml
from autovla.config.schema.model import ModelConfig
from scripts.env.autovla_env import load_profiles


def test_active_model_presets_separate_assembly_from_runtime_readiness() -> None:
    """N1.6 可装配但运行仍未验证,另两族继续由资产许可门关闭。"""

    models = {
        key: load_yaml(f"configs/models/{key}.yaml").model
        for key in ("gr00t_n1d6", "gr00t_n1d7", "pi0_5")
    }
    assert all(model.lifecycle_state == "active" for model in models.values())
    assert models["gr00t_n1d6"].runtime_support == "executable"
    assert models["gr00t_n1d6"].validation_status == "runtime_unverified"
    assert models["gr00t_n1d7"].runtime_support == "asset_required"
    assert models["pi0_5"].runtime_support == "asset_required"
    assert "cosmos" in models["gr00t_n1d7"].validation_status
    assert "gemma" in models["pi0_5"].validation_status


def test_deferred_presets_and_new_profiles_remain_manual() -> None:
    """Pi0/Pi0-FAST 显式延后,N1.7/Pi0.5 profile 不安装不同步。"""

    for key in ("pi0", "pi0_fast"):
        model = load_yaml(f"configs/models/{key}.yaml").model
        assert model.lifecycle_state == "DEFERRED_BY_USER_PRIORITY"
        assert model.runtime_support == "architecture_defined_runtime_deferred"

    profiles = load_profiles()
    for key in ("model-gr00t-n1d7", "model-pi0-5"):
        profile = profiles[key]
        assert profile.default_sync == "manual"
        assert profile.install_status == "not_installed"
        assert profile.requires_manual_authorization is True
        assert "sync-profile" in profile.forbidden_commands


def test_model_validation_status_rejects_arbitrary_strings() -> None:
    """模型验证状态只接受当前配置兼容的结构化闭集。"""

    with pytest.raises(ValueError, match=r"model\.validation_status is not canonical"):
        ModelConfig(validation_status="looks_ready_but_is_not_canonical")
