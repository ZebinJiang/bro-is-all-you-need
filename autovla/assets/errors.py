"""AutoVLA 模型资产错误类型。"""

from __future__ import annotations


class ModelAssetError(RuntimeError):
    """模型资产操作的公共错误基类。"""


class ModelAssetConfigurationError(ModelAssetError, ValueError):
    """资产配置、路径或注册信息不合法。"""


class MissingModelAssetError(ModelAssetError, FileNotFoundError):
    """本地不存在已注册且验证完成的模型资产。"""

    def __init__(self, asset_key: str, detail: str) -> None:
        """给出不会被误解为隐式下载的修复命令。"""

        super().__init__(
            f"model asset {asset_key!r} is unavailable: {detail}; "
            f"run `autovla-assets fetch {asset_key}` explicitly"
        )
        self.asset_key = asset_key


class ModelAssetIntegrityError(ModelAssetError):
    """资产清单、文件大小或摘要与固定规范不一致。"""


class ModelAssetContainmentError(ModelAssetError):
    """资产路径、符号链接或 provider 输出逃逸受管根目录。"""


class ModelAssetLockError(ModelAssetError):
    """显式 fetch 无法在有界时间内取得资产锁。"""


class StaleModelAssetLockError(ModelAssetLockError):
    """资产锁已超过允许年龄,需要人工确认后清理。"""


class ModelAssetProviderError(ModelAssetError):
    """显式 provider 获取失败或 provider 与规范不兼容。"""


class ModelAssetAuthorizationError(ModelAssetError, PermissionError):
    """访问、条款、获取或验证收据不足以授权本地解析。"""

    def __init__(self, asset_key: str, blocker: str) -> None:
        """仅公开稳定 blocker,不回显外部收据内容。"""

        super().__init__(
            f"model asset {asset_key!r} is not authorized: {blocker}; "
            "inspect `autovla-assets terms` before retrying"
        )
        self.asset_key = asset_key
        self.blocker = blocker
