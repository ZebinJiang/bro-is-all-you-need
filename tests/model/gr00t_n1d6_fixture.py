"""AutoVLA 自有的 reduced GR00T 本地 Eagle/tokenizer 测试资产生成器。"""

from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: object) -> None:
    """写入稳定、可读的测试 JSON。"""

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_reduced_eagle_assets(
    root: Path,
    *,
    patch_size: int = 16,
    downsample_ratio: float = 0.5,
) -> Path:
    """生成仅供验证的微型本地 Eagle 和 Qwen BPE 资产。"""

    from tokenizers.pre_tokenizers import ByteLevel

    root.mkdir(parents=True, exist_ok=False)
    alphabet = sorted(ByteLevel.alphabet())
    vocabulary = {token: index for index, token in enumerate(alphabet)}
    for token in ("<pad>", "</s>", "<unk>"):
        vocabulary[token] = len(vocabulary)
    _write_json(root / "vocab.json", vocabulary)
    (root / "merges.txt").write_text("#version: 0.2\n", encoding="utf-8")
    _write_json(
        root / "tokenizer_config.json",
        {
            "model_max_length": 512,
            "padding_side": "left",
            "tokenizer_class": "Qwen2TokenizerFast",
        },
    )
    _write_json(
        root / "special_tokens_map.json",
        {"eos_token": "</s>", "pad_token": "<pad>", "unk_token": "<unk>"},
    )
    _write_json(
        root / "chat_template.json",
        {
            "chat_template": (
                "{% for message in messages %}{% for item in message['content'] %}"
                "{% if item['type'] == 'text' %}{{ item['text'] }}{% endif %}"
                "{% if item['type'] == 'image' %}<image-1>{% endif %}"
                "{% endfor %}{% endfor %}"
            )
        },
    )
    _write_json(root / "preprocessor_config.json", {"size": 32})
    _write_json(root / "processor_config.json", {"local_files_only": True})
    _write_json(
        root / "config.json",
        {
            "image_token_index": 511,
            "downsample_ratio": downsample_ratio,
            "select_layer": -1,
            "text_config": {
                "model_type": "qwen3",
                "vocab_size": 512,
                "hidden_size": 64,
                "intermediate_size": 128,
                "num_hidden_layers": 2,
                "num_attention_heads": 4,
                "num_key_value_heads": 4,
                "head_dim": 16,
                "max_position_embeddings": 512,
                "rope_theta": 10000.0,
            },
            "vision_config": {
                "model_type": "siglip2_vision_model",
                "hidden_size": 64,
                "intermediate_size": 128,
                "num_hidden_layers": 2,
                "num_attention_heads": 4,
                "num_channels": 3,
                "image_size": 32,
                "patch_size": patch_size,
            },
        },
    )
    return root


__all__ = ["write_reduced_eagle_assets"]
