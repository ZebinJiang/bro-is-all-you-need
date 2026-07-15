"""旧 deployment 推理名称的单向兼容别名。"""

from autovla.inference.session import InferenceSession

# 保持对象身份, 不保留第二个 predictor 生命周期实现。
InferencePolicy = InferenceSession

__all__ = ["InferencePolicy"]
