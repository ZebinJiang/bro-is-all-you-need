# Owner Dispatch Governance

## Purpose

Owner Dispatch Memory records live dispatch health for persistent Owner channels. It is distinct from Tool Memory and is the authority for whether an Owner dispatch produced review evidence.

The canonical machine-readable file is `coordination/OWNER_DISPATCH_MEMORY.yaml`.

## Required schema

Each dispatch memory entry records:

- `task_id`
- `role`
- `owner_thread_name`
- `thread_id`
- `channel_health`
- `sent_turn`
- `status_ping`
- `report_expected`
- `report_path`
- `output_presence`
- `report_presence`
- `classification`
- `role_refresh`
- `resolution_history`

## Classifications

- `OWNER_REPORT_RECEIVED`: visible Owner output and required report exist.
- `OWNER_REPORT_MISSING`: output exists but the required report is absent.
- `OWNER_THREAD_COMPLETED_NO_OUTPUT`: thread turn completed but no visible Owner output or report exists.
- `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`: dispatch channel is silent enough that the role must be refreshed or replaced before approval.
- `OWNER_REPLACED_BY_APPROVED_SHORT_LIVED_REVIEWER`: a scoped replacement reviewer produced accepted evidence after the silent Owner channel was recorded.

## Approval rule

Only `OWNER_REPORT_RECEIVED` with valid report evidence can satisfy Owner approval. Thread completion metadata alone is not approval. Missing output, missing report, or a silent channel must block acceptance.

For `GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001`, missing output, missing reports, or
silent Owner channels also block activation. Child reports cannot satisfy the
activation gate directly; the parent Owner report must cite them, summarize
risks, and record retirement.

## Resolution rule

A silent Owner entry remains unresolved until the Manager records one of:

- refreshed persistent Owner thread id and passing smoke;
- accepted replacement reviewer report;
- explicit user decision to waive that Owner evidence for the loop.

The resolution history must preserve the original silent-dispatch classification.
# Runtime Memory And Compute Hardening

Owner dispatch is fail-closed when an Owner thread has no active turn to steer. The durable status is `OWNER_THREAD_NO_ACTIVE_TURN_TO_STEER`. A completed, archived, missing, or UI-unsteerable Owner thread is not approval and cannot receive new work. The Manager must route no work to that Owner until a user-authorized replacement Owner thread is selected, refreshed, recorded in `coordination/THREAD_REGISTRY.yaml`, and recorded in `coordination/OWNER_REFRESH_LEDGER.md`.

The Data Owner replacement for this hardening task is `019f0c18-8c51-77d2-89bc-8b6ed5f85399`. The previous Data Owner registry entry is archived/unsteerable and must not receive future dispatch.

Tool Memory is advisory-only. It may record candidate operational patterns, but it cannot authorize validation, compute, PR mutation, publication, or Owner approval. `GIT_LFS_LOCKSVERIFY_PROXY_TIMEOUT_CANDIDATE` remains candidate-only; `locksverify=false` must not become a default or canonical publication behavior.

Any command classified as unknown or heavy validation must route through Compute/HPC before execution. Login-node CPU saturation is not a reason to continue locally; it is a reason to stop and route.
