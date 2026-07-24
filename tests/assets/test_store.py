"""纯标准库模型资产 store、resolver、provider 与 CLI 测试。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import autovla.assets.providers as asset_providers
import autovla.assets.store as asset_store
import autovla.cli.assets as asset_cli
from autovla.assets import (
    GR00T_N1D6_ASSET_SPEC,
    GR00T_N1D6_EAGLE_SUPPORT_SPEC,
    Gr00tModelAssetBundle,
    HuggingFaceModelAssetProvider,
    ImmutableJsonValue,
    LocalModelAssetProvider,
    MissingModelAssetError,
    ModelAssetAcquisition,
    ModelAssetContainmentError,
    ModelAssetFile,
    ModelAssetIntegrityError,
    ModelAssetLockError,
    ModelAssetManifest,
    ModelAssetProviderError,
    ModelAssetRegistry,
    ModelAssetResolver,
    ModelAssetSpec,
    ModelAssetStore,
    ResolvedModelAsset,
    StaleModelAssetLockError,
    resolve_model_asset_root,
)

_LICENSE = b"test-only license\n"
_TIMESTAMP = "2026-07-14T00:00:00Z"


def _spec(
    content: bytes = b"asset",
    *,
    provider: str = "local",
) -> ModelAssetSpec:
    """构造含许可和微型权重的固定离线测试规范。"""

    return ModelAssetSpec(
        key="tiny",
        family_key="tiny_family",
        provider=provider,
        source_url="https://example.invalid/offline/tiny",
        public_identifier="offline/tiny",
        repository="offline/tiny",
        revision="1" * 40,
        license_name="Test-Only",
        license_file_path="LICENSE",
        use_limitation="tests only",
        redistribution="not applicable",
        checksum_policy="sha256-size-v1",
        files=(
            ModelAssetFile(
                path="LICENSE",
                size=len(_LICENSE),
                sha256=hashlib.sha256(_LICENSE).hexdigest(),
                role="license",
            ),
            ModelAssetFile(
                path="weights/tiny.bin",
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                role="base_model_weights",
            ),
        ),
    )


def _acquisition(marker: str = "first") -> ModelAssetAcquisition:
    """构造严格、递归不可变的测试 acquisition。"""

    return ModelAssetAcquisition(
        provider_version="test-provider-1.0",
        downloader_version="test-downloader-1.0",
        provider_metadata={
            "marker": marker,
            "resume": True,
            "nested": {"attempts": (1, 2)},
        },
    )


def _manifest(
    spec: ModelAssetSpec,
    *,
    timestamp: str = _TIMESTAMP,
    marker: str = "first",
) -> ModelAssetManifest:
    """构造带动态获取证据的测试完成清单。"""

    return ModelAssetManifest.from_spec(
        spec,
        acquired_at_utc=timestamp,
        acquisition=_acquisition(marker),
    )


def _source(root: Path, content: bytes = b"asset") -> Path:
    """写入 provider 使用的微型源文件。"""

    root.mkdir(parents=True, exist_ok=True)
    (root / "LICENSE").write_bytes(_LICENSE)
    path = root / "weights" / "tiny.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return root


def _set_runtime_attribute(target: object, name: str, value: object) -> None:
    """通过运行时字段名触发 frozen dataclass 写保护。"""

    setattr(target, name, value)


def _set_runtime_item(target: object, key: object, value: object) -> None:
    """通过运行时协议触发不可变 mapping 的写保护。"""

    try:
        setter: object = getattr(target, "__set" + "item__")
    except AttributeError as exc:
        raise TypeError("mapping does not expose item assignment") from exc
    if not callable(setter):
        raise TypeError("mapping item assignment is not callable")
    cast(Callable[[object, object], None], setter)(key, value)


def test_manifest_is_strict_immutable_and_separates_dynamic_identity() -> None:
    """动态 provenance 不改变 spec identity,JSON 元数据和字段都不可变。"""

    spec = _spec()
    first = _manifest(spec)
    second = _manifest(spec, timestamp="2026-07-14T00:00:01Z", marker="second")
    assert first.spec_identity == second.spec_identity == spec.identity
    assert first.to_dict() != second.to_dict()
    assert ModelAssetManifest.from_dict(first.to_dict()) == first
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        first.to_dict(), sort_keys=True
    )
    with pytest.raises(FrozenInstanceError):
        _set_runtime_attribute(first, "key", "other")
    with pytest.raises(TypeError):
        _set_runtime_item(first.provider_metadata, "new", "value")
    nested = first.provider_metadata["nested"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        _set_runtime_item(nested, "attempts", (3,))
    payload = first.to_dict()
    payload["unknown"] = True
    with pytest.raises(ValueError, match="fields are not exact"):
        ModelAssetManifest.from_dict(payload)
    invalid_metadata = first.to_dict()
    invalid_metadata["provider_metadata"] = {"bad": float("nan")}
    with pytest.raises(ValueError, match="finite"):
        ModelAssetManifest.from_dict(invalid_metadata)


def test_manifest_rejects_invalid_contract_and_acquisition_fields() -> None:
    """清单对静态契约、动态 acquisition 与验证状态逐类 fail closed。"""

    manifest = _manifest(_spec())
    mutations: Mapping[str, object] = {
        "source_url": "https://example.invalid/tiny?token=secret",
        "license_file_path": "MISSING-LICENSE",
        "checksum_policy": "sha1",
        "asset_roles": ["license"],
        "remote_code_required": True,
        "acquired_at_utc": "2026-07-14T00:00:00+00:00",
        "provider_version": "unsafe version",
        "verification_state": "pending",
    }
    for field, invalid in mutations.items():
        payload = manifest.to_dict()
        payload[field] = invalid
        with pytest.raises(ValueError):
            ModelAssetManifest.from_dict(payload)


def test_root_precedence_explicit_then_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """显式 root 覆盖环境变量,环境变量覆盖仓库共享默认。"""

    environment = tmp_path / "environment"
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("AUTOVLA_MODEL_HOME", str(environment))
    assert resolve_model_asset_root(explicit) == explicit.resolve()
    assert resolve_model_asset_root() == environment.resolve()


def test_relative_escape_and_store_symlink_escape_are_rejected(tmp_path: Path) -> None:
    """规范拒绝 ``..``,store 拒绝指向根外的符号链接。"""

    with pytest.raises(ValueError, match="unsafe"):
        ModelAssetFile("../escape", 0, "0" * 64, "base_model_weights")
    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    root = store.asset_path(spec)
    root.mkdir(parents=True)
    (root / "LICENSE").write_bytes(_LICENSE)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"asset")
    member = root / "weights" / "tiny.bin"
    member.parent.mkdir()
    member.symlink_to(outside)
    (root / ".autovla-asset.json").write_text(
        json.dumps(_manifest(spec).to_dict()), encoding="utf-8"
    )
    with pytest.raises((ModelAssetContainmentError, ModelAssetIntegrityError)):
        store.verify(spec)


def test_local_provider_rejects_parent_directory_symlink_escape(tmp_path: Path) -> None:
    """本地 provider 不允许父目录 symlink 把成员解析到 declared root 外。"""

    source = tmp_path / "source"
    source.mkdir()
    (source / "LICENSE").write_bytes(_LICENSE)
    outside = tmp_path / "outside"
    (outside / "tiny.bin").parent.mkdir(parents=True)
    (outside / "tiny.bin").write_bytes(b"asset")
    (source / "weights").symlink_to(outside, target_is_directory=True)
    store = ModelAssetStore(tmp_path / "store")
    with pytest.raises(ModelAssetProviderError, match="escapes declared root"):
        store.fetch(_spec(), LocalModelAssetProvider(source))
    assert not store.asset_path(_spec()).exists()


def test_resolver_never_calls_provider_and_missing_error_has_fetch_command(
    tmp_path: Path,
) -> None:
    """普通 resolve 只读本地,并返回精确显式 fetch 命令。"""

    resolver = ModelAssetResolver(ModelAssetStore(tmp_path), ModelAssetRegistry((_spec(),)))
    with pytest.raises(MissingModelAssetError) as error:
        resolver.resolve("tiny")
    assert "autovla-assets fetch tiny" in str(error.value)


def test_explicit_local_fetch_rehashes_receipt_before_each_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """发布与后续消费都完整哈希,receipt 不会掩盖同名文件替换。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    provider = LocalModelAssetProvider(_source(tmp_path / "source"))
    original = cast(
        Callable[[Path], str],
        getattr(asset_store, "_sha" + "256"),
    )
    hashed: list[str] = []

    def _counted(path: Path) -> str:
        """记录摘要调用并复用真实流式实现。"""

        hashed.append(path.name)
        return original(path)

    monkeypatch.setattr(asset_store, "_sha" + "256", _counted)
    resolved = store.fetch(spec, provider)
    assert resolved.root == store.asset_path(spec)
    assert resolved.identity == spec.identity
    assert sorted(hashed) == ["LICENSE", "tiny.bin"]
    store.validate_resolved(resolved, spec)
    assert sorted(hashed) == ["LICENSE", "LICENSE", "tiny.bin", "tiny.bin"]

    # 同大小同名替换必须被 fresh SHA256 复核拒绝。
    (resolved.root / "weights/tiny.bin").write_bytes(b"other")
    with pytest.raises(ModelAssetIntegrityError, match="sha256 mismatch"):
        store.validate_resolved(resolved, spec)
    assert not tuple((store.root / ".staging").iterdir())


def test_digest_failure_does_not_publish_final_directory(tmp_path: Path) -> None:
    """摘要失败只清理本次 staging,不产生不完整最终目录。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    provider = LocalModelAssetProvider(_source(tmp_path / "source", b"wrong"))
    with pytest.raises(ModelAssetIntegrityError, match="digest mismatch"):
        store.fetch(spec, provider)
    assert not store.asset_path(spec).exists()


def test_huggingface_cache_is_persistent_contained_and_not_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fake HF 成功保留 store cache,final/staging 不含 provider cache。"""

    spec = _spec(provider="huggingface")
    store = ModelAssetStore(tmp_path / "store")
    cache = store.provider_cache_root("huggingface")

    def _snapshot_download(
        *,
        repo_id: str,
        revision: str,
        cache_dir: str,
        allow_patterns: list[str],
    ) -> str:
        """在显式 cache 内构造可复制的假 snapshot。"""

        assert (repo_id, revision) == (spec.repository, spec.revision)
        assert allow_patterns == [item.path for item in spec.files]
        cache_root = Path(cache_dir)
        (cache_root / "resume.marker").write_text("kept", encoding="utf-8")
        return str(_source(cache_root / "snapshots" / revision))

    module = SimpleNamespace(__version__="0.25.1", snapshot_download=_snapshot_download)

    def _import_module(name: str) -> object:
        """只允许测试触发预期的 lazy import。"""

        assert name == "huggingface_hub"
        return module

    monkeypatch.setattr(asset_providers.importlib, "import_module", _import_module)
    resolved = store.fetch(spec, HuggingFaceModelAssetProvider(cache))
    assert (cache / "resume.marker").read_text(encoding="utf-8") == "kept"
    assert resolved.manifest.provider_version == "0.25.1"
    assert not any(path.name == ".cache" for path in resolved.root.rglob("*"))
    assert not tuple((store.root / ".staging").iterdir())


def test_huggingface_failure_retains_cache_and_redacts_raw_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fake HF 失败保留 resume cache,同时错误不回显 token 或 signed URL。"""

    spec = _spec(provider="huggingface")
    store = ModelAssetStore(tmp_path / "store")
    cache = store.provider_cache_root("huggingface")

    def _snapshot_download(
        *,
        repo_id: str,
        revision: str,
        cache_dir: str,
        allow_patterns: list[str],
    ) -> str:
        """写入恢复标记后模拟包含敏感文本的 provider 故障。"""

        assert repo_id and revision and allow_patterns
        Path(cache_dir, "resume.marker").write_text("partial", encoding="utf-8")
        raise RuntimeError("https://signed.invalid/file?token=TOP_SECRET")

    module = SimpleNamespace(__version__="0.25.1", snapshot_download=_snapshot_download)

    def _import_module(name: str) -> object:
        """返回不执行网络的 fake HF 模块。"""

        assert name == "huggingface_hub"
        return module

    monkeypatch.setattr(asset_providers.importlib, "import_module", _import_module)
    with pytest.raises(ModelAssetProviderError) as error:
        store.fetch(spec, HuggingFaceModelAssetProvider(cache))
    rendered = str(error.value)
    assert "TOP_SECRET" not in rendered and "signed.invalid" not in rendered
    assert (cache / "resume.marker").exists()
    assert not store.asset_path(spec).exists()
    assert not tuple((store.root / ".staging").iterdir())


def test_huggingface_snapshot_must_remain_inside_store_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fake HF 返回 cache 外 snapshot 时 fail closed 且不发布资产。"""

    spec = _spec(provider="huggingface")
    store = ModelAssetStore(tmp_path / "store")
    outside = _source(tmp_path / "outside-snapshot")

    def _snapshot_download(
        *,
        repo_id: str,
        revision: str,
        cache_dir: str,
        allow_patterns: list[str],
    ) -> str:
        """返回故意逃逸专用 cache 的 snapshot。"""

        assert repo_id and revision and cache_dir and allow_patterns
        return str(outside)

    module = SimpleNamespace(__version__="0.25.1", snapshot_download=_snapshot_download)

    def _import_module(name: str) -> object:
        """返回 snapshot containment 测试模块。"""

        assert name == "huggingface_hub"
        return module

    monkeypatch.setattr(asset_providers.importlib, "import_module", _import_module)
    with pytest.raises(ModelAssetProviderError, match="escaped"):
        store.fetch(
            spec,
            HuggingFaceModelAssetProvider(store.provider_cache_root("huggingface")),
        )
    assert not store.asset_path(spec).exists()
    assert not tuple((store.root / ".staging").iterdir())


def test_huggingface_cache_constructor_rejects_non_store_layout(tmp_path: Path) -> None:
    """HF provider 只接受绝对 ``.cache/huggingface`` 专用位置。"""

    with pytest.raises(ModelAssetProviderError, match=r"\.cache/huggingface"):
        HuggingFaceModelAssetProvider(tmp_path / "cache")


def test_huggingface_cache_must_belong_to_selected_store(tmp_path: Path) -> None:
    """形状正确但属于另一根的 HF cache 也必须在下载前拒绝。"""

    spec = _spec(provider="huggingface")
    store = ModelAssetStore(tmp_path / "store")
    outside_cache = tmp_path / "other-store" / ".cache" / "huggingface"
    provider = HuggingFaceModelAssetProvider(outside_cache)
    with pytest.raises(ModelAssetProviderError, match="belong to this model asset store"):
        store.fetch(spec, provider)
    assert not store.asset_path(spec).exists()


def test_provider_cache_directory_cannot_pollute_staging_or_final(tmp_path: Path) -> None:
    """即使 cache 为空,provider 也不能把它混入 staging 或最终资产。"""

    spec = _spec()
    source = _source(tmp_path / "source")

    class _PollutingProvider:
        """复制规范文件后故意创建未注册的空 cache 目录。"""

        name = "local"

        def fetch(
            self,
            spec: ModelAssetSpec,
            destination: Path,
        ) -> ModelAssetAcquisition:
            """返回合法 acquisition,但留下应被目录清单拒绝的污染。"""

            acquisition = LocalModelAssetProvider(source).fetch(spec, destination)
            (destination / ".cache" / "huggingface").mkdir(parents=True)
            return acquisition

    store = ModelAssetStore(tmp_path / "store")
    with pytest.raises(ModelAssetIntegrityError, match="directories differ"):
        store.fetch(spec, _PollutingProvider())
    assert not store.asset_path(spec).exists()
    assert not tuple((store.root / ".staging").iterdir())


def test_lock_write_failure_closes_fd_and_preserves_replacement_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁初始化失败关闭本 fd,且 inode 已替换时不删除他人锁。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    lock = store.root / ".locks" / "tiny.lock"
    real_close = asset_store.os.close
    closed: list[int] = []

    def _close(descriptor: int) -> None:
        """记录 fd 关闭并调用真实实现。"""

        closed.append(descriptor)
        real_close(descriptor)

    def _fail_write(descriptor: int, data: bytes) -> int:
        """替换 lock inode 后模拟底层写失败。"""

        assert descriptor >= 0 and data
        lock.unlink()
        lock.write_text("owner=other\n", encoding="utf-8")
        raise OSError("simulated write failure")

    monkeypatch.setattr(asset_store.os, "close", _close)
    monkeypatch.setattr(asset_store.os, "write", _fail_write)
    provider = LocalModelAssetProvider(_source(tmp_path / "source"))
    with pytest.raises(ModelAssetLockError, match="initialize"):
        store.fetch(spec, provider)
    assert len(closed) == 1
    assert lock.read_text(encoding="utf-8") == "owner=other\n"


def test_lock_fsync_failure_closes_fd_and_removes_only_owned_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁 fsync 失败时关闭描述符并删除仍匹配本上下文 inode 的锁。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    lock = store.root / ".locks" / "tiny.lock"
    real_close = asset_store.os.close
    closed: list[int] = []

    def _close(descriptor: int) -> None:
        """记录关闭并调用真实实现。"""

        closed.append(descriptor)
        real_close(descriptor)

    def _fail_fsync(descriptor: int) -> None:
        """只在 lock 初始化阶段模拟底层 fsync 故障。"""

        assert descriptor >= 0
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(asset_store.os, "close", _close)
    monkeypatch.setattr(asset_store.os, "fsync", _fail_fsync)
    provider = LocalModelAssetProvider(_source(tmp_path / "source"))
    with pytest.raises(ModelAssetLockError, match="initialize"):
        store.fetch(spec, provider)
    assert len(closed) == 1
    assert not lock.exists()


def test_stale_lock_fails_closed_without_automatic_deletion(tmp_path: Path) -> None:
    """陈旧锁给出独立错误且不得擅自删除。"""

    spec = _spec()
    store = ModelAssetStore(tmp_path / "store")
    lock = store.root / ".locks" / "tiny.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("owner=unknown\n", encoding="utf-8")
    old = time.time() - 10
    os.utime(lock, (old, old))
    provider = LocalModelAssetProvider(_source(tmp_path / "source"))
    with pytest.raises(StaleModelAssetLockError, match="inspect before removing"):
        store.fetch(spec, provider, lock_timeout_seconds=0, stale_after_seconds=1)
    assert lock.exists()


def test_cli_fetch_revision_is_exact_and_provider_errors_are_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 拒绝 moving/mismatch revision,并控制 JSON provider 错误文本。"""

    spec = _spec(provider="huggingface")
    monkeypatch.setattr(asset_cli, "DEFAULT_MODEL_ASSET_REGISTRY", ModelAssetRegistry((spec,)))

    def _must_not_construct(cache_root: Path) -> HuggingFaceModelAssetProvider:
        """revision 失败必须发生在 provider 构造之前。"""

        raise AssertionError(f"provider unexpectedly constructed at {cache_root}")

    monkeypatch.setattr(asset_cli, "HuggingFaceModelAssetProvider", _must_not_construct)
    result = asset_cli.main(
        [
            "--root",
            str(tmp_path / "mismatch"),
            "--json",
            "fetch",
            "tiny",
            "--revision",
            "main",
        ]
    )
    mismatch = capsys.readouterr().out
    assert result == 2 and "registry pin" in mismatch

    class _ExplodingProvider:
        """模拟抛出含敏感 URL 的非受控第三方 provider。"""

        name = "huggingface"

        def __init__(self, cache_root: Path) -> None:
            """保留 store 明确传入的专用 cache 根。"""

            self.cache_root = cache_root

        def fetch(
            self,
            selected: ModelAssetSpec,
            destination: Path,
        ) -> ModelAssetAcquisition:
            """在测试中抛出必须由 store 收口的原始异常。"""

            assert selected == spec and destination.is_dir()
            raise RuntimeError("token=TOP_SECRET https://signed.invalid/private")

    def _exploding(cache_root: Path) -> _ExplodingProvider:
        """返回不访问网络的故障 provider。"""

        assert cache_root.name == "huggingface"
        return _ExplodingProvider(cache_root)

    monkeypatch.setattr(asset_cli, "HuggingFaceModelAssetProvider", _exploding)
    result = asset_cli.main(
        [
            "--root",
            str(tmp_path / "redacted"),
            "--json",
            "fetch",
            "tiny",
            "--revision",
            spec.revision,
        ]
    )
    failure = capsys.readouterr().out
    assert result == 2
    assert "TOP_SECRET" not in failure and "signed.invalid" not in failure
    result = asset_cli.main(
        [
            "--root",
            str(tmp_path / "redacted-human"),
            "fetch",
            "tiny",
            "--revision",
            spec.revision,
        ]
    )
    human_failure = capsys.readouterr().out
    assert result == 2
    assert "TOP_SECRET" not in human_failure and "signed.invalid" not in human_failure


def test_cli_inspect_exposes_complete_immutable_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """inspect JSON 暴露 family、公开来源、许可、角色和 checksum policy。"""

    spec = _spec(provider="huggingface")
    monkeypatch.setattr(asset_cli, "DEFAULT_MODEL_ASSET_REGISTRY", ModelAssetRegistry((spec,)))
    result = asset_cli.main(["--root", str(tmp_path / "store"), "--json", "inspect", "tiny"])
    payload = json.loads(capsys.readouterr().out)["result"]
    assert result == 0
    assert payload["family_key"] == spec.family_key
    assert payload["source_url"] == spec.source_url
    assert payload["public_identifier"] == spec.public_identifier
    assert payload["license_file_path"] == spec.license_file_path
    assert payload["checksum_policy"] == spec.checksum_policy
    assert payload["asset_roles"] == list(spec.asset_roles)


def test_cli_list_preserves_registered_asset_inventory_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """list 保留既有资产清单字段和值,不改作模型族状态列表。"""

    spec = _spec(provider="huggingface")
    monkeypatch.setattr(asset_cli, "DEFAULT_MODEL_ASSET_REGISTRY", ModelAssetRegistry((spec,)))
    result = asset_cli.main(["--root", str(tmp_path / "store"), "--json", "list"])
    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload == {
        "ok": True,
        "result": [
            {
                "key": spec.key,
                "family_key": spec.family_key,
                "provider": spec.provider,
                "source_url": spec.source_url,
                "public_identifier": spec.public_identifier,
                "repository": spec.repository,
                "revision": spec.revision,
                "license": spec.license_name,
            }
        ],
    }


def test_cli_matching_revision_can_use_explicit_fake_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """匹配 registry pin 的 CLI fetch 可通过显式 fake provider 离线完成。"""

    spec = _spec(provider="huggingface")
    source = _source(tmp_path / "source")
    monkeypatch.setattr(asset_cli, "DEFAULT_MODEL_ASSET_REGISTRY", ModelAssetRegistry((spec,)))

    def _local_provider(cache_root: Path) -> LocalModelAssetProvider:
        """忽略未创建的 cache,仅复制显式本地 fixture。"""

        assert cache_root.name == "huggingface"
        return LocalModelAssetProvider(source)

    monkeypatch.setattr(asset_cli, "HuggingFaceModelAssetProvider", _local_provider)
    result = asset_cli.main(
        [
            "--root",
            str(tmp_path / "store"),
            "--json",
            "fetch",
            "tiny",
            "--revision",
            spec.revision,
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert result == 0 and payload["ok"] is True
    assert payload["result"]["identity"] == spec.identity


def test_official_spec_is_exactly_pinned_and_no_heavy_imports() -> None:
    """官方 spec 固定来源、角色、许可、摘要且资产包无重依赖导入。"""

    spec = GR00T_N1D6_ASSET_SPEC
    assert spec.family_key == "gr00t_n1d6"
    assert spec.source_url == "https://huggingface.co/nvidia/GR00T-N1.6-3B"
    assert spec.public_identifier == spec.repository == "nvidia/GR00T-N1.6-3B"
    assert spec.revision == "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61"
    assert spec.license_name == "NVIDIA License" and spec.license_file_path == "LICENSE"
    assert spec.checksum_policy == "sha256-size-v1"
    assert "license" in spec.asset_roles and "base_model_weights" in spec.asset_roles
    assert spec.remote_code_required is False
    shards = [item for item in spec.files if item.path.endswith("safetensors")]
    assert [(item.size, item.sha256, item.role) for item in shards] == [
        (
            4991091456,
            "9710d31d331b79cfa229fd23605ba9ad47e207cb0f4c7722fe0bacdc666c8326",
            "base_model_weights",
        ),
        (
            1582283096,
            "eb79bbd7893068897cda18c86ed91064e92e20e356dea97bc398bf9c8bf2fa35",
            "base_model_weights",
        ),
    ]
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import autovla.assets; "
                "assert not {'torch','transformers','huggingface_hub'} & set(sys.modules)"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr


def test_provider_metadata_type_is_narrow_json_mapping() -> None:
    """类型化 provider 元数据只包含严格 JSON-safe 不可变值。"""

    metadata: Mapping[str, ImmutableJsonValue] = _acquisition().provider_metadata
    assert metadata["resume"] is True
    assert metadata["nested"] == {"attempts": (1, 2)}


def test_gitignore_protects_model_assets() -> None:
    """仓库忽略模型根和 checkpoint 根,防止资产污染候选。"""

    text = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "base_model/" in text
    assert "checkpoints/" in text


def test_eagle_support_spec_is_complete_non_executable_and_bundle_is_typed() -> None:
    """Eagle 规范覆盖支持数据与许可,且双收据身份不可互换。"""

    spec = GR00T_N1D6_EAGLE_SUPPORT_SPEC
    expected = {
        "LICENSE",
        "config.json",
        "preprocessor_config.json",
        "processor_config.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "added_tokens.json",
        "chat_template.json",
        "generation_config.json",
    }
    assert {Path(item.path).name for item in spec.files} == expected
    assert all(not item.path.endswith(".py") for item in spec.files)
    assert spec.remote_code_required is False
    assert spec.revision == "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"
    with pytest.raises((TypeError, ValueError)):
        Gr00tModelAssetBundle(
            base_checkpoint=cast(ResolvedModelAsset, object()),
            eagle_support=cast(ResolvedModelAsset, object()),
        )
