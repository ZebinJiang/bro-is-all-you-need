# GR00T GPU200 Multiformat Telemetry Surface

PR #30 prior multiformat benchmark numbers are invalidated. The old raw row
measured preloaded `SourceSample` lookup and camera_refs, while converted
candidates measured disk-backed materialized payload readers. That comparison
is not a fair native-loader benchmark and must not be used for backend
selection, backend ranking, training-readiness claims, or final winner claims.

This document is retained to preserve the PR-visible invalidation record for
`AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`. The corrected
benchmark surface is [Fair Native Loader Bakeoff V1](FAIR_NATIVE_LOADER_BAKEOFF_V1.md).

## Invalidated Evidence

| Invalidated surface | Reason | Replacement |
| --- | --- | --- |
| Wave 8 load-benchmark numeric rows | Raw baseline used preloaded SourceSample lookup and camera_refs instead of a materialized native loader. | Fair native-loader rerun with worker_count=8 and identical materialized RGB/state/action payloads. |
| Wave 11 telemetry comparison wording | Runtime evidence was bounded task telemetry, not a complete fair backend bakeoff across all four candidates. | Corrected PR #30 rerun tables and generated artifact ledger. |

The generated evidence from the invalidated run was cleared locally with an
invalidation manifest before the corrected rerun. Source dataset files remain
read-only and were not mutated.

## Corrected Candidate Set

The fair rerun covers exactly these candidates:

- `zjh_lerobot_v21_raw`
- `zjh_lerobot_v3_local`
- `zjh_webdataset_tar`
- `zjh_robodm_container_v1`

Each candidate must load the same selected sample/window manifest and expose:

- materialized `camera.rgb_0`, `camera.rgb_1`, and `camera.rgb_2` payload proof
- state/action/action_mask payload fields
- payload hash and completeness proof
- worker_count=8 timing
- artifact size and file-count evidence
- no training, model load, checkpoint download, W&B/HF network use, endpoint, or
  robot behavior

## Current Boundary

- no final backend winner
- no long-training readiness claim
- no model-quality claim
- no source dataset mutation
- no generated artifacts committed as product source
- no external runtime side effects
