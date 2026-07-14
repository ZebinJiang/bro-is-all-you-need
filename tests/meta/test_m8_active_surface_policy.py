"""M8 active surface、依赖 profile 与 staged asset policy 测试。"""

from pathlib import Path

from scripts.quality.check_staged_model_assets import rejection_reason

ROOT = Path(__file__).resolve().parents[2]


def test_active_m8_upstream_keys_use_current_autovla_identity() -> None:
    """只要求两个 M8 条目改名,保留历史 GenesisVLA 键与全部 pins。"""

    text = (ROOT / "docs/references/upstream_sources.yaml").read_text(encoding="utf-8")
    assert text.count("current_autovla_code_reuse:") == 2
    assert text.count("current_genesisvla_code_reuse:") == 5
    assert "5dc80c4" in text
    assert "b919284ab1ad6dbc1cb0e06b10386ff74160b586" in text


def test_active_presets_have_no_fsdp_or_cpu_model_runtime() -> None:
    """验证 active M8 preset/launcher/CI 排除 FSDP 和 CPU model runtime。"""

    active_paths = (
        ROOT / "autovla/resources/configs/environments",
        ROOT / "autovla/resources/configs/experiments/gr00t_n1d6_robodm_container.yaml",
        ROOT / "autovla/resources/configs/experiments/gr00t_n1d6_webdataset.yaml",
        ROOT / "autovla/resources/configs/training",
        ROOT / "configs/environments",
        ROOT / "configs/experiments/gr00t_n1d6_robodm_container.yaml",
        ROOT / "configs/experiments/gr00t_n1d6_webdataset.yaml",
        ROOT / "configs/experiments/gr00t_n1d6_webdataset_ddp.yaml",
        ROOT / "configs/experiments/gr00t_n1d6_webdataset_zero1.yaml",
        ROOT / "configs/experiments/gr00t_n1d6_webdataset_zero2.yaml",
        ROOT / "configs/experiments/gr00t_n1d6_webdataset_zero3.yaml",
        ROOT / "configs/training",
        ROOT / "configs/distributed",
        ROOT / "scripts/slurm/request_m8_a100_architecture_smoke.sh",
        ROOT / "scripts/slurm/m8_a100_architecture_smoke.sbatch",
        ROOT / ".github/workflows/autovla.yml",
    )
    text = "\n".join(
        (
            path.read_text(encoding="utf-8")
            if path.is_file()
            else "\n".join(
                item.read_text(encoding="utf-8")
                for item in sorted(path.rglob("*"))
                if item.is_file()
            )
        )
        for path in active_paths
    ).lower()
    assert "fsdp" not in text
    assert "fully_sharded" not in text
    assert "m6-cpu-runtime" not in text
    assert "device: cpu" not in text


def test_staged_asset_policy_is_path_and_size_aware(tmp_path: Path) -> None:
    """验证模型 namespace 必拒绝,小型普通 fixture 不因扩展名误伤。"""

    base_model = tmp_path / "base_model" / "model.py"
    base_model.parent.mkdir()
    base_model.write_text("source = True\n", encoding="utf-8")
    fixture = tmp_path / "tests" / "fixtures" / "header.bin"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"small source fixture")
    large_weight = tmp_path / "fixtures" / "model.safetensors"
    large_weight.parent.mkdir(exist_ok=True)
    large_weight.write_bytes(b"x" * (1024 * 1024))

    assert rejection_reason(tmp_path, base_model) == "forbidden model asset/cache path"
    assert rejection_reason(tmp_path, fixture) is None
    assert rejection_reason(tmp_path, large_weight) == "large model artifact suffix"
