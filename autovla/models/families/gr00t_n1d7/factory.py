"""GR00T N1.7 共享装配请求兼容的失败关闭工厂。"""

from __future__ import annotations

from autovla.models.assembly import ModelAssemblyRequest, ModelAssemblyResult
from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
from autovla.models.families.gr00t_n1d7.assets import Gr00tN1d7AssetBundle
from autovla.models.families.gr00t_n1d7.backbone import (
    CosmosReason2VisionLanguageBackbone,
)
from autovla.models.families.gr00t_n1d7.checkpoint import Gr00tN1d7CheckpointAdapter
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.families.gr00t_n1d7.model import Gr00tN1d7Model
from autovla.models.families.gr00t_n1d7.processor import Gr00tN1d7Processor


class Gr00tN1d7ModelFactory:
    """提供 ModelAssemblyRequest/Result 类型面但不越过当前执行门。

    架构组件可在无运行时副作用的情况下构造。完整 ``__call__`` 必须等待
    许可、gated 资产、checkpoint shape 和 CUDA 证据。当前不返回伪造的
    ``ModelAssemblyResult``。
    """

    def architecture_components(self, request: ModelAssemblyRequest) -> tuple[
        Gr00tN1d7Processor,
        CosmosReason2VisionLanguageBackbone,
        Gr00tN1d7ActionHead,
        Gr00tN1d7Model,
        Gr00tN1d7CheckpointAdapter,
    ]:
        """构造不分配 tensor 的同配置组件描述。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        if not isinstance(request.asset_bundle, Gr00tN1d7AssetBundle):
            raise TypeError("request must carry a verified GR00T N1.7 asset bundle")
        processor = Gr00tN1d7Processor(request.config)
        backbone = CosmosReason2VisionLanguageBackbone(request.config)
        action_head = Gr00tN1d7ActionHead(request.config)
        model = Gr00tN1d7Model(request.config, backbone, action_head)
        return processor, backbone, action_head, model, Gr00tN1d7CheckpointAdapter()

    def __call__(self, request: ModelAssemblyRequest, /) -> ModelAssemblyResult[
        Gr00tN1d7Processor,
        CosmosReason2VisionLanguageBackbone,
        Gr00tN1d7ActionHead,
        Gr00tN1d7Model,
        Gr00tN1d7CheckpointAdapter,
        object,
    ]:
        """拒绝在证据不足时生成可执行装配结果。"""

        self.architecture_components(request)
        raise RuntimeError(
            "N1.7 assembly result requires resolved license, Cosmos, checkpoint, and CUDA evidence"
        )


__all__ = ["Gr00tN1d7ModelFactory"]
