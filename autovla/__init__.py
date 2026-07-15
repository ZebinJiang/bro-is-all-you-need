"""AutoVLA 轻量包根,优先读取已安装分发版本。"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("autovla")
except PackageNotFoundError:
    from autovla._version import __version__

__all__ = ["__version__"]
