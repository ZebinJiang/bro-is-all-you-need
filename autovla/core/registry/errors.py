"""AutoVLA 注册表异常类型。"""


class RegistryError(Exception):
    """注册表相关错误的基类。"""


class DuplicateRegistrationError(RegistryError):
    """表示注册表键重复且未启用覆盖。"""


class UnknownRegistrationError(RegistryError):
    """表示请求的注册表键不存在。"""


class OptionalDependencyError(RegistryError):
    """表示已选择组件缺少其声明的可选依赖。"""


class InvalidImportStringError(RegistryError):
    """表示懒工厂导入字符串无效或目标不可调用。"""
