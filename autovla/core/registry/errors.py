"""AutoVLA 注册表异常类型。"""


class RegistryError(Exception):
    """注册表相关错误的基类。"""


class DuplicateRegistrationError(RegistryError):
    """表示注册表键重复且未启用覆盖。"""


class UnknownRegistrationError(RegistryError):
    """表示请求的注册表键不存在。"""
