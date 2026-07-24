"""M13 runtime lock 平台 marker 的定向回归测试。"""

from __future__ import annotations

import pytest

from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.runtime_profiles.uv_lock import _validate_target_markers


def test_resolution_markers_reject_target_when_every_branch_is_false() -> None:
    """顶层 resolution marker 全不匹配时必须按平台不兼容失败。"""

    environment = {
        "platform_machine": "x86_64",
        "sys_platform": "linux",
    }

    with pytest.raises(RuntimeEnvironmentError) as caught:
        _validate_target_markers(
            {
                "resolution-markers": [
                    'sys_platform == "win32"',
                    'platform_machine == "aarch64"',
                ]
            },
            environment,
        )

    assert caught.value.code == "RUNTIME_LOCK_PLATFORM_MISMATCH"
