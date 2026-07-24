"""运行时环境画像的稳定错误类型。"""

from __future__ import annotations


class RuntimeEnvironmentError(RuntimeError):
    """携带稳定错误码的运行时环境失败。"""

    def __init__(self, code: str, message: str) -> None:
        """保存机器可判定错误码与面向人的简短说明。"""

        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
