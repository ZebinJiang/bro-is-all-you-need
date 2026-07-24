"""记录 Pi0.5 清洁实现采用的固定来源与许可边界。

设计参考: Physical-Intelligence/openpi@15a9616a00943ada6c20a0f158e3adb39df2ccac。
源码许可: Apache-2.0。用途: 保留公开架构与数学契约,不复制上游实现。
风险: Gemma、tokenizer、checkpoint 与派生权重条款独立,未收据前禁止运行。
"""

OPENPI_REVISION = "15a9616a00943ada6c20a0f158e3adb39df2ccac"
OPENPI_URL = f"https://github.com/Physical-Intelligence/openpi@{OPENPI_REVISION}"
_BACKEND_DECISION = "NO_BACKEND_WINNER"
_SOURCE_TO_LOCAL = (
    ("src/openpi/models/pi0_config.py", "config.py"),
    ("src/openpi/models/tokenizer.py", "processor.py"),
    ("src/openpi/models_pytorch/gemma_pytorch.py", "backbone.py"),
    ("src/openpi/models_pytorch/pi0_pytorch.py", "action_head.py,model.py"),
    ("examples/convert_jax_model_to_pytorch.py", "conversion.py,checkpoint.py"),
)

__all__ = ["OPENPI_REVISION", "OPENPI_URL"]
