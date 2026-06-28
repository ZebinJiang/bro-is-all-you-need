# ADR-001: M2 Upstream Design Selection

## Status

Accepted for M2 transform/data contract.

## Context

M2 needs a small, model-agnostic data contract after M1 core/config closure. The
task reviewed current StarVLA/AutoVLA M1 contracts plus metadata-only
records for FluxVLA and Dexbotic. No upstream source file was copied or adapted.

## Accepted Ideas

| Source | Exact revision | License | Reviewed path | Accepted idea | Local interface |
| --- | --- | --- | --- | --- | --- |
| StarVLA-base | `5e42b775f97d438ae58752f986284da9c4adf98b` | MIT | `autovla/core/types/sample.py` | Keep `RawSample` as the model-agnostic raw boundary. | `TransformProtocol`, `ComposeTransform`, `collate_raw_samples` |
| StarVLA-base | `5e42b775f97d438ae58752f986284da9c4adf98b` | MIT | `docs/autovla/testing_standard.md` | Keep small per-module CPU tests as acceptance evidence. | `tests/dataloader/**` |
| LeRobot | `1396b9fab7aecddd10006c33c47a487ffdcb54b4` (`v0.5.1`, v3.0 dataset target) | Apache-2.0 | upstream schema/docs metadata only | Generate tiny LeRobot v3-like directory evidence with metadata/data relationships, without depending on the full package. | `autovla/testing/fixtures/**`, `tests/dataloader/test_tiny_fixtures.py` |
| PyArrow | `pypi:pyarrow==18.1.0` | Apache-2.0 | `pyarrow.parquet` write/read API | Use a pinned test/quality-only parquet backend for generated fixture evidence. | `autovla/testing/fixtures/**`, `tests/dataloader/**` |
| FluxVLA | `source-archive-sha256:aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d` | Apache-2.0 | `archive:FluxVLA-main/README.md` | Use explicit padding/action mask semantics and tiny fixture organization. | `autovla/testing/fixtures/**`, `collate_raw_samples` |
| Dexbotic | `source-archive-sha256:a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30` | MIT | `archive:dexbotic-main/README.md` | Use typed transform configuration and composable stage boundaries. | `TransformSpec`, `TransformRegistry`, `ComposeTransform` |

## Rejected Ideas

| Source | Rejected idea | Reason |
| --- | --- | --- |
| FluxVLA | Runner lifecycle, checkpoint manager, DDP/FSDP, safetensors resume. | These belong to later runner/model milestones, not M2 data contract. |
| FluxVLA | ZMQ, RTC, CUDA Graph, Triton serving paths. | These belong to later deployment/performance milestones. |
| Dexbotic | BaseExp-style god object. | It would mix config, build, train, and execution responsibilities. |
| Dexbotic | Benchmark absolute paths. | AutoVLA must keep project-local governed paths. |
| Dexbotic | Transform stages that invoke model-specific tokenization. | M2 transforms must remain model-agnostic and CPU/numpy testable. |

## Reuse Classification

- StarVLA-base: inspired-only; M2 extends the local M1 boundary without copying
  external source.
- LeRobot: format-target only; no upstream source, fixtures, or package code is
  copied or adapted.
- PyArrow: test/quality dependency only; no copied or adapted source and no
  public dataloader API exposure.
- FluxVLA: inspired-only; no copied or adapted code, fixtures, or assets.
- Dexbotic: inspired-only; no copied or adapted code, symbols, or configs.

`docs/references/upstream_sources.yaml` is the authoritative registry for exact
revision, license, reviewed path, local destination, and reuse classification.

## Compatibility Impact

M2 does not change M1 `RawSample`, action, config, framework, runner, policy, or
registry contracts. Legacy payload conversion is additive through
`LegacyDataloaderAdapter` and requires explicit `robot_tag` injection.
