# Prompt-Controlled Loop Protocol

## Purpose

This protocol defines the fail-closed contract for prompt-controlled review
loops in the Codex-only AutoVLA control plane.

The active model label for this governance surface is `gpt-5.5`. A loop
template, state file, Owner report, or Tool Memory entry must not promote
another model label as active unless a top-level user prompt explicitly changes
the project model label.

`docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md` is the normative runtime layer
for prompt-controlled loop v2. This protocol supplies the resolved-spec and
gate rules that make that runtime enforceable.

`docs/coordination/LOOP_ACTIVATION_GATE.md` defines the draft, installed, and
activated lifecycle. `docs/coordination/OWNER_RUNTIME_SMOKE.md` defines the
required activation smoke.
`docs/coordination/OWNER_TOPOLOGY_GOVERNANCE.md` defines the fail-closed
owner_topology contract for implementation, review, publication, tool recovery,
and compute role separation.

## Thread Reasoning Setting

Prompt-controlled loop v2 uses the Codex thread tool schema value
`thinking: "xhigh"` for persistent Owner creation, Owner refresh, Owner
dispatch, worker-thread creation, and follow-up dispatch whenever the field is
available. Natural-language budget or profile words such as "maximum" do not
authorize the schema value `max` in this repository. If the field is
unavailable, the Manager records `thinking=xhigh requested/not exposed` and
continues only when all other Owner dispatch evidence is valid.

## Control Rule

The Manager proceeds from the top-level prompt and the resolved loop spec. The
Manager does not start by interviewing the user. The Manager asks the user only
when a required field, authorization, budget policy, timeout policy, validation
path, publication gate, external action, deletion, credential, robot endpoint,
or safety decision is absent or ambiguous.

When a required element is missing or ambiguous, the loop status is
`BLOCKED_LOOP_SPEC`. The Manager records the missing element and stops before
Owner dispatch, child-agent launch, execution, PR mutation, completion-state
mutation, publication, or acceptance.

When owner role separation is missing or unsafe, the loop status is
`BLOCKED_OWNER_TOPOLOGY`. This includes non-empty topology `write_scope`
without implementation Owner, PR/publication action without publisher Owner,
tool recovery without Tooling Owner, compute action without Compute/HPC Owner,
and reviewer-does-not-patch violations on risky cross-cutting work.

## Runtime Dispatch Rule

The only normal runtime hierarchy is:

```text
Manager thread -> persistent Owner thread -> Owner-owned child agents
```

The Manager dispatches task packets to routed Owner threads. Owner threads own
their child-agent plans, launch only top-level-prompt-authorized child agents,
collect child outputs, and produce Owner reports. The Manager may not directly
spawn domain child agents except for an explicitly authorized bootstrap
governance fallback. Bootstrap fallback evidence must be labeled and cannot
prove future Owner-runtime dispatch.

Child-agent reports cannot bypass Owner reports. A child report is usable gate
evidence only when it is referenced by the parent Owner report and the child has
retired.

## Activation Rule

Prompt-controlled loop v2 is not active merely because PR #7 is merged or the
governance files exist. Normal loop mode is blocked as `LOOP_NOT_ACTIVATED`
until `GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` passes.

The activation smoke is governance-only. It routes Quality as primary,
Architecture as reviewer, and Tooling as consulted. It forbids ToolEnvRunner,
ComputeRunner, dependency recovery, connector mutation, PR mutation, PR #6
mutation, compute, Slurm, M3 source/runtime changes, and real training.

Spec validation is separate from runtime dispatch proof. A passing
`run-loop.py` result is not an Owner runtime smoke pass.

## Required Loop Spec Fields

Every executable loop spec must contain all fields below before the Manager can
run it:

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
- `owner_topology`
- `owner_routes`
- `owner_thread_plan`
- `owner_subagent_plan`
- `owner_dispatch_memory_path`
- `tool_memory_policy`
- `budget_policy`
- `timeout_policy`
- `connector_action_policy`
- `compute_policy`
- `validation_evidence_ledger`
- `plan_gate`
- `delivery_gate`
- `scan_gate`
- `pr_visibility_gate`
- `draft_state_policy`
- `completion_gate`
- `rollback_policy`
- `activation_gate`
- `final_allowed_states`

If any field is absent, empty where a value is required, or inconsistent with
repository governance, the Manager records `BLOCKED_LOOP_SPEC`.

The empty-value check is recursive for the entire resolved spec. Any present
empty string, empty list, empty object, or JSON null at any depth blocks as
`BLOCKED_LOOP_SPEC` with a `nested_empty=...` diagnostic path. Explicit booleans
and numbers are allowed when the surrounding policy makes them meaningful.

The required-field check is also recursive for required nested leaves. A
concrete-looking object still blocks if any of these leaves are missing, empty,
or unresolved:

- `owner_routes.primary`
- `owner_routes.reviewers`
- `owner_topology.task_class`
- `owner_topology.spec_owner`
- `owner_topology.delivery_owner`
- `owner_topology.reviewer_owners`
- `owner_topology.fallback_policy.blocked_status`
- `owner_topology.fallback_policy.compatibility_shim_decision`
- `owner_thread_plan.primary_owner`
- `owner_thread_plan.required_reviewers`
- `owner_thread_plan.owner_concurrency.max_parallel_owner_threads`
- `owner_thread_plan.owner_threads`
- `owner_thread_plan.owner_packet_paths`
- `owner_thread_plan.owner_report_paths`
- `owner_subagent_plan`
- `plan_gate.reviewers`
- `plan_gate.required_owner_reports`
- `plan_gate.pass_condition`
- `delivery_gate.reviewers`
- `delivery_gate.required_owner_reports`
- `delivery_gate.pass_condition`
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
- `connector_action_policy.target`
- `connector_action_policy.pr_mutation_allowed`
- `connector_action_policy.publication_allowed`
- `connector_action_policy.ready_transition_allowed`
- `connector_action_policy.merge_allowed`
- `connector_action_policy.exact_head_required`
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
- `scan_gate.evidence_path`
- `scan_gate.blockers_present`
- `pr_visibility_gate.expected_state`
- `pr_visibility_gate.target_pr_number`
- `pr_visibility_gate.target_pr_url`
- `pr_visibility_gate.expected_remote_head`
- `pr_visibility_gate.current_visibility`
- `pr_visibility_gate.mutation_authorized`
- `pr_visibility_gate.authorized_mutations`
- `pr_visibility_gate.visibility_evidence_path`
- `draft_state_policy.preserve_draft`
- `draft_state_policy.ready_transition_authorized`
- `draft_state_policy.ready_transition_authority`
- `draft_state_policy.unauthorized_ready_status`
- `completion_gate.missing_spec_status`
- `activation_gate.governance_state`
- `activation_gate.installed`
- `activation_gate.activated`
- `activation_gate.normal_loop_mode_allowed`
- `activation_gate.normal_loop_mode_requested`
- `activation_gate.activation_required_task`
- `activation_gate.activation_task`
- `activation_gate.runtime_smoke_required`
- `activation_gate.runtime_smoke_status`
- `activation_gate.runtime_smoke_evidence_path`
- `activation_gate.normal_loop_blocked_status`
- `activation_gate.owner_dispatch_blocked_status`
- `activation_gate.owner_thread_required_status`
- `activation_gate.missing_spec_status`
- `activation_gate.spec_validation_is_runtime_dispatch_proof`
- `final_allowed_states`

## Owner Plans

The top-level prompt controls Owner routing, Owner concurrency, child-agent
sequence, child-agent concurrency, write ownership, and gate reviewers. The
Manager must not invent these values.

Every plan must carry `owner_topology`. The topology identifies `spec_owner`,
`delivery_owner`, implementation Owner(s), reviewer Owner(s), `publisher_owner`,
`tooling_owner`, and `compute_owner` as applicable to the task class. Missing or
unsafe topology stops before Owner dispatch as `BLOCKED_OWNER_TOPOLOGY`.

For AutoVLA repo-wide rename style work, Product/Spec owns the spec,
Engineering/Codebase Migration owns implementation delivery, Data and Model are
reviewer Owners unless the prompt assigns data/model contract write scopes, and
compatibility shims return `READY_FOR_USER_DECISION_COMPATIBILITY_SHIM` rather
than being inferred.

`owner_thread_plan` must define:

- primary Owner;
- required reviewer Owners;
- consulted Owners, if any;
- skipped Owners and reasons, if any;
- Owner concurrency supplied by the top-level prompt;
- per-routed-Owner thread metadata;
- Owner packet path for every routed Owner;
- Owner report path for every routed Owner.

`owner_subagent_plan` must define every routed Owner's child-agent sequence,
allowed write paths, protected paths, required child report path, conclusion
values, start dependencies, and retirement target. Missing
`owner_subagent_plan`, a routed Owner without a subagent plan, child-agent depth
greater than one, or Tooling/Compute routed without persistent Owner metadata is
`BLOCKED_LOOP_SPEC`.

## Plan Gate

The plan gate is a required Owner-report gate. The Manager drafts `plan.md`,
sends it to designated reviewer Owners, and accepts the plan only when every
required Owner report exists and passes.

Reviewer Owners may launch Reviewer child agents only when the top-level prompt
authorizes that child-agent sequence. Completed Owner turns with no output,
missing Owner reports, or child-agent reports without parent Owner reports do
not satisfy the plan gate.

## Delivery Gate

The delivery gate is a required Owner-report gate. The Primary Owner executes
delivery through Owner-owned child agents, consolidates child reports into one
Owner report, and then Quality plus required domain reviewer Owners review the
delivery.

The Manager accepts delivery only when required Owner reports exist, required
child agents have retired, validation evidence exists, scans are complete when
publication is involved, and the delivery gate passes. Child-agent reports alone
are never approval.

## Budget and Timeout Policy

Budget and timeout values must come from the top-level prompt or a resolved loop
spec. The Manager must not invent fallback values.

Valid budget and timeout policies must identify:

- which authority supplied the policy;
- what work the policy applies to;
- where exhausted-budget evidence is written;
- which status is reported when the budget is exhausted;
- whether continuation requires a new top-level prompt.

Template examples may contain placeholders such as
`<budget-policy-from-top-level-prompt>`. These placeholders are examples only
and are not defaults.

## Connector-Action Fallback

Connector actions include GitHub PR mutation, issue comments, workflow re-runs,
thread-management actions, automation updates, and any external service
operation.

Connector actions are allowed only when the loop spec explicitly authorizes the
action, target, expected head, visibility state, and rollback or no-op fallback.

If a connector action is unavailable but not required for completion, the
Manager records the fallback path and continues with local evidence only. If the
connector action is required for completion, the Manager records the relevant
blocked status and stops before claiming completion.

Tool Memory may help remember known connector behavior, but it must not
authorize a connector action.

## Compute-Action Fallback

Compute, Slurm, GPU, dependency, scheduler, and external execution actions
require the complete authorization fields defined by
`docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md` and
`coordination/COMPUTE_EXECUTION_STATE.yaml`.

Prompt-controlled loops must not invent governance resource defaults. Slurm
commands require explicit compute authorization, explicit Slurm authorization,
and project-wrapper routing. Escalated shell execution is separate from compute
authorization and cannot be inferred from it.

Compute/HPC must be routed as a persistent Owner when compute, GPU, Slurm,
scheduler, or login-node policy work is in scope. ComputeRunner is a
Compute/HPC-owned child agent and may run only when the prompt authorizes the
exact action and scope.

Compute blockers use the named statuses `BLOCKED_COMPUTE_AUTH`,
`BLOCKED_COMPUTE_ENV`, and `BLOCKED_COMPUTE_POLICY`. Scheduler rejection,
scheduler-policy conflict, or any attempted bypass of scheduler policy, cgroups,
accounting, partition/QoS limits, or site controls is a hard stop before retry,
mutation, or completion.

## Exact-Head and PR Visibility Gates

Any PR mutation, draft PR publication, PR body update, ready-for-review
transition, merge, or remote branch update requires:

- local scans passed for the mutation scope;
- no scan blocker remains;
- current local head matches the loop `expected_head`;
- the target PR or branch head matches the expected remote head when a remote
  check is part of the loop;
- the PR visibility state matches the loop spec.

A `REQUEST_CHANGES` draft PR path is scan-gated and exact-head-gated. Scan
blockers stop the path. A draft PR remains draft unless the top-level prompt
explicitly authorizes a ready transition.

PR #6 is special during PR7 activation hardening: it may be represented by a
review-only exact-head example, but must not be mutated, marked ready, merged,
commented on, or otherwise changed unless a future top-level prompt explicitly
authorizes that exact action after loop activation.

## Scan-Blocker Hard Stop

Secret, artifact, large-file, large text-diff, forbidden-path, dependency,
source/test/runtime, M3/PR path, Slurm-script, DevSpace-internal-evidence, and
drift scans are hard stops when they report a blocker. The Manager records the
blocker and stops before commit, push, PR mutation, branch mutation, cleanup, or
completion.

## Validation-Evidence Ledger

Each loop requires a validation-evidence ledger with:

- command;
- working directory;
- start state;
- result;
- evidence path or transcript summary;
- skipped checks and reason;
- Owner or reviewer responsible for accepting the evidence;
- residual risk;
- rollback note.

Missing validation evidence path is `BLOCKED_LOOP_SPEC`.

## Owner Output Requirement

An Owner turn that completes without an Owner report or without visible output
is not approval. It must be classified as `OWNER_THREAD_COMPLETED_NO_OUTPUT`
and, when repeated or attached to a role handoff, as
`ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`.

The Manager must use `coordination/OWNER_DISPATCH_MEMORY.yaml`, not Tool Memory,
to record this condition.

## Completion Gate

A loop is complete only when all required Owner reports, child-agent retirement
evidence, validation evidence, scan gates, exact-head gates, PR visibility
gates, and completion-state rules are satisfied. Tool Memory, child-agent
reports alone, thread completion state, or local belief cannot replace those
gates.

Before activation, normal-loop completion is impossible. The only allowed
pre-activation passing state is the runtime-smoke pass status
`LOOP_V2_OWNER_RUNTIME_SMOKE_PASS`.
# Runtime Memory And Compute Policy Extension

Resolved loop specs must fail closed when an Owner thread has no active turn to steer. `owner_replacement_policy.no_active_turn_status` must be `OWNER_THREAD_NO_ACTIVE_TURN_TO_STEER` when replacement is relevant, and replacement must be user-authorized, role-matched, and reflected in `coordination/THREAD_REGISTRY.yaml`.

Resolved loop specs that mention validation commands must include `compute_command_classification`. Unknown classification, heavy validation, or compute-required commands require Compute/HPC Owner routing and explicit compute policy. Heavy validation on the login node is forbidden unless explicitly allowed in the resolved spec.

Raw `srun` or `sbatch` authorization without Compute/HPC Owner routing and compute budget is invalid. Scheduler policy rejection cannot be bypassed. Git LFS `locksverify=false` is candidate-only advisory memory and cannot be the default or canonical publication behavior.
