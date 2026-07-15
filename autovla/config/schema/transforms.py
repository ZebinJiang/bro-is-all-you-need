"""共享变换计划配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_non_empty_str


@dataclass(frozen=True, slots=True)
class TransformsConfig:
    """引用 R3 TransformPlan 和统计量身份, 不复制变换实现。"""

    plan_fingerprint: str = "identity"
    statistics_fingerprint: str = "identity"

    def __post_init__(self) -> None:
        """校验两个稳定身份。"""
        require_non_empty_str(self.plan_fingerprint, "transforms.plan_fingerprint")
        require_non_empty_str(
            self.statistics_fingerprint,
            "transforms.statistics_fingerprint",
        )


__all__ = ["TransformsConfig"]
