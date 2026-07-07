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

`NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`

No converted backend winner is selected. The actual-worker benchmark
implementation is intended to provide the next compute-runnable evidence packet,
not to choose a final backend during Data-W1R.

Compute-W1R provided wrapper-backed source-dataset evidence for D2-D5 worker
counts `0,2,4,8`. Data-W2 keeps that evidence as execution proof while preserving
`NO_BACKEND_WINNER`: D1 is still blocked, D6 is not implemented, and final
timing comparability still lacks the full prompt-contract metric matrix.

## Consistency Rules

- Prior adapter-v1 tables may remain as overhead diagnostics.
- Actual-worker tables must record numeric actual worker evidence.
- Rows with missing worker evidence must be blocked, not RUN.
- RUN rows must include action, state, language, action mask, and three RGB
  payloads.
- Generated artifacts remain under task-local `runs/tmp/**` or
  `datasets/working/autovla_actual_worker_bakeoff_v1/**`.
- No GPU200, Slurm, training, model/checkpoint/tokenizer/HF/W&B/endpoint/robot
  behavior is authorized by these docs.
