# Top-Level Loop Prompt Template

Use this template when User + ChatGPT create a prompt-controlled loop. Replace
every placeholder before treating the loop as executable. Placeholders are not
defaults.

## model_label

`gpt-5.5`

## loop_id

`<loop-id>`

## task_id

`<task-id>`

## goal

`<single-loop-goal>`

## non_goals

- `<explicit-non-goal>`

## context_sources

- `<path-or-reference-to-read>`

## allowed_actions

- `<allowed-local-action-or-connector-action-or-none>`

## feedback_channels

- Manager final response: `<required-status-shape>`
- Owner reports: `<owner-report-directory>`
- Validation evidence: `<validation-evidence-ledger-path>`

## state_paths

- loop spec: `<loop-yaml-path>`
- resolved spec: `<loop-resolved-json-path>`
- plan: `<plan-md-path>`
- owner packets: `<owner-packets-directory>`
- owner reports: `<owner-reports-directory>`
- delivery: `<delivery-md-path>`
- state: `<state-json-path>`
- run log: `<run-log-md-path>`
- checkpoints: `<checkpoints-directory>`

## stop_boundaries

- `<blocked-status-and-condition>`

## budget

- authority: `<budget-policy-from-top-level-prompt>`
- applies_to: `<scope-of-budget>`
- exhausted_evidence_path: `<budget-exhausted-evidence-path>`
- exhausted_status: `<blocked-status>`
- continuation_requires_prompt: `<true-or-false-from-prompt>`

Do not infer numeric budget defaults.

## authorizations

- Owner thread construction: `<authorized-owner-roles-or-none>`
- source writes: `<authorized-or-forbidden-with-scope>`
- publication mutation: `<authorized-or-forbidden-with-target>`
- compute execution: `<authorized-or-forbidden-with-scope>`
- Slurm execution: `<authorized-or-forbidden-with-scope>`
- connector actions: `<authorized-or-forbidden-with-target>`
- cleanup/deletion: `<authorized-or-forbidden-with-scope>`
- endpoint or robot use: `<authorized-or-forbidden-with-scope>`

## owner_thread_plan

```yaml
owner_thread_plan:
  primary_owner: Training
  required_reviewers:
    - Architecture
    - Quality
  consulted_owners:
    - Data
    - Model
  skipped_owners:
    Deployment: no deployment surface
  owner_concurrency:
    max_parallel_owner_threads: <supplied_by_prompt>
  owner_threads:
    Training:
      role_type: persistent_owner
      thread_level: true
      lifecycle: refresh_before_dispatch
      can_spawn_child_agents: true
      child_agent_depth_limit: 1
      requires_role_refresh_before_dispatch: true
      owner_report_required: true
      completed_no_output_is_approval: false
    Architecture:
      role_type: persistent_owner
      thread_level: true
      lifecycle: refresh_before_dispatch
      can_spawn_child_agents: true
      child_agent_depth_limit: 1
      requires_role_refresh_before_dispatch: true
      owner_report_required: true
      completed_no_output_is_approval: false
    Quality:
      role_type: persistent_owner
      thread_level: true
      lifecycle: refresh_before_dispatch
      can_spawn_child_agents: true
      child_agent_depth_limit: 1
      requires_role_refresh_before_dispatch: true
      owner_report_required: true
      completed_no_output_is_approval: false
  owner_packet_paths:
    Training: <owner-packets-directory>/training.md
    Architecture: <owner-packets-directory>/architecture.md
    Quality: <owner-packets-directory>/quality.md
  owner_report_paths:
    Training: <owner-reports-directory>/training.md
    Architecture: <owner-reports-directory>/architecture.md
    Quality: <owner-reports-directory>/quality.md
```

When Tooling or Compute/HPC is routed, include `70-OWNER · Tooling` or
`80-OWNER · Compute/HPC` metadata with `role_type: persistent_owner` and
`lifecycle: create_or_refresh_when_routed`.

## owner_subagent_plan

```yaml
owner_subagent_plan:
  Training:
    max_child_agents: <supplied_by_prompt>
    peak_concurrency: <supplied_by_prompt>
    child_agent_depth_limit: 1
    sequence:
      - child_id: training-planner
        type: Planner
        capability: draft training loop implementation plan
        allowed_write_paths:
          - none
        protected_paths:
          - <protected-path>
        required_output: <child-report-directory>/training-planner.md
        conclusion_values:
          - PASS_PLAN
          - REQUEST_CHANGES
          - BLOCKED_SCOPE
        starts_after:
          - owner_packet_received
        retires_before: <owner-reports-directory>/training.md
      - child_id: training-reviewer
        type: Reviewer
        capability: review no-real-training and child-agent usability
        allowed_write_paths:
          - none
        protected_paths:
          - <protected-path>
        required_output: <child-report-directory>/training-reviewer.md
        conclusion_values:
          - APPROVE
          - REQUEST_CHANGES
          - BLOCKED_SCOPE
        starts_after:
          - training-planner
        retires_before: <owner-reports-directory>/training.md
  Quality:
    max_child_agents: <supplied_by_prompt>
    peak_concurrency: <supplied_by_prompt>
    child_agent_depth_limit: 1
    sequence:
      - child_id: quality-reviewer
        type: Reviewer
        capability: validate scans and gate evidence
        allowed_write_paths:
          - none
        protected_paths:
          - <protected-path>
        required_output: <child-report-directory>/quality-reviewer.md
        conclusion_values:
          - APPROVE
          - REQUEST_CHANGES
          - BLOCKED_SCAN
        starts_after:
          - owner_packet_received
        retires_before: <owner-reports-directory>/quality.md
```

## write_scope

- allowed_write_paths:
  - `<explicit-allowed-write-path>`
- source_writer_concurrency: `<supplied_by_prompt>`
- publication_writer_concurrency: `<supplied_by_prompt>`
- compute_runner_concurrency: `<supplied_by_prompt>`

## protected_paths

- `<explicit-protected-path>`

## plan_gate

```yaml
plan_gate:
  reviewers:
    - Architecture
    - Quality
  child_reports_cannot_bypass_owner_report: true
  required_owner_reports:
    Architecture: <owner-reports-directory>/architecture.md
    Quality: <owner-reports-directory>/quality.md
  pass_condition: every required Owner report exists and concludes with an allowed passing value
  missing_report_status: OWNER_REPORT_MISSING
  completed_no_output_status: OWNER_THREAD_COMPLETED_NO_OUTPUT
```

## delivery_gate

```yaml
delivery_gate:
  reviewers:
    - Quality
    - <domain-reviewer-owner>
  required_owner_reports:
    Quality: <owner-reports-directory>/quality.md
    <domain-reviewer-owner>: <owner-reports-directory>/<domain-reviewer-owner>.md
  pass_condition: every required Owner report exists, every required child retired, validation evidence exists, and scans pass when publication is in scope
  child_reports_cannot_bypass_owner_report: true
```

## pr_behavior

- target PR: `<existing-pr-or-new-draft-pr-policy>`
- expected state: `<draft-or-ready-policy>`
- mutation authorization: `<authorized-or-forbidden>`
- exact head required: `<true-or-false-from-prompt>`

## final_allowed_states

- `PASS`
- `REQUEST_CHANGES`
- `BLOCKED_LOOP_SPEC`
- `BLOCKED_SCOPE`
- `BLOCKED_SCAN`
- `BLOCKED_COMPUTE_AUTH`
- `BLOCKED_COMPUTE_ENV`
- `BLOCKED_COMPUTE_POLICY`
- `FAIL`

## hard_stops

- missing required field
- unresolved placeholder in resolved spec
- routed Owner without Owner thread plan
- routed Owner without subagent plan
- missing Owner packet path
- missing Owner report path
- child-agent depth greater than one
- Tooling or Compute/HPC routed without persistent Owner metadata
- protected path write
- unauthorized connector, compute, Slurm, endpoint, cleanup, or publication

## expected_artifacts

- `RUN_IN_SESSION.md`
- `loop.yaml`
- `loop.resolved.json`
- `plan.md`
- `owner-packets/`
- `owner-reports/`
- `delivery-N.md`
- `state.json`
- `run-log.md`
- `checkpoints/`
- final Manager summary

## tool_memory_policy

- path: `coordination/TOOL_MEMORY.yaml`
- authority: advisory only
- may_not_replace:
  - validation evidence
  - Owner report
  - scan result
  - PR mutation authorization
  - completion-state decision

## compute_execution_policy

- default: governance-only unless explicitly authorized
- login-node work: lightweight local checks only
- Compute/HPC Owner required when compute, GPU, Slurm, scheduler, or login-node
  policy is routed
- ComputeRunner child required for authorized compute execution
- project wrappers required for Slurm work
- scheduler bypass forbidden

If any required field remains unresolved, stop as `BLOCKED_LOOP_SPEC`.
