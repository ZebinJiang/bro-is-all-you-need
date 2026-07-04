"""DataBackend 候选项 registry。"""

from __future__ import annotations

from types import MappingProxyType

from autovla.dataloader.backends.contracts import DataBackendSpec


def get_backend_specs() -> MappingProxyType[str, DataBackendSpec]:
    """返回本 tranche 可审查的 backend 候选契约。"""
    return MappingProxyType(
        {
            "synthetic": DataBackendSpec(
                backend_key="synthetic",
                display_name="Synthetic metadata baseline",
                input_root_policy="optional_missing_local_path",
                supports_local_probe=True,
                supports_streaming_future=False,
                supports_random_access_future=True,
                license_reference_id="internal",
                dependency_status="stdlib_only",
                implementation_status="implemented",
            ),
            "raw_zjh": DataBackendSpec(
                backend_key="raw_zjh",
                display_name="Raw ZJH local metadata",
                input_root_policy="local_directory_metadata_only",
                supports_local_probe=True,
                supports_streaming_future=False,
                supports_random_access_future=True,
                license_reference_id="starvla",
                dependency_status="stdlib_only",
                implementation_status="implemented",
            ),
            "lerobot_local": DataBackendSpec(
                backend_key="lerobot_local",
                display_name="LeRobot local metadata",
                input_root_policy="local_directory_metadata_only",
                supports_local_probe=True,
                supports_streaming_future=True,
                supports_random_access_future=True,
                license_reference_id="lerobot",
                dependency_status="future_optional_runtime",
                implementation_status="metadata_probe_only",
            ),
            "webdataset_tar": DataBackendSpec(
                backend_key="webdataset_tar",
                display_name="WebDataset tar metadata",
                input_root_policy="local_tar_metadata_only",
                supports_local_probe=True,
                supports_streaming_future=True,
                supports_random_access_future=False,
                license_reference_id="webdataset",
                dependency_status="stdlib_tarfile_only",
                implementation_status="metadata_probe_only",
            ),
        }
    )
