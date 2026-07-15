"""Pi0.5 生产运行时的本地 safetensors-only checkpoint 适配器。"""

from __future__ import annotations

import hashlib
from pathlib import Path


class Pi05CheckpointAdapter:
    """严格加载单一 safetensors 文件,拒绝 pickle、远程路径与宽松键匹配。"""

    identity = "autovla.pi0_5.safetensors_strict.v1"

    def validate_path(self, path: str | Path) -> Path:
        """要求已存在的绝对本地普通 ``.safetensors`` 文件。"""

        value = Path(path)
        if not value.is_absolute() or value.suffix != ".safetensors":
            raise ValueError("Pi0.5 runtime checkpoint must be an absolute .safetensors path")
        if not value.is_file() or value.is_symlink():
            raise ValueError("Pi0.5 runtime checkpoint must be an existing non-symlink file")
        return value

    def fingerprint(self, path: str | Path) -> str:
        """流式计算 checkpoint SHA256,避免整文件驻留内存。"""

        value = self.validate_path(path)
        digest = hashlib.sha256()
        with value.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def load_local(self, model: object, path: str | Path) -> tuple[str, int]:
        """通过 safetensors 加载并要求模型严格消费全部键。"""

        value = self.validate_path(path)
        from safetensors.torch import load_file

        state = load_file(str(value), device="cpu")
        loader = getattr(model, "load_state_dict", None)
        if not callable(loader):
            raise TypeError("Pi0.5 model must expose load_state_dict")
        result = loader(state, strict=True)
        missing = tuple(getattr(result, "missing_keys", ()))
        unexpected = tuple(getattr(result, "unexpected_keys", ()))
        if missing or unexpected:
            raise ValueError(
                f"strict checkpoint mismatch: missing={missing}, unexpected={unexpected}"
            )
        return self.fingerprint(value), len(state)
