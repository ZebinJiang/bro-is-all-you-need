"""本地模型资产根、完整性验证、持久 provider cache 和原子发布。"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla.assets.contracts import (
    ModelAssetAcquisition,
    ModelAssetManifest,
    ModelAssetProvider,
    ModelAssetSpec,
    ResolvedModelAsset,
    utc_acquisition_timestamp,
)
from autovla.assets.errors import (
    MissingModelAssetError,
    ModelAssetConfigurationError,
    ModelAssetContainmentError,
    ModelAssetError,
    ModelAssetIntegrityError,
    ModelAssetLockError,
    ModelAssetProviderError,
    StaleModelAssetLockError,
)

if TYPE_CHECKING:
    from autovla.assets.lifecycle import (
        AssetAccessReceipt,
        AssetAuthorizationPolicyRegistry,
        AssetLifecycleEvidence,
        AssetTermsReceipt,
        AuthorizedModelAsset,
    )
    from autovla.assets.registry import ModelAssetRegistry

MANIFEST_NAME = ".autovla-asset.json"
_SHARED_WORKSPACE = Path("/home/cz-jzb/workspace/vla-flywheel")


@runtime_checkable
class _CacheRootProvider(Protocol):
    """描述必须显式暴露持久 cache 根的 provider。"""

    cache_root: Path


def resolve_model_asset_root(explicit_root: str | Path | None = None) -> Path:
    """按 explicit、环境变量、仓库 worktree 共享根的顺序解析资产根。"""

    if explicit_root is not None:
        return _absolute_root(explicit_root, "explicit model asset root")
    environment = os.environ.get("AUTOVLA_MODEL_HOME")
    if environment:
        return _absolute_root(environment, "AUTOVLA_MODEL_HOME")
    repository = _repository_root(Path(__file__).resolve())
    shared = _SHARED_WORKSPACE.resolve(strict=False)
    worktrees = shared / ".worktrees"
    if repository == shared or _is_relative_to(repository, worktrees):
        return shared / "base_model"
    raise ModelAssetConfigurationError(
        "model asset root is unresolved; set an explicit root or AUTOVLA_MODEL_HOME"
    )


class ModelAssetStore:
    """管理受 containment 保护的本地不可变资产与 provider cache。"""

    def __init__(self, root: str | Path | None = None) -> None:
        """解析资产根但不创建目录、不下载且不导入模型运行时。"""

        self.root = resolve_model_asset_root(root)

    def asset_path(self, spec: ModelAssetSpec) -> Path:
        """返回固定 key/revision 的受管最终目录。"""

        return self._contained(self.root / spec.key / spec.revision)

    def provider_cache_root(self, provider_name: str) -> Path:
        """返回 store 内 provider 专用持久 cache,不创建目录。"""

        raw_name = cast(object, provider_name)
        if (
            not isinstance(raw_name, str)
            or not provider_name
            or not provider_name.replace("_", "").isalnum()
        ):
            raise ModelAssetConfigurationError("provider cache name must be canonical")
        return self._contained(self.root / ".cache" / provider_name)

    def read_user_receipts(
        self,
        spec: ModelAssetSpec,
    ) -> tuple[
        tuple["AssetAccessReceipt", ...],
        tuple["AssetTermsReceipt", ...],
    ]:
        """只读取忽略根内的小型用户访问/条款 JSON,不读取资产成员。"""

        from autovla.assets.lifecycle import AssetAccessReceipt, AssetTermsReceipt

        receipt_root = self._member(
            self.root,
            f".receipts/{spec.key}/{spec.revision}",
        )
        if not receipt_root.exists():
            return (), ()
        if not receipt_root.is_dir():
            raise ModelAssetIntegrityError("asset receipt root must be a directory")
        for path in receipt_root.iterdir():
            if path.name not in {"access.json", "terms"}:
                raise ModelAssetIntegrityError("asset receipt root contains an unexpected member")

        access_receipts: tuple[AssetAccessReceipt, ...] = ()
        access_path = receipt_root / "access.json"
        if access_path.exists():
            access = AssetAccessReceipt.from_dict(
                self._read_receipt_json(access_path, receipt_root)
            )
            self._require_receipt_spec(
                access.asset_key,
                access.spec_identity,
                access.revision,
                spec,
            )
            access_receipts = (access,)

        terms_receipts: list[AssetTermsReceipt] = []
        terms_root = receipt_root / "terms"
        if terms_root.exists():
            if terms_root.is_symlink() or not terms_root.is_dir():
                raise ModelAssetContainmentError(
                    "asset terms receipt root must be a real directory"
                )
            for path in sorted(terms_root.iterdir(), key=lambda item: item.name):
                if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                    raise ModelAssetIntegrityError(
                        "asset terms receipt directory contains an unexpected member"
                    )
                receipt = AssetTermsReceipt.from_dict(self._read_receipt_json(path, receipt_root))
                if path.stem != receipt.terms_kind.value:
                    raise ModelAssetIntegrityError(
                        "asset terms receipt filename does not match its kind"
                    )
                self._require_receipt_spec(
                    receipt.asset_key,
                    receipt.spec_identity,
                    receipt.revision,
                    spec,
                )
                terms_receipts.append(receipt)
        return access_receipts, tuple(terms_receipts)

    def verify(self, spec: ModelAssetSpec) -> ResolvedModelAsset:
        """流式校验清单、containment、大小与 SHA256,并签发 verified receipt。"""

        root = self.asset_path(spec)
        from autovla.assets.authorization import reusable_authorized_asset

        reusable = reusable_authorized_asset(self.root, spec)
        if reusable is not None:
            persisted = self._read_manifest(root, spec)
            if persisted != reusable.manifest:
                raise ModelAssetIntegrityError(
                    "reusable authorized asset manifest changed after verification"
                )
            self._validate_members(root, spec, verify_hashes=False)
            self._require_safe_manifest(persisted)
            return reusable
        manifest = self._read_manifest(root, spec)
        self._validate_members(root, spec, verify_hashes=True)
        self._require_safe_manifest(manifest)
        return ResolvedModelAsset.from_verified_store(root, manifest)

    def validate_resolved(
        self,
        resolved: ResolvedModelAsset,
        spec: ModelAssetSpec,
    ) -> ResolvedModelAsset:
        """复核 receipt 的根、清单、containment、大小和全部 SHA256。"""

        raw_resolved = cast(object, resolved)
        if not isinstance(raw_resolved, ResolvedModelAsset):
            raise ModelAssetIntegrityError("resolved asset receipt has an invalid type")
        resolved = raw_resolved
        expected_root = self.asset_path(spec)
        if resolved.root != expected_root:
            raise ModelAssetContainmentError("resolved asset receipt does not belong to this store")
        if resolved.manifest.to_spec() != spec:
            raise ModelAssetIntegrityError("resolved asset receipt is incompatible with registry")
        persisted = self._read_manifest(expected_root, spec)
        if persisted != resolved.manifest:
            raise ModelAssetIntegrityError("resolved asset manifest changed after verification")
        self._require_safe_manifest(persisted)
        # receipt 不是永久信任票据;每次生产消费前重新哈希,拒绝同名替换。
        self._validate_members(expected_root, spec, verify_hashes=True)
        return resolved

    def fetch(
        self,
        spec: ModelAssetSpec,
        provider: ModelAssetProvider,
        *,
        lock_timeout_seconds: float = 30.0,
        stale_after_seconds: float = 3600.0,
    ) -> ResolvedModelAsset:
        """显式获取到 staging,一次完整校验后原子发布并复用校验结果。"""

        if provider.name != spec.provider and provider.name != "local":
            raise ModelAssetProviderError("selected provider cannot fetch the registered asset")
        if provider.name == "huggingface":
            try:
                if not isinstance(provider, _CacheRootProvider):
                    raise ModelAssetProviderError(
                        "Hugging Face provider must declare the selected store cache"
                    )
                raw_cache_root = cast(object, provider.cache_root)
            except ModelAssetProviderError:
                raise
            except Exception:
                raise ModelAssetProviderError(
                    "Hugging Face provider must declare the selected store cache"
                ) from None
            expected_cache_root = self.provider_cache_root("huggingface")
            if (
                not isinstance(raw_cache_root, Path)
                or raw_cache_root.resolve(strict=False) != expected_cache_root
            ):
                raise ModelAssetProviderError(
                    "Hugging Face provider cache must belong to this model asset store"
                )
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock(spec, lock_timeout_seconds, stale_after_seconds):
            try:
                return self.verify(spec)
            except MissingModelAssetError:
                pass
            final = self.asset_path(spec)
            if final.exists():
                raise ModelAssetIntegrityError(
                    f"incomplete/incompatible final asset exists at {final}; refusing overwrite"
                )
            staging_root = self._contained(self.root / ".staging")
            staging_root.mkdir(parents=True, exist_ok=True)
            staging = self._contained(staging_root / f"{spec.key}-{uuid.uuid4().hex}")
            staging.mkdir(mode=0o700)
            try:
                try:
                    acquisition = provider.fetch(spec, staging)
                except ModelAssetError:
                    raise
                except Exception:
                    raise ModelAssetProviderError(
                        "provider fetch failed before publication; private staging was discarded"
                    ) from None
                raw_acquisition = cast(object, acquisition)
                if not isinstance(raw_acquisition, ModelAssetAcquisition):
                    raise ModelAssetProviderError(
                        "provider did not return strict acquisition metadata"
                    )
                acquisition = raw_acquisition
                self._verify_staging(spec, staging)
                manifest = ModelAssetManifest.from_spec(
                    spec,
                    acquired_at_utc=utc_acquisition_timestamp(),
                    acquisition=acquisition,
                )
                self._require_safe_manifest(manifest)
                _write_json_atomic(staging / MANIFEST_NAME, manifest.to_dict())
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, final)
            except BaseException:
                _remove_empty_or_files(staging)
                raise
            self._validate_members(final, spec, verify_hashes=False)
            return ResolvedModelAsset.from_verified_store(final, manifest)

    def _require_safe_manifest(self, manifest: ModelAssetManifest) -> None:
        """在发布和解析边界拒绝非 safetensors 权重或远端代码策略。"""

        from autovla.assets.lifecycle import AssetVerificationResult

        receipt = manifest.verification_receipt
        if receipt.result is not AssetVerificationResult.VERIFIED:
            raise ModelAssetIntegrityError(
                "model asset manifest violates safetensors-only or remote-code policy"
            )

    def _read_manifest(self, root: Path, spec: ModelAssetSpec) -> ModelAssetManifest:
        """严格读取完成清单并核对注册规范。"""

        manifest_path = root / MANIFEST_NAME
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise MissingModelAssetError(spec.key, f"missing completion manifest at {root}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = ModelAssetManifest.from_dict(payload)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            raise ModelAssetIntegrityError("invalid model asset manifest") from None
        if manifest.to_spec() != spec:
            raise ModelAssetIntegrityError(
                "local model asset manifest is incompatible with registry"
            )
        return manifest

    def _read_receipt_json(self, path: Path, receipt_root: Path) -> object:
        """严格读取受 containment 保护的小型 JSON 收据。"""

        if path.is_symlink() or not path.is_file():
            raise ModelAssetContainmentError("asset receipt must be a real file")
        resolved = self._contained(path.resolve(strict=True))
        if not _is_relative_to(resolved, receipt_root):
            raise ModelAssetContainmentError("asset receipt escaped its asset scope")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ModelAssetIntegrityError("invalid asset lifecycle receipt JSON") from None

    def _require_receipt_spec(
        self,
        asset_key: str,
        spec_identity: str,
        revision: str,
        spec: ModelAssetSpec,
    ) -> None:
        """要求用户收据与所检查规范完全一致。"""

        if asset_key != spec.key or spec_identity != spec.identity or revision != spec.revision:
            raise ModelAssetIntegrityError("asset lifecycle receipt is incompatible with registry")

    def _validate_members(
        self,
        root: Path,
        spec: ModelAssetSpec,
        *,
        verify_hashes: bool,
    ) -> None:
        """校验成员 containment/大小,并按需执行一次完整摘要读取。"""

        expected = {MANIFEST_NAME, *(item.path for item in spec.files)}
        expected_directories = _expected_directories(spec)
        actual: set[str] = set()
        actual_directories: set[str] = set()
        for candidate in root.rglob("*"):
            if candidate.is_symlink():
                raise ModelAssetContainmentError(
                    f"symlink asset path is forbidden: {candidate.relative_to(root)}"
                )
            if candidate.is_file():
                actual.add(candidate.relative_to(root).as_posix())
            elif candidate.is_dir():
                actual_directories.add(candidate.relative_to(root).as_posix())
        if actual != expected:
            raise ModelAssetIntegrityError(
                f"final asset contents differ from manifest; missing={sorted(expected-actual)}, "
                f"unexpected={sorted(actual-expected)}"
            )
        if actual_directories != expected_directories:
            raise ModelAssetIntegrityError(
                "final asset directories differ from manifest; "
                f"missing={sorted(expected_directories-actual_directories)}, "
                f"unexpected={sorted(actual_directories-expected_directories)}"
            )
        for item in spec.files:
            path = self._member(root, item.path)
            if not path.is_file() or path.is_symlink():
                raise ModelAssetIntegrityError(f"asset member is missing or symlinked: {item.path}")
            if path.stat().st_size != item.size:
                raise ModelAssetIntegrityError(f"asset size mismatch: {item.path}")
            if verify_hashes and _sha256(path) != item.sha256:
                raise ModelAssetIntegrityError(f"asset sha256 mismatch: {item.path}")

    def _verify_staging(self, spec: ModelAssetSpec, staging: Path) -> None:
        """发布前拒绝 symlink、逃逸、额外文件和摘要差异。"""

        expected = {item.path for item in spec.files}
        expected_directories = _expected_directories(spec)
        actual: set[str] = set()
        actual_directories: set[str] = set()
        for path in staging.rglob("*"):
            if path.is_symlink():
                raise ModelAssetContainmentError(f"provider created symlink: {path}")
            if path.is_file():
                actual.add(path.relative_to(staging).as_posix())
                self._contained(path.resolve(strict=True))
            elif path.is_dir():
                actual_directories.add(path.relative_to(staging).as_posix())
        if actual != expected:
            raise ModelAssetIntegrityError(
                f"provider output differs from spec; missing={sorted(expected-actual)}, "
                f"unexpected={sorted(actual-expected)}"
            )
        if actual_directories != expected_directories:
            raise ModelAssetIntegrityError(
                "provider output directories differ from spec; "
                f"missing={sorted(expected_directories-actual_directories)}, "
                f"unexpected={sorted(actual_directories-expected_directories)}"
            )
        for item in spec.files:
            path = self._member(staging, item.path)
            if path.stat().st_size != item.size or _sha256(path) != item.sha256:
                raise ModelAssetIntegrityError(f"provider output digest mismatch: {item.path}")

    @contextmanager
    def _lock(
        self,
        spec: ModelAssetSpec,
        timeout_seconds: float,
        stale_after_seconds: float,
    ) -> Generator[None, None, None]:
        """用 O_EXCL 创建有界文件锁;陈旧锁必须人工审查。"""

        _validate_lock_bounds(timeout_seconds, stale_after_seconds)
        locks = self._contained(self.root / ".locks")
        locks.mkdir(parents=True, exist_ok=True)
        lock = self._contained(locks / f"{spec.key}.lock")
        deadline = time.monotonic() + timeout_seconds
        descriptor: int | None = None
        inode: int | None = None
        while descriptor is None:
            try:
                candidate = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                try:
                    age = time.time() - lock.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > stale_after_seconds:
                    raise StaleModelAssetLockError(
                        f"stale model asset lock at {lock}; inspect before removing"
                    ) from exc
                if time.monotonic() >= deadline:
                    raise ModelAssetLockError(
                        f"timed out waiting for model asset lock {lock}"
                    ) from exc
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
                continue
            descriptor = candidate
            inode = os.fstat(descriptor).st_ino
            try:
                payload = f"pid={os.getpid()}\ntime={time.time()}\n".encode("ascii")
                if os.write(descriptor, payload) != len(payload):
                    raise OSError("short model asset lock write")
                os.fsync(descriptor)
            except OSError:
                _release_owned_lock(lock, descriptor, inode)
                descriptor = None
                inode = None
                raise ModelAssetLockError("failed to initialize model asset lock") from None
        assert descriptor is not None and inode is not None
        owned_descriptor = descriptor
        owned_inode = inode
        try:
            yield
        finally:
            _release_owned_lock(lock, owned_descriptor, owned_inode)

    def _member(self, root: Path, relative: str) -> Path:
        """逐段构造成员并拒绝父目录 symlink 逃逸。"""

        path = root.joinpath(*relative.split("/"))
        current = root
        for part in relative.split("/"):
            current = current / part
            if current.is_symlink():
                raise ModelAssetContainmentError(f"symlink asset path is forbidden: {relative}")
        return self._contained(path.resolve(strict=False))

    def _contained(self, path: Path) -> Path:
        """要求解析后的路径始终位于资产根内部。"""

        candidate = path.resolve(strict=False)
        if not _is_relative_to(candidate, self.root):
            raise ModelAssetContainmentError(f"model asset path escapes root: {path}")
        return candidate


class ModelAssetResolver:
    """保留 M11 本地验证入口,并提供独立的 M12 授权入口。"""

    def __init__(
        self,
        store: ModelAssetStore,
        registry: "ModelAssetRegistry",
        policies: "AssetAuthorizationPolicyRegistry | None" = None,
    ) -> None:
        """绑定 store、规范 registry 与显式授权策略 registry。"""

        self.store = store
        self.registry = registry
        self.policies = policies

    def resolve(
        self,
        key: str,
    ) -> ResolvedModelAsset:
        """只在本地验证一个注册资产,不要求 M12 策略且不做获取。"""

        return self.store.verify(self.registry.require(key))

    def resolve_authorized(
        self,
        key: str,
        evidence: "AssetLifecycleEvidence | None",
    ) -> "AuthorizedModelAsset":
        """先要求精确 M12 授权,再读取并复核本地 payload。"""

        from autovla.assets.errors import ModelAssetAuthorizationError
        from autovla.assets.lifecycle import AuthorizedModelAsset, require_asset_authorization

        spec = self.registry.require(key)
        if self.policies is None:
            raise ModelAssetAuthorizationError(
                spec.key,
                "ASSET_AUTHORIZATION_POLICY_MISSING",
            )
        if evidence is None:
            raise ModelAssetAuthorizationError(
                spec.key,
                "ASSET_LIFECYCLE_EVIDENCE_MISSING",
            )
        policy = self.policies.require(spec.key)
        authorization = require_asset_authorization(spec, policy, evidence)
        resolved = self.store.verify(spec)
        if resolved.acquisition_receipt.fingerprint != evidence.acquisition_receipt.fingerprint:
            raise ModelAssetAuthorizationError(
                spec.key,
                "LOCAL_ACQUISITION_RECEIPT_IDENTITY_MISMATCH",
            )
        if resolved.verification_receipt.fingerprint != evidence.verification_receipt.fingerprint:
            raise ModelAssetAuthorizationError(
                spec.key,
                "LOCAL_VERIFICATION_RECEIPT_IDENTITY_MISMATCH",
            )
        return AuthorizedModelAsset(
            resolved=resolved,
            authorization=authorization,
        )


def _absolute_root(value: str | Path, name: str) -> Path:
    """要求配置根是绝对路径,并以非严格方式规范化。"""

    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ModelAssetConfigurationError(f"{name} must be absolute")
    return path.resolve(strict=False)


def _repository_root(start: Path) -> Path:
    """从模块路径寻找真实 checkout/worktree 根。"""

    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate.resolve(strict=False)
    raise ModelAssetConfigurationError("installed package is not inside an AutoVLA repository")


def _is_relative_to(path: Path, root: Path) -> bool:
    """兼容 Python 3.10 的 containment 判断。"""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sha256(path: Path) -> str:
    """以 1 MiB 块流式计算摘要,空间复杂度保持常数。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_directories(spec: ModelAssetSpec) -> set[str]:
    """返回规范文件要求的全部父目录,拒绝隐藏 cache 或空目录污染。"""

    expected: set[str] = set()
    for item in spec.files:
        parts = item.path.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            expected.add("/".join(parts[:index]))
    return expected


def _write_json_atomic(path: Path, payload: object) -> None:
    """同目录临时文件 fsync 后原子替换 JSON。"""

    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _remove_empty_or_files(root: Path) -> None:
    """仅清理本次私有 staging,不触碰 provider cache 或最终资产。"""

    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    root.rmdir()


def _release_owned_lock(lock: Path, descriptor: int, inode: int) -> None:
    """关闭本上下文 fd,并仅在 inode 仍匹配时删除自己的锁。"""

    close_error = False
    try:
        os.close(descriptor)
    except OSError:
        close_error = True
    try:
        current = lock.lstat()
    except FileNotFoundError:
        current = None
    if current is not None and current.st_ino == inode:
        lock.unlink()
    if close_error:
        raise ModelAssetLockError("failed to close model asset lock descriptor") from None


def _validate_lock_bounds(timeout_seconds: float, stale_after_seconds: float) -> None:
    """要求锁等待和陈旧阈值为有限且类型明确的数值。"""

    values = (
        ("timeout", timeout_seconds, True),
        ("stale_after", stale_after_seconds, False),
    )
    for name, value, allow_zero in values:
        raw_value = cast(object, value)
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise ModelAssetConfigurationError(f"asset lock {name} must be numeric")
        number = float(raw_value)
        if not math.isfinite(number) or number < 0 or (not allow_zero and number == 0):
            raise ModelAssetConfigurationError("asset lock bounds must be finite and positive")
