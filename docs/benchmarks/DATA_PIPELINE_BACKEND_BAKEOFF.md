# AutoVLA ZJH Data Backend Bakeoff

## Summary

- Schema: `autovla.zjh_backend_bakeoff.v1`
- Subset fingerprint: `950767717324b3572f6e4213d5c2e012a3b51a3e80b7643ee44a09723e2e77d4`
- Fair comparison worker_count=8 required: `True`
- Partial compute evidence is integrated; final winner remains pending.
- Three benchmark evidence rows exist when historical WebDataset evidence is counted, but WebDataset is not primary worker_count=8 comparable.
- Missing final requirements: third benchmarked candidate, final winner, Owner reviews, draft PR.
- No real training, model load, checkpoint read, tokenizer load, W&B/HF network, endpoint, or robot action.

## Candidate Dashboard

| Candidate | Dependency status | Worker count | Batch size | Sample count | Build time | Artifact size | P50 latency | P95 latency | Samples/sec | File opens | PFS read MB/s | Estimated GPU wait | Status | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | `no_new_dependency` | `8` | `missing` | `512` | `not_applicable` | `missing` | `6.055724` | `6.055724` | `84548.106882` | `12` | `not_applicable` | `0.0` | `FAIL` | build a PFS-backed Training Store before training |
| `lerobot_v3_view` | `official_lerobot_v3_dependency_not_approved` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_PROTOTYPE_ONLY` | official LeRobot v3 route is dependency-blocked; local row is prototype_only |
| `robodm_style_container` | `actual_robodm_dependency_license_blocked` | `8` | `missing` | `512` | `49.798713` | `missing` | `9.264098` | `9.264098` | `55267.118288` | `6` | `47.125842` | `0.0` | `INSUFFICIENT_TELEMETRY` | run bounded raw decode and store-read benchmark in one compute evidence pass |
| `webdataset_streaming` | `historical_webdataset_dependency_approved_pr16_only` | `4` | `missing` | `512` | `954.466104` | `missing` | `476.634326` | `476.634326` | `1074.198756` | `6` | `6.480499` | `0.0` | `FAIL_NON_PRIMARY_WORKER_COUNT` | historical WebDataset evidence is performance FAIL and used for context only; rerun primary worker_count=8 before final ranking |
| `zarr_chunked_store` | `actual_zarr_python310_version_decision_missing` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_PROTOTYPE_ONLY` | actual Zarr route is dependency/version-blocked; local row is prototype_only |
| `gr00t_original_dataloader` | `model_training_side_effect_safety_not_proven` | `8` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `not_run` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | do not execute until Model and Training prove dataloader-only safety |

## Shared Subset/Window Policy

- All benchmarkable rows must use the same ordered `training_window_ids` manifest.
- Raw ZJH fields are action=`action`, state=`observation.state`, and three declared camera refs.
- Candidates without action/state/action_mask equivalence stay out of speed ranking.
- Prototype rows are decision-support only and must not be named as official dependency backends.

## Residual Compute Requirement

- Current evidence includes raw bounded-decode, native bounded container-cache prototype, and historical WebDataset package-backed streaming rows.
- Final acceptance still requires a primary worker_count=8 comparison or explicit Manager/user acceptance of the historical non-primary WebDataset evidence.
- This writer integrates current raw bounded-decode and native bounded container-cache prototype evidence plus historical WebDataset evidence.

## Publication Notes

- `zjh_lerobot_v21_raw` is the no-new-dependency raw baseline.
- `prototype_only` rows are native metadata/report scaffolds, not official backend claims.
- Dependency-backed official routes remain blocked until their exact dependency gates pass.
- Generated store/media/checkpoint/model artifacts must stay out of git.
