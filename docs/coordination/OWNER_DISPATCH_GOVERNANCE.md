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
