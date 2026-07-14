"""GR00T 本地生产资产错误。"""

from __future__ import annotations

from pathlib import Path


class LocalModelAssetError(RuntimeError):
    """报告官方模型所需本地资产缺失且禁止任何隐式回退。"""

    def __init__(
        self,
        field: str,
        path: str | Path | None,
        required_members: tuple[str, ...],
        *,
        detail: str | None = None,
    ) -> None:
        """构造包含字段、路径、成员和本地修复动作的错误。"""
        resolved_path = None
        if path is not None:
            candidate = Path(path).expanduser()
            resolved_path = str(candidate.resolve(strict=False))
        members = ", ".join(required_members)
        corrective_action = (
            "provide an authorized absolute local path containing every required member"
        )
        suffix = "" if detail is None else f"; detail={detail}"
        super().__init__(
            f"GR00T local asset error: field={field}; resolved_path={resolved_path!r}; "
            f"required_members=[{members}]; local_files_only=true; "
            f"corrective_action={corrective_action}; no download, remote identifier, "
            f"or architecture fallback is allowed{suffix}"
        )
        self.field = field
        self.resolved_path = resolved_path
        self.required_members = required_members
        self.local_files_only = True
        self.corrective_action = corrective_action
        self.detail = detail


__all__ = ["LocalModelAssetError"]
