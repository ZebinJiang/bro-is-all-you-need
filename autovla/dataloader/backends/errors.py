"""DataBackend registry 和 probe 错误类型。"""

from __future__ import annotations


class DataBackendError(ValueError):
    """DataBackend 子系统基础错误。"""


class DataBackendRegistryError(DataBackendError):
    """DataBackend registry/factory 查找错误。"""


class DataProbeValidationError(DataBackendError):
    """DataBackend metadata-only probe 配置错误。"""
