# Prompt-Controlled Loop Protocol

## Purpose

This protocol defines the fail-closed contract for prompt-controlled review loops in the Codex-only GenesisVLA control plane.

The active model label for this governance surface is `gpt-5.5`. A loop template, state file, Owner report, or Tool Memory entry must not promote another model label as active unless a top-level user prompt explicitly changes the project model label.

## Control rule

The Manager proceeds from the top-level prompt and the resolved loop spec. The Manager does not start by interviewing the user. The Manager asks the user only when a required field, authorization, budget policy, timeout policy, validation path, publication gate, external action, deletion, credential, robot endpoint, or safety decision is absent or ambiguous.

When a required element is missing or ambiguous, the loop status is `BLOCKED_LOOP_SPEC`. The Manager records the missing element and stops before dispatch, execution, PR mutation, completion-state mutation, or publication.

## Required loop spec fields

Every executable loop spec must contain all fields below before the Manager can run it:

- `loop_id`
- `task_id`
- `model_label`
- `top_level_prompt`
- `objective`
- `in_scope`
- `out_of_scope`
- `branch`
- `base_head`
- `expected_head`
- `allowed_write_paths`
- `protected_paths`
- `owner_routes`
- `owner_dispatch_memory_path`
- `tool_memory_policy`
- `budget_policy`
- `timeout_policy`
- `connector_action_policy`
- `compute_policy`
- `validation_evidence_ledger`
- `scan_gate`
- `pr_visibility_gate`
- `draft_state_policy`
- `completion_gate`
- `rollback_policy`

If any field is absent, empty where a value is required, or inconsistent with repository governance, the Manager records `BLOCKED_LOOP_SPEC`.

The empty-value check is recursive for the entire resolved spec. Any present empty string, empty list, empty object, or JSON null at any depth blocks as `BLOCKED_LOOP_SPEC` with a `nested_empty=...` diagnostic path. Explicit booleans and numbers are allowed when the surrounding policy makes them meaningful.

The required-field check is also recursive for required nested leaves. A concrete-looking object still blocks if any of these leaves are missing, empty, or unresolved:

- `owner_routes.primary`
- `owner_routes.reviewers`
- `tool_memory_policy.path`
- `tool_memory_policy.authority`
- `budget_policy.authority`
- `budget_policy.applies_to`
- `budget_policy.exhausted_evidence_path`
- `budget_policy.exhausted_status`
- `budget_policy.continuation_requires_prompt`
- `timeout_policy.authority`
- `timeout_policy.applies_to`
- `timeout_policy.timeout_evidence_path`
- `timeout_policy.timeout_status`
- `timeout_policy.continuation_requires_prompt`
- `connector_action_policy.authorized_actions`
- `connector_action_policy.fallback`
- `compute_policy.compute_authorized`
- `compute_policy.authorized_actions`
- `compute_policy.purpose`
- `compute_policy.command_or_wrapper`
- `compute_policy.execution_location`
- `compute_policy.resource_class`
- `compute_policy.resource_source`
- `compute_policy.evidence_path`
- `compute_policy.safety_stop_condition`
- `compute_policy.expected_output`
- `compute_policy.rollback_or_cleanup_note`
- `compute_policy.authorizing_prompt_or_task`
- `compute_policy.slurm_authorized`
- `compute_policy.escalation_authorized`
- `compute_policy.scheduler_policy_ack`
- `compute_policy.scheduler_rejection_status`
- `validation_evidence_ledger.path`
- `scan_gate.required`
- `scan_gate.blocker_status`
- `pr_visibility_gate.expected_state`
- `completion_gate.missing_spec_status`

## Budget and timeout policy

Budget and timeout values must come from the top-level prompt or a resolved loop spec. The Manager must not invent fallback values.

Valid budget and timeout policies must identify:

- which authority supplied the policy;
- what work the policy applies to;
- where exhausted-budget evidence is written;
- which status is reported when the budget is exhausted;
- whether continuation requires a new top-level prompt.

Template examples may contain placeholders such as `<budget-policy-from-top-level-prompt>`. These placeholders are examples only and are not defaults.

## Connector-action fallback

Connector actions include GitHub PR mutation, issue comments, workflow re-runs, thread-management actions, automation updates, and any external service operation.

Connector actions are allowed only when the loop spec explicitly authorizes the action, target, expected head, visibility state, and rollback or no-op fallback.

If a connector action is unavailable but not required for completion, the Manager records the fallback path and continues with local evidence only. If the connector action is required for completion, the Manager records the relevant blocked status and stops before claiming completion.

Tool Memory may help remember known connector behavior, but it must not authorize a connector action.

## Compute-action fallback

Compute, Slurm, GPU, dependency, scheduler, and external execution actions require the complete authorization fields defined by `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md` and `coordination/COMPUTE_EXECUTION_STATE.yaml`.

Prompt-controlled loops must not invent governance resource defaults. Slurm commands require explicit compute authorization, explicit Slurm authorization, and project-wrapper routing. Escalated shell execution is separate from compute authorization and cannot be inferred from it.

Compute blockers use the named statuses `BLOCKED_COMPUTE_AUTH`, `BLOCKED_COMPUTE_ENV`, and `BLOCKED_COMPUTE_POLICY`. Scheduler rejection, scheduler-policy conflict, or any attempted bypass of scheduler policy, cgroups, accounting, partition/QoS limits, or site controls is a hard stop before retry, mutation, or completion.

## Exact-head and PR visibility gates

Any PR mutation, draft PR publication, PR body update, ready-for-review transition, merge, or remote branch update requires:

- local scans passed for the mutation scope;
- no scan blocker remains;
- current local head matches the loop `expected_head`;
- the target PR or branch head matches the expected remote head when a remote check is part of the loop;
- the PR visibility state matches the loop spec.

A `REQUEST_CHANGES` draft PR path is scan-gated and exact-head-gated. Scan blockers stop the path. A draft PR remains draft unless the top-level prompt explicitly authorizes a ready transition.

## Scan-blocker hard stop

Secret, artifact, large-file, large text-diff, forbidden-path, dependency, source/test/runtime, M3/PR path, Slurm-script, DevSpace-internal-evidence, and drift scans are hard stops when they report a blocker. The Manager records the blocker and stops before commit, push, PR mutation, branch mutation, cleanup, or completion.

## Validation-evidence ledger

Each loop requires a validation-evidence ledger with:

- command;
- working directory;
- start state;
- result;
- evidence path or transcript summary;
- skipped checks and reason;
- owner or reviewer responsible for accepting the evidence;
- residual risk;
- rollback note.

Missing validation evidence path is `BLOCKED_LOOP_SPEC`.

## Owner output requirement

An Owner turn that completes without an Owner report or without visible output is not approval. It must be classified as `OWNER_THREAD_COMPLETED_NO_OUTPUT` and, when repeated or attached to a role handoff, as `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`.

The Manager must use `coordination/OWNER_DISPATCH_MEMORY.yaml`, not Tool Memory, to record this condition.

## Completion gate

A loop is complete only when all required reports, validation evidence, scan gates, exact-head gates, PR visibility gates, and completion-state rules are satisfied. Tool Memory, thread completion state, or local belief cannot replace those gates.
