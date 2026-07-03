from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.env.autovla_env import (
    FORBIDDEN_PROFILE_IDS,
    load_profiles,
    render_command,
    validate_finetune_config,
)

ROOT = Path(__file__).resolve().parents[2]


def test_env_profiles_cover_required_tiers() -> None:
    profiles = load_profiles()

    required = {
        "autovla-core",
        "data-webdataset",
        "data-robodm",
        "data-zarr",
        "data-lerobot",
        "model-gr00t-n1d6",
        "model-pi0",
        "model-pi0-fast",
        "model-openvla",
        "model-qwen-action",
    }

    assert required <= profiles.keys()
    assert {profile.dependency_tier for profile in profiles.values()} == {"core", "data", "model"}


def test_no_all_model_zoo_profile_exists() -> None:
    profiles = load_profiles()

    assert FORBIDDEN_PROFILE_IDS.isdisjoint(profiles)


def test_model_profiles_require_manual_authorization() -> None:
    profiles = load_profiles()

    for profile in profiles.values():
        if profile.dependency_tier == "model":
            assert profile.requires_manual_authorization is True
            assert profile.default_sync == "manual"
            assert profile.install_status in {"not_installed", "manual_only"}


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


def test_finetune_env_selector_accepts_gr00t_example() -> None:
    result = validate_finetune_config(
        ROOT / "configs/finetune/examples/gr00t_n1d6_webdataset_env.yaml",
        load_profiles(),
    )

    assert result["environment"]["profile"] == "model-gr00t-n1d6"
    assert result["profile"]["dependency_tier"] == "model"


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
