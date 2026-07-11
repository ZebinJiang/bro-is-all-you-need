#!/usr/bin/env python3
"""生成 AutoVLA 自有 Eagle/tokenizer fixture、解析配置和运行请求。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from m6_runtime_common import TARGETS, TASK_ID, project_root


def _write_json(path: Path, payload: object) -> None:
    """以独占模式写入稳定 JSON,拒绝覆盖既有证据。"""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")


def _byte_level_alphabet() -> tuple[str, ...]:
    """按 GPT-2 byte-to-unicode 规则生成完整确定性字母表。"""
    byte_values = list(range(ord("!"), ord("~") + 1))
    byte_values += list(range(ord("¡"), ord("¬") + 1))
    byte_values += list(range(ord("®"), ord("ÿ") + 1))
    codepoints = list(byte_values)
    extra = 0
    for value in range(256):
        if value not in byte_values:
            byte_values.append(value)
            codepoints.append(256 + extra)
            extra += 1
    return tuple(sorted(chr(codepoint) for codepoint in codepoints))


def _write_eagle_assets(root: Path) -> None:
    """写入最小配置/tokenizer fixture,不包含权重或第三方资产文件。"""
    root.mkdir(parents=True, exist_ok=False)
    vocabulary = {token: index for index, token in enumerate(_byte_level_alphabet())}
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
            "downsample_ratio": 0.5,
            "image_token_index": 511,
            "select_layer": -1,
            "text_config": {
                "head_dim": 16,
                "hidden_size": 64,
                "intermediate_size": 128,
                "max_position_embeddings": 512,
                "model_type": "qwen3",
                "num_attention_heads": 4,
                "num_hidden_layers": 2,
                "num_key_value_heads": 4,
                "rope_theta": 10000.0,
                "vocab_size": 512,
            },
            "vision_config": {
                "hidden_size": 64,
                "image_size": 32,
                "intermediate_size": 128,
                "model_type": "siglip2_vision_model",
                "num_attention_heads": 4,
                "num_channels": 3,
                "num_hidden_layers": 2,
                "patch_size": 16,
            },
        },
    )


def _require_governed_evidence_root(path: str) -> Path:
    """要求生成根位于当前 checkout 的 ignored runs/tmp。"""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("evidence root must be an absolute path")
    resolved = candidate.resolve(strict=False)
    allowed = (project_root() / "runs" / "tmp").resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise ValueError("evidence root must be a child of project runs/tmp/")
    return resolved


def _sample_count(data_root: Path) -> int:
    """读取本地 RoboDM 索引行数,不打开或修改数据文件。"""
    index = data_root / "sample_index.jsonl"
    if not index.is_file():
        raise ValueError(f"data root requires sample_index.jsonl: {data_root}")
    count = sum(1 for line in index.read_text(encoding="utf-8").splitlines() if line.strip())
    if count <= 0:
        raise ValueError("RoboDM sample index must contain at least one row")
    return count


def generate(evidence_root: Path, data_root: Path, runtime_python: Path) -> dict[str, object]:
    """生成一次不可覆盖的 reduced runtime 输入集合。"""
    evidence_root.mkdir(parents=True, exist_ok=True)
    data_root = data_root.expanduser().resolve(strict=True)
    runtime_python = runtime_python.expanduser()
    if not runtime_python.is_absolute() or not runtime_python.is_file():
        raise ValueError("runtime Python must be an existing absolute file")
    if runtime_python.stat().st_mode & 0o111 == 0:
        raise ValueError("runtime Python must be an executable file")
    count = _sample_count(data_root)
    asset_root = evidence_root / "assets" / "eagle"
    config_dir = evidence_root / "configs"
    request_dir = evidence_root / "requests"
    evidence_dir = evidence_root / "evidence"
    output_root = evidence_root / "outputs"
    for directory in (config_dir, request_dir, evidence_dir, output_root):
        directory.mkdir(parents=True, exist_ok=True)
    _write_eagle_assets(asset_root)

    template_path = project_root() / "configs/runtime/m6-reduced-runtime.template.yaml"
    text = template_path.read_text(encoding="utf-8")
    replacements = {
        "__AUTOVLA_CHECKPOINT_ROOT_JSON__": json.dumps(str(output_root / "cpu")),
        "__AUTOVLA_DATA_ROOT_JSON__": json.dumps(str(data_root)),
        "__AUTOVLA_EAGLE_ASSET_PATH_JSON__": json.dumps(str(asset_root)),
        "__AUTOVLA_METRICS_PATH_JSON__": json.dumps(str(evidence_dir / "cpu-metrics.jsonl")),
        "__AUTOVLA_SAMPLE_COUNT__": str(count),
    }
    for placeholder, value in replacements.items():
        if placeholder not in text:
            raise ValueError(f"runtime template is missing placeholder: {placeholder}")
        text = text.replace(placeholder, value)
    if "__AUTOVLA_" in text:
        raise ValueError("runtime template contains unresolved placeholders")
    config_path = config_dir / "reduced_runtime.yaml"
    with config_path.open("x", encoding="utf-8") as stream:
        stream.write(text)

    requests: dict[str, str] = {}
    for target in TARGETS:
        output_dir = output_root / target
        output_dir.mkdir(exist_ok=False)
        request_path = request_dir / f"{target}.json"
        _write_json(
            request_path,
            {
                "asset_root": str(asset_root),
                "config_path": str(config_path),
                "data_root": str(data_root),
                "evidence_json": str(evidence_dir / f"{target}.json"),
                "local_only": True,
                "max_steps": 2,
                "offline": True,
                "output_dir": str(output_dir),
                "runtime_python": str(runtime_python),
                "schema_version": 1,
                "target": target,
                "task_id": TASK_ID,
            },
        )
        requests[target] = str(request_path)
    return {
        "asset_root": str(asset_root),
        "config_path": str(config_path),
        "requests": requests,
    }


def main() -> int:
    """解析 caller-supplied 证据根和只读本地数据根。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--runtime-python", required=True)
    args = parser.parse_args()
    result = generate(
        _require_governed_evidence_root(args.evidence_root),
        Path(args.data_root),
        Path(args.runtime_python),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
