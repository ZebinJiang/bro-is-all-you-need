# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# ruff: noqa: RUF001, RUF002
"""Pi0.5 家族清洁实现的精确上游源码收据。

每条记录绑定固定提交中的路径、符号和 Git blob，并说明本地采用方式。
该模块只含元数据，不读取 checkpoint、tokenizer、模型或数据集载荷。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from types import MappingProxyType

OPENPI_REVISION = "15a9616a00943ada6c20a0f158e3adb39df2ccac"
OPENPI_URL = f"https://github.com/Physical-Intelligence/openpi@{OPENPI_REVISION}"
OPENPI_LICENSE = "Apache-2.0"
_BACKEND_DECISION = "NO_BACKEND_WINNER"


@dataclass(frozen=True, slots=True)
class Pi05SourceReceipt:
    """绑定一个上游符号及其本地采用边界。"""

    upstream_path: str
    upstream_symbol: str
    git_blob: str
    local_symbols: tuple[str, ...]
    reuse_mode: str

    def __post_init__(self) -> None:
        """拒绝空字段、短 blob 或未声明的采用方式。"""

        text_values = (
            self.upstream_path,
            self.upstream_symbol,
            self.reuse_mode,
        )
        if any(not value.strip() for value in text_values):
            raise ValueError("Pi0.5 source receipt fields must not be empty")
        if len(self.git_blob) != 40 or any(
            character not in "0123456789abcdef" for character in self.git_blob
        ):
            raise ValueError("Pi0.5 source receipt requires a complete Git blob SHA-1")
        if not self.local_symbols or any(not value.strip() for value in self.local_symbols):
            raise ValueError("Pi0.5 source receipt requires local symbols")
        if self.reuse_mode not in {"clean_reimplementation", "minimal_adaptation"}:
            raise ValueError("unsupported Pi0.5 source reuse mode")


@dataclass(frozen=True, slots=True)
class Pi05LocalReuseDetail:
    """补充上游收据对应的本地路径、采用分类、修改和依赖影响。"""

    upstream_path: str
    local_paths: tuple[str, ...]
    reuse_class: str
    local_modifications: str
    dependency_impact: str

    def __post_init__(self) -> None:
        """要求路径非空并严格区分许可、适配与启发式清洁实现。"""

        if not self.upstream_path.strip() or not self.local_paths:
            raise ValueError("Pi0.5 local reuse detail requires source and local paths")
        if any(not value.strip() for value in self.local_paths):
            raise ValueError("Pi0.5 local reuse paths must not be empty")
        if self.reuse_class not in {"license_reference", "adapted", "inspired"}:
            raise ValueError("unsupported Pi0.5 local reuse class")
        if not self.local_modifications.strip() or not self.dependency_impact.strip():
            raise ValueError("Pi0.5 local reuse detail requires impact descriptions")

    def to_json_dict(self, *, git_blob: str) -> dict[str, object]:
        """返回 canonical 文档使用的稳定来源映射。"""

        return {
            "upstream_path": self.upstream_path,
            "git_blob": git_blob,
            "local_paths": list(self.local_paths),
            "reuse_class": self.reuse_class,
            "local_modifications": self.local_modifications,
            "dependency_impact": self.dependency_impact,
        }


PI05_SOURCE_RECEIPTS = (
    Pi05SourceReceipt(
        "LICENSE",
        "Apache License 2.0",
        "f49a4e16e68b128803cc2dcea614603632b04eac",
        ("PI05_SOURCE_RECEIPTS",),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models/pi0_config.py",
        "Pi0Config",
        "584d83f199e092203b59861a861c64768a4e0300",
        ("Pi05Config", "PI05_SPEC"),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models/model.py",
        "Observation, preprocess_observation",
        "29618b49453742266fe6e4a5815ceee06d815f3b",
        ("Pi05Processor.prepare_observation",),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models/tokenizer.py",
        "PaligemmaTokenizer.tokenize",
        "8a4966d6298619e52c7ba53359ccbbb8ba0b8cf6",
        ("Pi05Processor._tokenize",),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models_pytorch/preprocessing_pytorch.py",
        "preprocess_observation_pytorch",
        "33c94a59b18a7e45732a02200f0daef5b0f93018",
        ("Pi05Processor._resolve_camera_inputs", "Pi05Processor._prepare_image"),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models_pytorch/pi0_pytorch.py",
        "PI0Pytorch",
        "e68ddb7cc02c2fd256e9b48ac9d0fb9df966536a",
        ("Pi05Model", "Pi05ActionExpert"),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models_pytorch/gemma_pytorch.py",
        "PaliGemmaWithExpertModel",
        "ecc597a9a23ffb26db8c1907fd264c4af797d786",
        ("Pi05VisionLanguageBackbone", "Pi05ActionExpert"),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/shared/image_tools.py",
        "resize_with_pad, resize_with_pad_torch",
        "8cde35352021de1e66b5856eb1a18bf2dff61ee7",
        ("Pi05Processor._prepare_image",),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/shared/normalize.py",
        "NormStats, serialize_json, deserialize_json",
        "5a75faecfbf4267329824b103e4cdd091d729840",
        ("Pi05NormalizationReceipt", "Pi05SemanticNormalizationPlan"),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/transforms.py",
        "Normalize, Unnormalize, TokenizePrompt, PadStatesAndActions",
        "272375ea95a5e43a42a6c0ff14cf89d34da76a45",
        ("Pi05SemanticNormalizationPlan", "Pi05Processor"),
        "minimal_adaptation",
    ),
    Pi05SourceReceipt(
        "src/openpi/policies/policy.py",
        "Policy.infer",
        "b9b708bdcaffa086be4b22b84a29b8cc00c710e4",
        ("Pi05PolicySession",),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/policies/aloha_policy.py",
        "AlohaInputs, AlohaOutputs",
        "f16be3334584692ba505553220ab20ff7b2719c5",
        ("Pi05Processor._resolve_camera_inputs", "Pi05SemanticTransform"),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/policies/droid_policy.py",
        "DroidInputs, DroidOutputs",
        "55bdb419dd552daa9dd2943638b91c7d580e26fc",
        ("Pi05Processor._resolve_camera_inputs", "Pi05SemanticTransform"),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/policies/libero_policy.py",
        "LiberoInputs, LiberoOutputs",
        "fe5aab0add5795531913363d7c46d916c81d1f9b",
        ("Pi05Processor._resolve_camera_inputs", "Pi05SemanticTransform"),
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "examples/convert_jax_model_to_pytorch.py",
        "slice_paligemma_state_dict, slice_gemma_state_dict, convert_pi0_checkpoint",
        "632c0b8782c1ecb5cb380130a30a3152b220eafd",
        ("OFFICIAL_PI05_CONVERSION_PLAN", "Pi05CheckpointConverter"),
        "minimal_adaptation",
    ),
)

_LOCAL_REUSE_DETAILS = (
    Pi05LocalReuseDetail(
        "LICENSE",
        ("autovla/models/families/pi0_5/source_map.py",),
        "license_reference",
        "记录 Apache-2.0 源码许可，不把许可文本计为代码复制或适配。",
        "无运行依赖；完整 Apache-2.0 文本由仓库 licenses/Apache-2.0.txt 保留。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models/pi0_config.py",
        (
            "autovla/models/families/pi0_5/config.py",
            "autovla/models/families/pi0_5/family.py",
        ),
        "inspired",
        "按固定维度与类型合同清洁重实现，未保留上游实现文本。",
        "仅复用既有 family 元数据；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models/model.py",
        ("autovla/models/families/pi0_5/processor.py",),
        "adapted",
        "最小适配 observation 预处理合同，并增加严格类型、shape、mask 与失败关闭校验。",
        "复用现有 NumPy/PyTorch family 依赖；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models/tokenizer.py",
        ("autovla/models/families/pi0_5/processor.py",),
        "adapted",
        "最小适配 prompt/token 上限合同，并只接受本地 paligemma_tokenizer.model。",
        "新增 sentencepiece==0.2.0；不引入 OpenPI 或远程 tokenizer 依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models_pytorch/preprocessing_pytorch.py",
        ("autovla/models/families/pi0_5/processor.py",),
        "adapted",
        "最小适配相机解析、图像 padding 与有效性 mask，增加严格输入校验。",
        "复用现有 NumPy/PyTorch family 依赖；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models_pytorch/pi0_pytorch.py",
        (
            "autovla/models/families/pi0_5/model.py",
            "autovla/models/families/pi0_5/action_head.py",
        ),
        "adapted",
        "最小适配 flow-matching、官方时间嵌入和十步 Euler，并接入 AutoVLA 接口。",
        "仅使用 PyTorch family 依赖；OpenPI 不成为运行依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/models_pytorch/gemma_pytorch.py",
        (
            "autovla/models/families/pi0_5/_openpi_compat/modeling.py",
            "autovla/models/families/pi0_5/backbone.py",
            "autovla/models/families/pi0_5/action_head.py",
        ),
        "adapted",
        "最小适配官方 PaliGemma/SigLIP/Gemma expert 图、命名空间和逐层 K/V。",
        "仅使用 PyTorch 图；Gemma 资产与条款不随源码许可传递。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/shared/image_tools.py",
        ("autovla/models/families/pi0_5/processor.py",),
        "adapted",
        "最小适配 resize-with-pad 语义，并增加 dtype、范围与确定性校验。",
        "复用现有 NumPy/PyTorch family 依赖；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/shared/normalize.py",
        ("autovla/models/families/pi0_5/normalization.py",),
        "inspired",
        "清洁实现不可变统计收据、语义绑定和序列化边界。",
        "仅使用标准库与现有 NumPy；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/transforms.py",
        (
            "autovla/models/families/pi0_5/normalization.py",
            "autovla/models/families/pi0_5/processor.py",
        ),
        "adapted",
        "最小适配 quantile 正反变换、prompt token 与 state/action padding 合同。",
        "复用现有 NumPy/PyTorch family 依赖；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/policies/policy.py",
        ("autovla/models/families/pi0_5/policy.py",),
        "inspired",
        "按公开 infer 边界清洁实现本地无标签 session，不保留上游实现文本。",
        "不依赖 OpenPI runtime；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/policies/aloha_policy.py",
        (
            "autovla/models/families/pi0_5/processor.py",
            "autovla/models/families/pi0_5/normalization.py",
        ),
        "inspired",
        "按公开相机与动作语义清洁实现可注入 embodiment transform。",
        "不依赖 OpenPI policy runtime；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/policies/droid_policy.py",
        (
            "autovla/models/families/pi0_5/processor.py",
            "autovla/models/families/pi0_5/normalization.py",
        ),
        "inspired",
        "按公开相机与动作语义清洁实现可注入 embodiment transform。",
        "不依赖 OpenPI policy runtime；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "src/openpi/policies/libero_policy.py",
        (
            "autovla/models/families/pi0_5/processor.py",
            "autovla/models/families/pi0_5/normalization.py",
        ),
        "inspired",
        "按公开相机与动作语义清洁实现可注入 embodiment transform。",
        "不依赖 OpenPI policy runtime；本修复不改依赖。",
    ),
    Pi05LocalReuseDetail(
        "examples/convert_jax_model_to_pytorch.py",
        ("autovla/models/families/pi0_5/conversion.py",),
        "adapted",
        "最小适配参数切片与独立 Q/K/V 规则，输出唯一 AutoVLA state-dict 命名空间。",
        "JAX/Flax/Orbax 保持 conversion-only；生产 runtime 不导入这些依赖。",
    ),
)

if tuple(item.upstream_path for item in _LOCAL_REUSE_DETAILS) != tuple(
    item.upstream_path for item in PI05_SOURCE_RECEIPTS
):
    raise RuntimeError("Pi0.5 source receipts and local reuse details drifted")

_RECEIPT_BY_PATH = MappingProxyType(
    {receipt.upstream_path: receipt for receipt in PI05_SOURCE_RECEIPTS}
)
PI05_SOURCE_TO_LOCAL = tuple(
    detail.to_json_dict(git_blob=_RECEIPT_BY_PATH[detail.upstream_path].git_blob)
    for detail in _LOCAL_REUSE_DETAILS
)


def source_map_fingerprint() -> str:
    """返回覆盖提交、许可和全部符号收据的稳定 SHA256。"""

    payload = {
        "license": OPENPI_LICENSE,
        "receipts": [asdict(receipt) for receipt in PI05_SOURCE_RECEIPTS],
        "revision": OPENPI_REVISION,
        "schema_version": "autovla.pi0_5.source_map.v2",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


PI05_SOURCE_MAP_FINGERPRINT = source_map_fingerprint()

__all__ = [
    "OPENPI_LICENSE",
    "OPENPI_REVISION",
    "OPENPI_URL",
    "PI05_SOURCE_MAP_FINGERPRINT",
    "PI05_SOURCE_RECEIPTS",
    "PI05_SOURCE_TO_LOCAL",
    "Pi05LocalReuseDetail",
    "Pi05SourceReceipt",
    "source_map_fingerprint",
]
