"""模型资产显式获取 provider；模块导入不加载网络依赖。"""

from __future__ import annotations

import importlib
import re
import shutil
from pathlib import Path

from autovla.assets.contracts import ModelAssetAcquisition, ModelAssetSpec
from autovla.assets.errors import ModelAssetProviderError

_SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")


class LocalModelAssetProvider:
    """从显式本地目录复制规范文件，主要用于离线迁移与测试。"""

    name = "local"

    def __init__(self, source: Path) -> None:
        """记录现有本地源目录，不接受隐式搜索路径。"""

        self.source = source.expanduser().resolve(strict=True)
        if not self.source.is_dir():
            raise ModelAssetProviderError("local model asset source must be a directory")

    def fetch(self, spec: ModelAssetSpec, destination: Path) -> ModelAssetAcquisition:
        """逐文件复制固定规范成员并拒绝任一父路径的 symlink 逃逸。"""

        destination_root = destination.resolve(strict=True)
        for item in spec.files:
            source = self._contained_source(item.path)
            target = destination_root.joinpath(*item.path.split("/"))
            if not _is_relative_to(target.resolve(strict=False), destination_root):
                raise ModelAssetProviderError("local provider destination escaped staging")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target, follow_symlinks=False)
        return ModelAssetAcquisition(
            provider_version="autovla-local-v1",
            downloader_version="python-shutil",
            provider_metadata={
                "backend": "local",
                "copied_file_count": len(spec.files),
                "source_containment_verified": True,
            },
        )

    def _contained_source(self, relative: str) -> Path:
        """逐段解析源路径并要求每个解析结果仍位于 declared root。"""

        current = self.source
        resolved = self.source
        for part in relative.split("/"):
            current = current / part
            try:
                resolved = current.resolve(strict=True)
            except OSError:
                raise ModelAssetProviderError(
                    f"local provider required file is unavailable: {relative}"
                ) from None
            if not _is_relative_to(resolved, self.source):
                raise ModelAssetProviderError(
                    f"local provider source escapes declared root: {relative}"
                )
        if not resolved.is_file():
            raise ModelAssetProviderError(
                f"local provider required file is unavailable: {relative}"
            )
        return resolved


class HuggingFaceModelAssetProvider:
    """仅由显式 fetch 调用、固定 revision 且可恢复缓存的 HF provider。"""

    name = "huggingface"

    def __init__(self, cache_root: Path) -> None:
        """绑定 store 内专用持久缓存，缓存不得位于 staging 或 final。"""

        candidate = cache_root.expanduser()
        if not candidate.is_absolute():
            raise ModelAssetProviderError("Hugging Face cache root must be absolute")
        if candidate.name != "huggingface" or candidate.parent.name != ".cache":
            raise ModelAssetProviderError(
                "Hugging Face cache root must use the store .cache/huggingface location"
            )
        self.cache_root = candidate.resolve(strict=False)

    def fetch(self, spec: ModelAssetSpec, destination: Path) -> ModelAssetAcquisition:
        """延迟导入 huggingface_hub，失败时保留 store cache 供后续 resume。"""

        if spec.provider != self.name or spec.remote_code_required:
            raise ModelAssetProviderError("Hugging Face provider/spec is incompatible")
        try:
            module = importlib.import_module("huggingface_hub")
            snapshot_download = module.snapshot_download
        except (ImportError, AttributeError):
            raise ModelAssetProviderError(
                "explicit Hugging Face fetch requires installed huggingface_hub"
            ) from None
        if not callable(snapshot_download):
            raise ModelAssetProviderError("huggingface_hub snapshot API is unavailable")
        if self.cache_root.is_symlink():
            raise ModelAssetProviderError("Hugging Face cache root must not be a symlink")
        self.cache_root.mkdir(parents=True, exist_ok=True)
        cache = self.cache_root.resolve(strict=True)
        try:
            snapshot = snapshot_download(
                repo_id=spec.repository,
                revision=spec.revision,
                cache_dir=str(cache),
                allow_patterns=[item.path for item in spec.files],
            )
            if not isinstance(snapshot, (str, Path)):
                raise ModelAssetProviderError("Hugging Face snapshot path has an invalid type")
            snapshot_root = Path(snapshot).resolve(strict=True)
            if not _is_relative_to(snapshot_root, cache):
                raise ModelAssetProviderError("Hugging Face snapshot escaped the store cache")
            destination_root = destination.resolve(strict=True)
            for item in spec.files:
                source = snapshot_root.joinpath(*item.path.split("/")).resolve(strict=True)
                if not _is_relative_to(source, cache) or not source.is_file():
                    raise ModelAssetProviderError(
                        f"Hugging Face snapshot omitted required file: {item.path}"
                    )
                target = destination_root.joinpath(*item.path.split("/"))
                if not _is_relative_to(target.resolve(strict=False), destination_root):
                    raise ModelAssetProviderError("Hugging Face destination escaped staging")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target, follow_symlinks=False)
        except ModelAssetProviderError:
            raise
        except Exception:
            raise ModelAssetProviderError(
                "explicit Hugging Face fetch failed; persistent cache was retained for resume"
            ) from None
        version = _safe_version(getattr(module, "__version__", None))
        return ModelAssetAcquisition(
            provider_version=version,
            downloader_version=version,
            provider_metadata={
                "backend": "huggingface_hub.snapshot_download",
                "cache_scope": "model_asset_store",
                "requested_file_count": len(spec.files),
                "resume_cache_retained": True,
            },
        )


def _safe_version(value: object) -> str:
    """把第三方版本收窄为不会携带 URL 或凭据的安全文本。"""

    return value if isinstance(value, str) and _SAFE_VERSION.fullmatch(value) else "unknown"


def _is_relative_to(path: Path, root: Path) -> bool:
    """兼容 Python 3.10 的 containment 判断。"""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
