# PR30 Result Consistency Audit

PR #30 now has two distinct evidence classes:

1. adapter-v0/v1 diagnostic timing, which is useful for identifying AutoVLA
   adapter/reader overhead;
2. actual dataloader worker evidence, which is required before any converted
   backend can be considered comparable.

The adapter-v1 numbers remain diagnostic-only because they record
`worker_count_label=configured_8` with `actual_worker_count=not_measured`.
They must not be treated as backend-selection evidence.

## Current Decision

`NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS`

No converted backend winner is selected. Compute-W2 provides the bounded final
PR #30 runnable-candidate ranking, but it does not close D1 native-route or
prompt-contract metric gaps.

Compute-W2 provided wrapper-backed source-dataset evidence for the primary
worker_count=8 matrix and the worker_count `0,2,4,8` secondary sweep. The
runnable primary ranking is:

1. D4 `zjh_webdataset_tar`: `501.775424` samples/s
2. D5 `zjh_robodm_container_v1`: `295.03279` samples/s
3. D3 `zjh_lerobot_v3_local`: `203.022981` samples/s
4. D1b/D2 `zjh_lerobot_v21_autovla_adapter`: `24.7923` samples/s

`NO_BACKEND_WINNER` remains correct: D1a is still blocked, D6 is not
implemented, and final timing comparability still lacks the full prompt-contract
metric matrix.

## Consistency Rules

- Prior adapter-v1 tables may remain as overhead diagnostics.
- Compute-W2 actual-worker tables are the current bounded runnable-candidate
  ranking.
- Actual-worker tables must record numeric actual worker evidence.
- Rows with missing worker evidence must be blocked, not RUN.
- RUN rows must include action, state, language, action mask, and three RGB
  payloads.
- Compute-W2 generated artifacts remain under task-local `runs/tmp/**` and
  `datasets/working/autovla_pr30_final_dataloader_perf_v1/w2`. Historical
  pre-W2 actual-worker evidence may reference
  `datasets/working/autovla_actual_worker_bakeoff_v1/**`, but that is not the
  W2 working root.
- No GPU200, training, model/checkpoint/tokenizer/HF/W&B/endpoint/robot
  behavior is authorized by these docs. Slurm evidence is limited to the
  bounded Compute-W2 dataloader benchmark through the project wrapper.
