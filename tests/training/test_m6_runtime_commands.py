"""验证 M6 生成输入、离线命令和项目 Slurm 包装边界。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "runs/tmp/AUTOVLA-M6-PRODUCTION-DATA-PLANE-GR00T-RUNTIME-BRINGUP-001"


def _generated_runtime(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    """在 ignored task root 生成一次不可变 fixture/config/request 集合。"""
    evidence_root = TASK_ROOT / "test-fixtures" / tmp_path.parent.name / tmp_path.name
    data_root = evidence_root / "fixture-data"
    data_root.mkdir(parents=True)
    (data_root / "sample_index.jsonl").write_text(
        json.dumps({"container": "fixture.tar", "member_prefix": "sample-0"}) + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/generate_m6_reduced_runtime.py"),
            "--evidence-root",
            str(evidence_root),
            "--data-root",
            str(data_root),
            "--runtime-python",
            sys.executable,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    return Path(payload["config_path"]), {
        target: Path(path) for target, path in payload["requests"].items()
    }


def _render(request: Path) -> subprocess.CompletedProcess[str]:
    """调用只渲染不执行的命令入口。"""
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/render_m6_runtime_command.py"),
            "--request",
            str(request),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_runtime_matrix_should_be_offline_bounded_and_device_explicit() -> None:
    """验证四类目标显式区分 CPU/CUDA、进程数和未执行状态。"""
    payload = yaml.safe_load(
        (ROOT / "configs/runtime/m6-runtime-matrix.yaml").read_text(encoding="utf-8")
    )
    assert payload["local_only"] is True
    assert payload["offline"] is True
    assert payload["max_steps"] == 2
    assert payload["targets"]["cpu"] == {
        "strategy": "single_device",
        "devices": 1,
        "device": "cpu",
    }
    assert payload["targets"]["gpu"]["device"] == "cuda"
    assert payload["targets"]["ddp"]["devices"] == 2
    assert payload["targets"]["fsdp2"]["devices"] == 2
    assert all("pass" not in value for value in payload["status"].values())


def test_runtime_surfaces_should_not_embed_machine_local_home_paths() -> None:
    """验证测试、文档和运行配置不绑定某台开发机的 home。"""
    machine_home = "/" + "home" + "/" + "cz-jzb"
    for path in (
        Path(__file__),
        ROOT / "docs/validation/M6_RUNTIME_VALIDATION.md",
        ROOT / "configs/runtime/m6-runtime-matrix.yaml",
        ROOT / "configs/runtime/m6-reduced-runtime.template.yaml",
    ):
        assert machine_home not in path.read_text(encoding="utf-8")


def test_generator_should_write_resolved_local_fixture_and_requests(tmp_path: Path) -> None:
    """验证生成器不依赖 tests、不写权重且严格解析全部 placeholder。"""
    from autovla.config import load_yaml

    config_path, requests = _generated_runtime(tmp_path)
    config_text = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    assert "__AUTOVLA_" not in config_text
    assert config["model"]["architecture_variant"] == "reduced_runtime"
    assert config["model"]["checkpoint_path"] is None
    assert config["model"]["local_files_only"] is True
    assert Path(config["model"]["eagle_asset_path"]).is_dir()
    assert config["data"]["datasets"][0]["embodiment"] == "reduced"
    assert config["training"]["max_steps"] == 2
    resolved = load_yaml(config_path)
    assert resolved.model.architecture_variant == "reduced_runtime"
    assert resolved.data.datasets[0].embodiment == "reduced"
    assert resolved.training.distributed.device == "cpu"
    assert set(requests) == {"cpu", "gpu", "ddp", "fsdp2"}
    generated = tuple(config_path.parents[1].rglob("*"))
    assert not any(
        path.suffix in {".bin", ".ckpt", ".pt", ".pth", ".safetensors"} for path in generated
    )
    generator_source = (ROOT / "scripts/runtime/generate_m6_reduced_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "tests." not in generator_source


def test_renderer_should_distinguish_cpu_gpu_and_two_rank_targets(tmp_path: Path) -> None:
    """验证 CPU/CUDA 设备和两个 torchrun rank 均进入真实 CLI argv。"""
    _, requests = _generated_runtime(tmp_path)
    rendered = {target: _render(request) for target, request in requests.items()}
    assert all(result.returncode == 0 for result in rendered.values())
    assert "training.distributed.device=cpu" in rendered["cpu"].stdout
    assert "training.distributed.device=cuda" in rendered["gpu"].stdout
    assert rendered["cpu"].stdout != rendered["gpu"].stdout
    assert "training.distributed.strategy_key=single_device" in rendered["gpu"].stdout
    for target, strategy in (
        ("ddp", "distributed_data_parallel"),
        ("fsdp2", "fully_sharded_data_parallel"),
    ):
        assert "torchrun" in rendered[target].stdout
        assert "--nproc-per-node 2" in rendered[target].stdout
        assert "--module autovla.cli.train" in rendered[target].stdout
        assert f"training.distributed.strategy_key={strategy}" in rendered[target].stdout
        assert "training.max_steps=2" in rendered[target].stdout
    assert all("HF_HUB_OFFLINE=1" in result.stdout for result in rendered.values())


def test_renderer_should_reject_missing_config_and_output_paths(tmp_path: Path) -> None:
    """验证执行前缺失配置或生成输出目录会 fail closed。"""
    _, requests = _generated_runtime(tmp_path)
    request = json.loads(requests["cpu"].read_text(encoding="utf-8"))
    request["config_path"] = str(requests["cpu"].parent / "missing.yaml")
    bad_config = requests["cpu"].parent / "bad-config.json"
    bad_config.write_text(json.dumps(request), encoding="utf-8")
    assert _render(bad_config).returncode != 0
    request["config_path"] = json.loads(requests["cpu"].read_text(encoding="utf-8"))["config_path"]
    request["output_dir"] = str(requests["cpu"].parent / "missing-output")
    bad_output = requests["cpu"].parent / "bad-output.json"
    bad_output.write_text(json.dumps(request), encoding="utf-8")
    assert _render(bad_output).returncode != 0


def test_slurm_entry_should_use_project_wrapper_and_real_m6_job(tmp_path: Path) -> None:
    """验证默认 dry-run 进入批准 wrapper,且专用 job 执行请求 launcher。"""
    _, requests = _generated_runtime(tmp_path)
    wrapper = ROOT / "scripts/slurm/render_m6_runtime_job.sh"
    result = subprocess.run(
        [
            "bash",
            str(wrapper),
            "--target",
            "gpu",
            "--request",
            str(requests["gpu"]),
            "--run-id",
            f"m6-wrapper-{tmp_path.parent.name}-{tmp_path.name}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "DRY RUN: no job submitted" in result.stdout
    assert "scripts/slurm/m6_runtime_job.sbatch" in result.stdout
    assert str(requests["gpu"]) in result.stdout
    source = wrapper.read_text(encoding="utf-8")
    job_source = (ROOT / "scripts/slurm/m6_runtime_job.sbatch").read_text(encoding="utf-8")
    assert "submit_sandbox_job.sh" in source
    assert not any(line.lstrip().startswith("sbatch ") for line in source.splitlines())
    assert "torchrun" not in source
    assert "template_job.sbatch" not in source
    assert "mock_autovla_task" not in job_source
    assert "run_m6_runtime_request.py" in job_source


def test_runtime_evidence_schema_should_require_command_and_status_fields() -> None:
    """验证 AC7 证据 schema 绑定命令、环境分类和状态 token。"""
    schema = json.loads(
        (ROOT / "configs/runtime/m6-runtime-evidence.schema.json").read_text(encoding="utf-8")
    )
    required = set(schema["required"])
    assert {"command", "runtime", "status", "status_tokens", "return_code"} <= required
    assert schema["properties"]["target"]["enum"] == ["cpu", "gpu", "ddp", "fsdp2"]
    token_rules = schema["properties"]["status_tokens"]
    required_tokens = {rule["contains"]["const"] for rule in token_rules["allOf"]}
    assert required_tokens == {
        "NO_BACKEND_WINNER",
        "OFFICIAL_GR00T_CHECKPOINT_VALIDATION_DEFERRED_LOCAL_ASSET_ABSENT",
        "OFFICIAL_ASSET_PARITY_NOT_RUN_LOCAL_ASSET_ABSENT",
    }
    assert token_rules["minItems"] == 3
    assert token_rules["uniqueItems"] is True


def _fake_torch_module(root: Path) -> Path:
    """写入不访问真实 Torch/CUDA 的最小能力探针模块。"""
    modules = root / "fake-modules"
    modules.mkdir()
    (modules / "torch.py").write_text(
        """
class _Cuda:
    @staticmethod
    def is_available():
        return False

    @staticmethod
    def device_count():
        return 0

cuda = _Cuda()
__version__ = "0.test"
""".lstrip(),
        encoding="utf-8",
    )
    return modules


def _fake_runtime(path: Path, body: str) -> Path:
    """写入一个可执行但不启动训练的测试进程。"""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o700)
    return path


@pytest.mark.parametrize(
    ("target", "runtime_body", "expected_code", "detail", "extra_token"),
    (
        ("cpu", "#!/bin/sh\nexit 0\n", 0, "", None),
        (
            "cpu",
            "#!/bin/sh\nexit 7\n",
            7,
            "runtime command failed with exit code 7",
            None,
        ),
        (
            "cpu",
            "#!/definitely/missing/autovla-interpreter\n",
            127,
            "runtime executable failure",
            "RUNTIME_EXECUTABLE_UNAVAILABLE",
        ),
        (
            "gpu",
            "#!/bin/sh\nexit 0\n",
            2,
            "runtime capability failure",
            "RUNTIME_DEVICE_OR_TORCH_UNAVAILABLE",
        ),
    ),
)
def test_runtime_process_code_and_evidence_are_exact(
    tmp_path: Path,
    target: str,
    runtime_body: str,
    expected_code: int,
    detail: str,
    extra_token: str | None,
) -> None:
    """验证成功、设备、可执行文件和普通命令状态完全一致。"""
    _, requests = _generated_runtime(tmp_path)
    request_path = requests[target]
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["runtime_python"] = str(
        _fake_runtime(request_path.parent / "fake-runtime", runtime_body)
    )
    request_path.write_text(json.dumps(request), encoding="utf-8")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(_fake_torch_module(request_path.parent))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime/run_m6_runtime_request.py"),
            "--request",
            str(request_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    evidence = json.loads(Path(request["evidence_json"]).read_text(encoding="utf-8"))
    assert result.returncode == expected_code
    assert evidence["return_code"] == expected_code
    assert evidence["status"] == ("PASS" if expected_code == 0 else "FAIL")
    assert detail in result.stderr
    expected_tokens = {
        "NO_BACKEND_WINNER",
        "OFFICIAL_GR00T_CHECKPOINT_VALIDATION_DEFERRED_LOCAL_ASSET_ABSENT",
        "OFFICIAL_ASSET_PARITY_NOT_RUN_LOCAL_ASSET_ABSENT",
    }
    assert expected_tokens <= set(evidence["status_tokens"])
    if extra_token is not None:
        assert extra_token in evidence["status_tokens"]
