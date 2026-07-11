"""无服务或机器人副作用的部署生命周期钩子。"""

from __future__ import annotations

from collections.abc import Callable


class DeploymentHook:
    """调用显式本地回调,不拥有端点、传输或动作循环。"""

    def __init__(
        self,
        *,
        before: Callable[[], None] | None = None,
        after: Callable[[object], None] | None = None,
    ) -> None:
        """保存可选本地生命周期回调。"""
        self._before = before
        self._after = after

    def before_inference(self) -> None:
        """在本地推理前调用显式回调。"""
        if self._before is not None:
            self._before()

    def after_inference(self, prediction: object) -> None:
        """在本地推理后调用显式回调,不发送外部动作。"""
        if self._after is not None:
            self._after(prediction)


__all__ = ["DeploymentHook"]
