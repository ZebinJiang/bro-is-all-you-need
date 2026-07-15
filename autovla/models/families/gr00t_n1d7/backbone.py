"""Cosmos Reason2 / Qwen3-VL 骨干的本地装配描述。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config


@dataclass(frozen=True, slots=True)
class CosmosReason2VisionLanguageBackbone:
    """描述动态网格 Qwen3-VL 骨干。不导入或实例化 Transformers。

    输入边界为 ``pixel_values``、``image_grid_thw``、左填充语言 token 和
    attention mask。输出宽度为 2048。保留 artifact 指定的 16 层。
    """

    config: Gr00tN1d7Config
    implementation: str = "qwen3_vl_cosmos_reason2"
    attention_backend_preference: tuple[str, ...] = ("flash_attention_2", "sdpa")
    dynamic_image_grid: bool = True
    local_files_only: bool = True
    trust_remote_code: bool = False
    rotary_buffer_validation_required: bool = True

    def __post_init__(self) -> None:
        """关闭远端代码、固定分辨率和来源默认层数。"""

        if not isinstance(self.config, Gr00tN1d7Config):
            raise TypeError("backbone requires Gr00tN1d7Config")
        if (
            not self.dynamic_image_grid
            or not self.local_files_only
            or self.trust_remote_code
            or not self.rotary_buffer_validation_required
        ):
            raise ValueError("Cosmos/Qwen3-VL backbone must remain local and dynamic-grid")
        if self.config.retained_language_layers != 16:
            raise ValueError("artifact must retain exactly 16 Qwen3-VL layers")
        if self.attention_backend_preference != ("flash_attention_2", "sdpa"):
            raise ValueError("attention fallback order must remain FlashAttention-2 then SDPA")

    @classmethod
    def from_request(cls, request: ModelAssemblyRequest) -> CosmosReason2VisionLanguageBackbone:
        """实现共享组件工厂输入面且不读取 backbone 资产。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config)

    @property
    def tune_freeze_defaults(self) -> dict[str, object]:
        """返回 artifact 绑定的默认训练/冻结策略。"""

        return {
            "language_trainable": self.config.tune_language,
            "visual_trainable": self.config.tune_visual,
            "top_language_layers": self.config.tune_top_language_layers,
            "remaining_language_frozen": True,
            "rotary_buffers_trainable": False,
        }


def _build_backbone(
    request: ModelAssemblyRequest,
) -> CosmosReason2VisionLanguageBackbone:
    """返回绑定共享请求的骨干描述。"""

    return CosmosReason2VisionLanguageBackbone.from_request(request)


__all__ = ["CosmosReason2VisionLanguageBackbone"]
