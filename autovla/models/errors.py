"""模型目录与 CLI 共用的稳定错误类型。"""

from __future__ import annotations


class ModelCatalogError(RuntimeError):
    """表示可安全序列化且不需要导入家族实现的目录错误。"""

    code = "MODEL_CATALOG_ERROR"

    def __init__(self, family_key: str, message: str) -> None:
        """保存规范 family key、稳定消息和机器可读 code。"""

        super().__init__(message)
        self.family_key = family_key
        self.message = message

    def to_json_dict(self) -> dict[str, str]:
        """返回字段闭合且排序无关的 JSON 对象。"""

        return {
            "code": self.code,
            "family_key": self.family_key,
            "message": self.message,
        }


class UnknownModelFamilyError(ModelCatalogError):
    """表示 inspect 请求的 family key 不在静态目录中。"""

    code = "UNKNOWN_MODEL_FAMILY"

    def __init__(self, family_key: str) -> None:
        """构造不泄漏内部异常文本的稳定错误。"""

        super().__init__(family_key, "unknown model family")


class DeferredModelFamilyError(ModelCatalogError):
    """表示 family 已登记但按用户优先级延后。"""

    code = "MODEL_FAMILY_DEFERRED"

    def __init__(self, family_key: str) -> None:
        """构造不触发 family-private 导入的稳定错误。"""

        super().__init__(family_key, "model family is deferred by user priority")


__all__ = [
    "DeferredModelFamilyError",
    "ModelCatalogError",
    "UnknownModelFamilyError",
]
