"""Pi0.5 家族装配计划与结果闭合边界。"""

from __future__ import annotations

from autovla.models.assembly import (
    CheckpointLoadEvidence,
    ModelAssemblyPlan,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.families.pi0_5.action_head import Pi05ActionExpert
from autovla.models.families.pi0_5.assets import Pi05AssetBundle
from autovla.models.families.pi0_5.backbone import Pi05VisionLanguageBackbone
from autovla.models.families.pi0_5.checkpoint import Pi05CheckpointAdapter
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.families.pi0_5.model import Pi05Model
from autovla.models.families.pi0_5.processor import Pi05Processor


class Pi05ModelFactory:
    """只规划或闭合外部已构造组件;不在当前资产门前执行模型。"""

    def plan(self, request: ModelAssemblyRequest) -> ModelAssemblyPlan:
        """验证类型化配置与资产包并返回共享不可执行计划。"""

        if type(request.config) is not Pi05Config:
            raise TypeError("Pi0.5 assembly requires Pi05Config")
        if type(request.asset_bundle) is not Pi05AssetBundle:
            raise TypeError("Pi0.5 assembly requires Pi05AssetBundle")
        return resolve_model_assembly(request)

    def complete(
        self,
        request: ModelAssemblyRequest,
        *,
        processor: Pi05Processor,
        backbone: Pi05VisionLanguageBackbone,
        action_expert: Pi05ActionExpert,
        model: Pi05Model,
        checkpoint_adapter: Pi05CheckpointAdapter,
        checkpoint_load: CheckpointLoadEvidence,
        tuning_freeze: TuningFreezeEvidence,
    ) -> ModelAssemblyResult[
        Pi05Processor,
        Pi05VisionLanguageBackbone,
        Pi05ActionExpert,
        Pi05Model,
        Pi05CheckpointAdapter,
        object,
    ]:
        """把调用方完成的严格加载和冻结证据绑定到同一共享计划。"""

        plan = self.plan(request)
        if processor.config != request.config:
            raise ValueError("processor config drifted from assembly request")
        if backbone.config != request.config or action_expert.config != request.config:
            raise ValueError("model component config drifted from assembly request")
        if model.config != request.config:
            raise ValueError("model config drifted from assembly request")
        return ModelAssemblyResult(
            plan=plan,
            processor=processor,
            backbone=backbone,
            action_head=action_expert,
            model=model,
            checkpoint_adapter=checkpoint_adapter,
            policy_bundle=None,
            checkpoint_load=checkpoint_load,
            tuning_freeze=tuning_freeze,
        )

    def __call__(self, request: ModelAssemblyRequest) -> object:
        """在官方资产和运行证据闭合前拒绝隐式构造或模型执行。"""

        self.plan(request)
        raise RuntimeError(
            "Pi0.5 automatic model construction is asset-gated; use complete() with strict evidence"
        )
