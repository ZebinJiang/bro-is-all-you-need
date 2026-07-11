"""AutoVLA 配置异常。"""


class ConfigurationError(ValueError):
    """表示配置内容无法组成合法实验。"""


class UnknownConfigurationFieldError(ConfigurationError):
    """表示配置包含 schema 未声明的字段。"""


class ConfigurationCompositionError(ConfigurationError):
    """表示命名预设无法解析或组合。"""


class ConfigurationOverrideError(ConfigurationError):
    """表示 dotted override 语法或路径无效。"""


__all__ = [
    "ConfigurationCompositionError",
    "ConfigurationError",
    "ConfigurationOverrideError",
    "UnknownConfigurationFieldError",
]
