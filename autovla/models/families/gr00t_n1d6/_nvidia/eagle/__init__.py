"""本地 Eagle/Qwen3/SigLIP2 实现;不使用远程动态代码。"""

from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig
from autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling import LocalEagleModel
from autovla.models.families.gr00t_n1d6._nvidia.eagle.processing import LocalEagleProcessor

__all__ = ["LocalEagleConfig", "LocalEagleModel", "LocalEagleProcessor"]
