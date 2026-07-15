"""M10 模型配置和手动环境画像的聚焦测试。"""

from __future__ import annotations

from autovla.config import load_yaml
from scripts.env.autovla_env import load_profiles


def test_active_model_presets_encode_asset_gates() -> None:
    """三个活跃 preset 均为资产门控且不声称 runtime ready。"""

    models = {
        key: load_yaml(f"configs/models/{key}.yaml").model
        for key in ("gr00t_n1d6", "gr00t_n1d7", "pi0_5")
    }
    assert all(model.lifecycle_state == "active" for model in models.values())
    assert all(model.runtime_support == "asset_required" for model in models.values())
    assert "compute_full_verification_required" in models["gr00t_n1d6"].validation_status
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
