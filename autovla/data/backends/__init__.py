"""AutoVLA 数据后端公共接口。"""

from autovla.data.backends.base import (
    DataBackend,
    DataBackendCapabilities,
    DataBackendSpec,
)

__all__ = ["DataBackend", "DataBackendCapabilities", "DataBackendSpec"]
