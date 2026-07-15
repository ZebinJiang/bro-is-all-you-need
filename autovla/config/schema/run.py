"""实验运行身份配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_choice, require_int, require_non_empty_str


@dataclass(frozen=True, slots=True)
class RunConfig:
    """保存实验名称、种子和受治理输出根。"""

    name: str = "unconfigured_experiment"
    seed: int = 7
    output_dir: str = "runs/local/unconfigured_experiment"
    intent: str = "architecture_inspection"

    def __post_init__(self) -> None:
        """校验运行身份且强制输出位于 runs。"""
        require_non_empty_str(self.name, "run.name")
        seed = require_int(self.seed, "run.seed")
        if seed < 0:
            raise ValueError("run.seed must be non-negative")
        require_non_empty_str(self.output_dir, "run.output_dir")
        if not self.output_dir.startswith("runs/"):
            raise ValueError("run.output_dir must stay under runs/")
        require_choice(
            self.intent,
            "run.intent",
            ("architecture_inspection", "training", "local_inference"),
        )


__all__ = ["RunConfig"]
