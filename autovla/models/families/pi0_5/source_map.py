# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# ruff: noqa: RUF002
"""Pi0.5 家族清洁实现的精确上游源码收据。

每条记录绑定固定提交中的路径、符号和 Git blob，并说明本地采用方式。
该模块只含元数据，不读取 checkpoint、tokenizer、模型或数据集载荷。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

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
        "clean_reimplementation",
    ),
    Pi05SourceReceipt(
        "src/openpi/models_pytorch/gemma_pytorch.py",
        "PaliGemmaWithExpertModel",
        "ecc597a9a23ffb26db8c1907fd264c4af797d786",
        ("Pi05VisionLanguageBackbone", "Pi05ActionExpert"),
        "clean_reimplementation",
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


def source_map_fingerprint() -> str:
    """返回覆盖提交、许可和全部符号收据的稳定 SHA256。"""

    payload = {
        "license": OPENPI_LICENSE,
        "receipts": [asdict(receipt) for receipt in PI05_SOURCE_RECEIPTS],
        "revision": OPENPI_REVISION,
        "schema_version": "autovla.pi0_5.source_map.v1",
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
    "Pi05SourceReceipt",
    "source_map_fingerprint",
]
