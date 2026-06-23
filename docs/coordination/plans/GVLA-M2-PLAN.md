# GVLA-M2-PLAN: Transform Pipeline + Data Contract

## Objective

Build the first GenesisVLA transform/data contract on top of the final M1
closure SHA `a244c96c4dc8638033be1e8c555c39e0b77c12b3`.

## Non-Goals

- Do not start M3 Runner, M4 Model, or M5 Deployment work.
- Do not modify M1 public contracts.
- Do not copy upstream source trees, archives, model weights, or large binaries.
- Do not introduce external dataset downloads or heavyweight image backends.

## Execution Tranche

This branch executes M2 D1-D8:

- transform protocol/config/registry/compose/fingerprint;
- image resize/normalize/deterministic augment;
- state/action normalization and inverse;
- absolute/delta/relative action modes;
- dataset statistics schema/cache;
- generated tiny LeRobot-like and Parquet-like fixtures;
- deterministic in-memory mixture sampling;
- legacy dataloader adapter.

## TDD Matrix

| Area | Tests |
| --- | --- |
| Transform config | `tests/dataloader/test_transform_registry.py` |
| Image transforms | `tests/dataloader/test_image_transforms.py` |
| State/action normalization | `tests/dataloader/test_state_action_normalization.py` |
| Action modes | `tests/dataloader/test_action_mode_transform.py` |
| Dataset statistics | `tests/dataloader/test_dataset_statistics.py` |
| Tiny fixtures | `tests/dataloader/test_tiny_fixtures.py` |
| Mixture dataset | `tests/dataloader/test_mixture_dataset.py` |
| Legacy adapter | `tests/dataloader/test_legacy_dataloader_adapter.py` |
| CPU tiny E2E | `tests/dataloader/test_cpu_tiny_e2e.py` |

## Upstream Provenance

M2 uses inspired-only design references recorded in
`docs/references/upstream_sources.yaml` and
`docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`. No copied or
adapted upstream source code is present.

## Stop Conditions

Stop if the implementation requires relaxing Ruff, Black, Pyright strict, or
pytest gates; if upstream source copying is needed; if M1 contracts must change;
or if M3 scope becomes necessary.
