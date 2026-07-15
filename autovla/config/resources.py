"""通过 importlib.resources 解析安装包内权威配置。"""

from __future__ import annotations

from importlib.resources import files
from typing import Protocol, cast

RESOURCE_SCHEME = "pkg://"
# 仅供无运行时检查器使用;生产训练 CLI 仍必须显式接收配置。
DEFAULT_EXPERIMENT = "pkg://experiments/m9_gr00t_gpu_architecture"
_GROUP_DIRECTORIES = {
    "data": "data",
    "environment": "environments",
    "environments": "environments",
    "model": "models",
    "models": "models",
    "training": "training",
    "optimization": "optimization",
    "experiment": "experiments",
    "experiments": "experiments",
}


class ConfigResource(Protocol):
    """描述配置读取所需的最小资源接口,兼容 Python 3.10。"""

    def is_file(self) -> bool:
        """返回资源是否为普通文件。"""

        ...

    def read_text(self, encoding: str = "utf-8", errors: str | None = None) -> str:
        """按文本方式读取资源。"""

        ...


def _simple_part(value: str, name: str) -> str:
    """要求资源路径片段为不含目录跳转的稳定名称。"""
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{name} must be a simple non-empty name")
    return value


def packaged_config_uri(group: str, name: str) -> str:
    """构造稳定的 ``pkg://group/name`` 配置引用。"""
    normalized_group = _simple_part(group, "config resource group")
    normalized_name = _simple_part(name.removesuffix(".yaml"), "config resource name")
    if normalized_group not in _GROUP_DIRECTORIES:
        raise ValueError(f"unknown config resource group: {normalized_group}")
    return f"{RESOURCE_SCHEME}{normalized_group}/{normalized_name}"


def parse_packaged_config_uri(reference: str) -> tuple[str, str]:
    """解析并校验包内配置 URI。"""
    if not reference.startswith(RESOURCE_SCHEME):
        raise ValueError(f"packaged config reference must start with {RESOURCE_SCHEME}")
    path = reference[len(RESOURCE_SCHEME) :]
    parts = path.split("/")
    if len(parts) != 2:
        raise ValueError("packaged config reference must be pkg://group/name")
    group, name = parts
    packaged_config_uri(group, name)
    return group, name.removesuffix(".yaml")


def config_resource(group: str, name: str) -> ConfigResource:
    """返回包内 YAML Traversable,不依赖当前工作目录。"""
    normalized_name = _simple_part(name.removesuffix(".yaml"), "config resource name")
    try:
        directory = _GROUP_DIRECTORIES[_simple_part(group, "config resource group")]
    except KeyError as exc:
        raise ValueError(f"unknown config resource group: {group}") from exc
    resource = files("autovla.resources")
    for part in ("configs", directory, f"{normalized_name}.yaml"):
        resource = resource.joinpath(part)
    if not resource.is_file():
        raise FileNotFoundError(f"unknown packaged config resource: {group}/{normalized_name}")
    return cast(ConfigResource, resource)


def config_resource_from_uri(reference: str) -> ConfigResource:
    """从稳定 URI 返回包内 YAML 资源。"""
    group, name = parse_packaged_config_uri(reference)
    return config_resource(group, name)


__all__ = [
    "DEFAULT_EXPERIMENT",
    "RESOURCE_SCHEME",
    "config_resource",
    "config_resource_from_uri",
    "packaged_config_uri",
    "parse_packaged_config_uri",
]
