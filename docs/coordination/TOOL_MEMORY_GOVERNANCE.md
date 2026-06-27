# Tool Memory Governance

## Purpose

Tool Memory records observed tool behavior, connector caveats, local command quirks, and safe fallbacks. It is advisory memory only.

The canonical machine-readable file is `coordination/TOOL_MEMORY.yaml`. Review decisions are recorded in `coordination/TOOL_MEMORY_REVIEW_LEDGER.md`.

## Hard limits

Tool Memory must not replace:

- validation evidence;
- Owner approval;
- Architecture or Quality review;
- scan results;
- exact-head checks;
- PR mutation authorization;
- PR visibility decisions;
- commit, push, or merge decisions;
- completion-state updates.

Tool Memory cannot authorize connector actions, compute execution, dependency edits, cleanup, branch mutation, publication, robot endpoint use, credentials, or external service calls.

Tool Memory is advisory only. A matching entry may help a reviewer remember a known tool behavior, but the current loop must still collect fresh command evidence and obey the resolved loop spec.

## Entry schema

Every entry in `coordination/TOOL_MEMORY.yaml` must use the approved schema or be explicitly pending and inactive:

- `id`
- `category`
- `generalized_signature`
- `detection_commands_or_signals`
- `approved_recovery_pattern`
- `prohibited_recovery_actions`
- `owner_responsible`
- `last_reviewed_by`
- `evidence_links`
- `scope`
- `expiry_or_review_trigger`
- `approval_state`
- `status`

Entries with `status: active` require `approval_state` to show approval by Tooling and Quality. Compute-related entries also require Compute/HPC approval. Entries awaiting either approval must remain `status: inactive` and must not be used as acceptance evidence.

## Allowed use

The Manager may use Tool Memory to:

- remember that a tool often fails under sandbox constraints;
- choose a documented local fallback when the loop spec permits it;
- record whether proxy use was observed for a network command;
- document known parse commands for governance files;
- preserve a non-authoritative note for future reviewers.

## Review rule

Every Tool Memory entry used in a loop must be reviewed in the validation ledger or report. If Tool Memory conflicts with current evidence, current evidence wins.

New entries require Tooling and Quality approval before active use. Entries that affect compute, Slurm, GPU execution, dependency changes, scheduler behavior, or login-node policy additionally require Compute/HPC approval. Tool Memory remains advisory after approval; it never grants connector, compute, publication, mutation, completion, or escalation authority.
