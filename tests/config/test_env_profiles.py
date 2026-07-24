from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from autovla.runtime_profiles.legacy import parse_simple_yaml
from scripts.env.autovla_env import (
    FORBIDDEN_PROFILE_IDS,
    load_profiles,
    render_command,
    validate_finetune_config,
)

ROOT = Path(__file__).resolve().parents[2]


def test_env_profiles_cover_required_tiers() -> None:
    profiles = load_profiles()

    expected = {
        "autovla-core",
        "data-webdataset",
        "data-robodm",
        "data-zarr",
        "data-lerobot",
        "model-gr00t-n1d6",
        "model-gr00t-n1d7",
        "model-pi0-5",
        "model-pi0",
        "model-pi0-fast",
        "model-openvla",
        "model-qwen-action",
        "pi0-5-conversion",
    }

    assert profiles.keys() == expected
    assert {profile.dependency_tier for profile in profiles.values()} == {
        "core",
        "data",
        "model",
    }


def test_no_all_model_zoo_profile_exists() -> None:
    profiles = load_profiles()

    assert FORBIDDEN_PROFILE_IDS.isdisjoint(profiles)


def test_high_risk_profiles_require_manual_authorization() -> None:
    profiles = load_profiles()

    for profile in profiles.values():
        if profile.dependency_tier in {"model", "training", "asset-acquisition"} or (
            profile.dependency_risk == "high"
        ):
            assert profile.requires_manual_authorization is True
            assert profile.default_sync == "manual"
            assert profile.install_status in {
                "not_installed",
                "manual_only",
                "installed",
                "not_verified_for_m11",
            }


def test_render_command_uses_locked_uv_project() -> None:
    profile = load_profiles()["model-gr00t-n1d6"]

    assert render_command(profile, ["python", "-V"]) == [
        "uv",
        "run",
        "--project",
        "envs/model-gr00t-n1d6",
        "--locked",
        "python",
        "-V",
    ]


def test_runtime_profiles_compose_only_required_gr00t_training_extras() -> None:
    """验证 N1D6/DeepSpeed 项目精确组合当前 M11 extras。"""

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    native = tomllib.loads(
        (ROOT / "envs/model-gr00t-n1d6/pyproject.toml").read_text(encoding="utf-8")
    )
    zero = tomllib.loads(
        (ROOT / "envs/training-deepspeed/pyproject.toml").read_text(encoding="utf-8")
    )

    assert native["project"]["dependencies"] == [
        "autovla[model-gr00t-n1d6,data-webdataset,training-deepspeed]"
    ]
    assert zero["project"]["dependencies"] == [
        "autovla[training-deepspeed,model-gr00t-n1d6,data-webdataset]"
    ]
    assert "all-model" not in json.dumps({"native": native, "zero": zero}).lower()


def test_preserved_n1d6_lock_is_audit_only_and_unverified_for_m11() -> None:
    """历史 N1D6 lock 仅供审计,不得冒充满足 M11 的已安装环境。"""

    profiles = load_profiles()
    profile = profiles["model-gr00t-n1d6"]
    descriptor = parse_simple_yaml(ROOT / "configs/env/profiles/model-gr00t-n1d6.yaml")

    assert profile.lock_status == "locked"
    assert profile.install_status == "not_verified_for_m11"
    assert descriptor["runtime_lock_sha256"] == (
        "41f807307ba96a00313b4e7af1bb584db5df42dfbe877eca09082dab60f5d662"
    )
    assert descriptor["runtime_lock_accepted"] is False
    assert descriptor["exact_packages"] == ["deepspeed==0.19.2", "torch==2.7.1"]
    observed_lock_packages = descriptor["observed_lock_packages"]
    assert isinstance(observed_lock_packages, list)
    observed_lock_packages = cast("list[object]", observed_lock_packages)
    assert "torch==2.6.0" in observed_lock_packages
    assert "deepspeed==0.19.2" not in observed_lock_packages
    assert "torch==2.7.1" in profile.notes
    assert "deepspeed==0.19.2" in profile.notes
    assert "不满足" in profile.notes
    assert "不能证明已安装环境" in profile.notes


def test_public_docs_preserve_historical_and_current_runtime_limits() -> None:
    """历史因果证据与当前 M11 未验证边界必须同时保留。"""

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    historical_smoke = (ROOT / "docs/validation/GPU_ARCHITECTURE_SMOKE.md").read_text(
        encoding="utf-8"
    )
    m11_matrix = (ROOT / "docs/runtime/M11_GPU_RUNTIME_MATRIX.md").read_text(encoding="utf-8")

    for text in (readme, historical_smoke):
        assert "3163" in text and "3167" in text
        assert "deferred" in text.lower()
    assert "[T,D]" in historical_smoke
    assert "before CUDA model/tensor allocation" in historical_smoke

    for text in (readme, m11_matrix):
        assert "BLOCKED_C3_DATA" in text
        assert "NO_BACKEND_WINNER" in text
    assert "unvalidated" in m11_matrix
    assert "Runtime validation is deferred" in readme


def test_finetune_env_selector_accepts_gr00t_example() -> None:
    result = validate_finetune_config(
        ROOT / "configs/finetune/examples/gr00t_n1d6_webdataset_env.yaml",
        load_profiles(),
    )
    environment = result["environment"]
    profile = result["profile"]
    assert isinstance(environment, dict)
    assert isinstance(profile, dict)
    environment = cast("dict[str, object]", environment)
    profile = cast("dict[str, object]", profile)

    assert environment["profile"] == "model-gr00t-n1d6"
    assert profile["dependency_tier"] == "model"


def test_finetune_env_selector_rejects_unknown_profile(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text(
        "\n".join(
            [
                "environment:",
                "  manager: uv",
                "  profile: all-model-zoo",
                "  uv_project: envs/all-model-zoo",
                "  uv_environment: .venv/all-model-zoo",
                "  sync_policy: manual",
                "  locked: true",
                "  offline: true",
                "  command_prefix:",
                "    - uv",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown profile"):
        validate_finetune_config(config, load_profiles())


def test_cli_list_and_check_profile() -> None:
    list_result = subprocess.run(
        [sys.executable, "scripts/env/autovla_env.py", "list-profiles"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "model-gr00t-n1d6" in json.loads(list_result.stdout)

    check_result = subprocess.run(
        [sys.executable, "scripts/env/autovla_env.py", "check-profile", "autovla-core"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(check_result.stdout) == {"profile": "autovla-core", "status": "ok"}


def test_cli_sync_profile_requires_explicit_flag() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/env/autovla_env.py", "sync-profile", "autovla-core"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "requires explicit --allow-sync" in result.stderr


def test_agents_policy_mentions_root_branch_and_uv_matrix() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "root checkout by default" in text
    assert "uv-managed profile projects" in text
    assert "git add ." in text


def test_module_docs_have_required_sections() -> None:
    module_docs = [
        ROOT / "autovla/dataloader/MODULE.md",
        ROOT / "autovla/training/MODULE.md",
        ROOT / "autovla/models/MODULE.md",
        ROOT / "autovla/config/MODULE.md",
        ROOT / "configs/env/MODULE.md",
        ROOT / "configs/finetune/MODULE.md",
        ROOT / "scripts/env/MODULE.md",
    ]

    for path in module_docs:
        text = path.read_text(encoding="utf-8")
        lower_text = text.lower()
        assert "# " in text
        assert "purpose" in lower_text
        assert "public contract" in lower_text
        assert "extension rule" in lower_text or "agent workflow" in lower_text


def test_pr16_is_not_active_implementation_path() -> None:
    process_text = (ROOT / "docs/process/OPEN_DECISIONS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "PR #16" in process_text
    assert "open draft" in process_text.lower()
    assert "not mutated" in readme


def test_uv_matrix_should_publish_webdataset_env_gate_next_goal() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    uv_strategy = (ROOT / "docs/architecture/UV_ENVIRONMENT_STRATEGY.md").read_text(
        encoding="utf-8"
    )
    model_matrix = (ROOT / "docs/architecture/MODEL_ZOO_ENVIRONMENT_MATRIX.md").read_text(
        encoding="utf-8"
    )

    next_goal = "AUTOVLA-M3-GR00T-N1D6-WEBDATASET-TELEMETRY-DRYRUN-ENV-GATE-001"
    assert next_goal in readme
    assert next_goal in uv_strategy
    assert next_goal in model_matrix
