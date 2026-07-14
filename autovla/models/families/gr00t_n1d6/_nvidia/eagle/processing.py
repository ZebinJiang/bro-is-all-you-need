# coding=utf-8
# Copyright 2024 The HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a:
# gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/processing_eagle3_vl.py.
"""本地 tokenizer 资产驱动的 Eagle 文本/image-token 编排。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypeGuard, runtime_checkable

import torch
from transformers.models.qwen2.tokenization_qwen2_fast import Qwen2TokenizerFast

from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig


@runtime_checkable
class _ChatTemplateRenderer(Protocol):
    """描述 tokenizer 的模板渲染入口。"""

    def __call__(
        self,
        conversation: list[dict[str, object]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> object:
        """把单轮对话渲染为文本。"""
        ...


@runtime_checkable
class _TextEncoder(Protocol):
    """描述 tokenizer 的文本编码入口。"""

    def __call__(self, text: str, *, add_special_tokens: bool) -> object:
        """把文本编码为 token ID 列表。"""
        ...


class LocalEagleProcessor:
    """只从现有本地词表构造 Qwen tokenizer 并编排视觉 token。"""

    def __init__(
        self,
        tokenizer: Qwen2TokenizerFast,
        config: LocalEagleConfig,
        chat_template: str,
    ) -> None:
        """保存直接构造的 tokenizer 和静态 Eagle 配置。"""
        self.tokenizer = tokenizer
        self.config = config
        if not chat_template.strip():
            raise ValueError("local Eagle chat template must not be empty")
        self.chat_template = chat_template
        self.tokenizer.chat_template = chat_template
        if _token_id(tokenizer, "pad_token_id") is None:
            if _token_id(tokenizer, "eos_token_id") is None:
                raise ValueError("local tokenizer must define a pad or eos token")
            eos_token: object = getattr(tokenizer, "eos_token", None)
            if not isinstance(eos_token, str):
                raise ValueError("local tokenizer eos token must be text")
            tokenizer.pad_token = eos_token

    @classmethod
    def from_local_assets(
        cls,
        root: str | Path,
        config: LocalEagleConfig,
    ) -> "LocalEagleProcessor":
        """使用明确词表/merge 文件构造 tokenizer,不调用 Hub 解析。"""
        resolved = Path(root).expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError("Eagle asset root must be a local directory")
        vocab = resolved / "vocab.json"
        merges = resolved / "merges.txt"
        tokenizer_config = resolved / "tokenizer_config.json"
        special_tokens = resolved / "special_tokens_map.json"
        chat_template_path = resolved / "chat_template.json"
        for path in (vocab, merges, tokenizer_config, special_tokens, chat_template_path):
            if not path.is_file():
                raise FileNotFoundError(f"required local tokenizer asset is missing: {path.name}")
        tokenizer_payload = _json_object(tokenizer_config)
        special_payload = _json_object(special_tokens)
        chat_payload = _json_object(chat_template_path)
        chat_template = chat_payload.get("chat_template")
        if not isinstance(chat_template, str) or not chat_template.strip():
            raise ValueError("chat_template.json must contain a non-empty chat_template")
        model_max_length = tokenizer_payload.get("model_max_length", 40960)
        if not isinstance(model_max_length, int) or isinstance(model_max_length, bool):
            raise ValueError("tokenizer model_max_length must be an integer")
        tokenizer = Qwen2TokenizerFast(
            vocab_file=str(vocab),
            merges_file=str(merges),
            model_max_length=model_max_length,
            padding_side="left",
            **_string_special_tokens(special_payload),
        )
        return cls(tokenizer, config, chat_template)

    def encode(
        self,
        texts: tuple[str, ...],
        *,
        image_count_per_sample: int,
        visual_tokens_per_image: int,
        device: torch.device,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """应用本地 chat template 并原位展开每个图像 marker。"""
        if not texts or image_count_per_sample <= 0 or visual_tokens_per_image <= 0:
            raise ValueError("texts, image count, and visual token count must be positive")
        sequences: list[list[int]] = []
        for text in texts:
            conversation: list[dict[str, object]] = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        *({"type": "image"} for _ in range(image_count_per_sample)),
                    ],
                }
            ]
            renderer: object = getattr(self.tokenizer, "apply_chat_template", None)
            if not isinstance(renderer, _ChatTemplateRenderer):
                raise TypeError("tokenizer apply_chat_template must be callable")
            rendered = renderer(
                conversation,
                tokenize=False,
                add_generation_prompt=False,
            )
            if not isinstance(rendered, str):
                raise TypeError("local chat template must render to text")
            sequences.append(
                self._tokenize_rendered_conversation(
                    rendered,
                    image_count=image_count_per_sample,
                    visual_tokens_per_image=visual_tokens_per_image,
                )
            )
        max_length = max(map(len, sequences))
        pad_id = _token_id(self.tokenizer, "pad_token_id")
        if pad_id is None:
            raise ValueError("tokenizer pad token must be configured")
        input_ids = torch.full(
            (len(sequences), max_length),
            pad_id,
            dtype=torch.long,
            device=device,
        )
        attention_mask = torch.zeros(
            (len(sequences), max_length),
            dtype=torch.bool,
            device=device,
        )
        for index, sequence in enumerate(sequences):
            start = max_length - len(sequence)
            input_ids[index, start:] = torch.tensor(sequence, dtype=torch.long, device=device)
            attention_mask[index, start:] = True
        return input_ids, attention_mask

    def _tokenize_rendered_conversation(
        self,
        rendered: str,
        *,
        image_count: int,
        visual_tokens_per_image: int,
    ) -> list[int]:
        """按模板 marker 顺序交错文本 token 和视觉 token。"""
        parts = re.split(r"(<image-(\d+)>)", rendered)
        token_ids: list[int] = []
        observed: list[int] = []
        index = 0
        while index < len(parts):
            part = parts[index]
            if part.startswith("<image-"):
                marker = int(parts[index + 1])
                observed.append(marker)
                token_ids.extend([self.config.image_token_id] * visual_tokens_per_image)
                index += 2
                continue
            if part:
                encoder: object = getattr(self.tokenizer, "encode", None)
                if not isinstance(encoder, _TextEncoder):
                    raise TypeError("tokenizer encode must be callable")
                encoded = encoder(part, add_special_tokens=False)
                if not _is_object_list(encoded) or not all(
                    isinstance(value, int) and not isinstance(value, bool) for value in encoded
                ):
                    raise TypeError("tokenizer encode must return integer token IDs")
                token_ids.extend(value for value in encoded if isinstance(value, int))
            index += 1
        expected = list(range(1, image_count + 1))
        if observed != expected:
            raise ValueError(
                "chat template image markers must appear exactly once in input image order"
            )
        return token_ids


def _string_special_tokens(payload: object) -> dict[str, str]:
    """提取 tokenizer 构造器接受的字符串 special-token 字段。"""
    if not _is_object_mapping(payload):
        raise ValueError("special token map must contain a JSON object")
    allowed = {"bos_token", "eos_token", "unk_token", "pad_token"}
    result: dict[str, str] = {}
    for raw_key, value in payload.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key
        if key not in allowed:
            continue
        if isinstance(value, str):
            result[key] = value
        elif _is_object_mapping(value):
            content: object = value.get("content")
            if isinstance(content, str):
                result[key] = content
    return result


def _json_object(path: Path) -> dict[str, object]:
    """读取本地 JSON 对象并保留显式类型边界。"""
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not _is_object_mapping(payload):
        raise ValueError(f"{path.name} must contain a JSON object")
    result: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError(f"{path.name} keys must be strings")
        result[key] = value
    return result


def _token_id(tokenizer: Qwen2TokenizerFast, name: str) -> int | None:
    """读取 tokenizer token ID 并拒绝非整数动态值。"""
    value: object = getattr(tokenizer, name, None)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"tokenizer {name} must be an integer or null")
    return value


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """收窄动态 tokenizer 列表并保留逐项校验。"""
    return isinstance(value, list)


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄动态 tokenizer 配置映射。"""
    return isinstance(value, Mapping)


__all__ = ["LocalEagleProcessor"]
