# Q-W1 Quality Governance Implementation Report

Task: GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001
Role: Q-W1, Quality sole governance writer
Branch: dev/governance-prompt-loop-v2-owner-retain
Starting HEAD: 46036868dabe93b8819ccac23fe0ee9246d8cff4
Conclusion: PASS

## Changed Files

- `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md`
- `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
- `docs/coordination/OWNER_ROLE_REGISTRY.md`
- `docs/coordination/NEW_THREAD_BOOTSTRAP.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `docs/coordination/LOOP_HARNESS_GOVERNANCE.md`
- `coordination/OWNER_ROLE_REGISTRY.yaml`
- `coordination/PROGRAM_STATE.yaml`
- `coordination/THREAD_REGISTRY.yaml`
- `coordination/loops/templates/TOP_LEVEL_LOOP_PROMPT.md`
- `coordination/loops/templates/NEW_THREAD_START.md`
- `coordination/loops/templates/OWNER_THREAD_START.md`
- `coordination/loops/templates/OWNER_TASK_PACKET.md`
- `coordination/loops/templates/OWNER_SUBAGENT_PLAN.yaml`
- `coordination/loops/templates/OWNER_REPORT.md`
- `coordination/loops/templates/SUBAGENT_REPORT.md`
- `coordination/loops/templates/plan.md`
- `coordination/loops/templates/delivery-N.md`
- `coordination/loops/templates/state.json`
- `coordination/loops/templates/run-log.md`
- `coordination/loops/templates/run-loop.py`
- `coordination/reports/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/owner-quality-implementation.md`

No source, test, dependency, Slurm, dataset, checkpoint, code-input, PR #6, or
M3 implementation paths were modified.

## Gap Analysis Summary

The Manager gap analysis and Wave 1 reviewers agreed that PR #7 had useful
fail-closed prompt-loop governance, Tool Memory separation, compute policy, and
Owner Dispatch Memory, but it did not yet make the intended runtime
machine-checkable:

Manager thread -> persistent Owner thread -> Owner-owned child agents -> Owner
report -> Manager plan and delivery gates.

The missing pieces were a normative runtime layer, eight thread-level Owners,
Owner packet/report templates, Owner-owned child-agent plans, plan/delivery
Owner-report gates, portable artifact state, and validator checks.

## Runtime Contract Added

Created `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md` as the normative
runtime contract. It defines:

- Manager -> persistent Owner thread -> Owner-owned child-agent hierarchy;
- eight thread-level Owners;
- Owner task packet requirements;
- Owner-owned child-agent types;
- `owner_subagent_plan` schema;
- top-level prompt control over Owner and child-agent parallelism;
- plan gate and delivery gate sequences;
- portable artifacts;
- PR-visible terminal states;
- Wave-to-runtime mapping.

## Owner Role Registry Corrections

Updated the Markdown and YAML registries so Architecture, Training, Data, Model,
Deployment, Quality, Tooling, and Compute/HPC are persistent thread-level Owners
when routed.

Each domain Owner now records:

- `role_type: persistent_owner`
- `thread_level: true`
- `can_spawn_child_agents: true`
- `child_agent_depth_limit: 1`
- `requires_role_refresh_before_dispatch: true`
- `owner_report_required: true`
- `completed_no_output_is_approval: false`

## Tooling And Compute/HPC Corrections

Tooling now uses `70-OWNER · Tooling` and Compute/HPC now uses
`80-OWNER · Compute/HPC`. Both use
`lifecycle: create_or_refresh_when_routed` and block as
`OWNER_THREAD_REQUIRED` or `ROLE_REFRESH_REQUIRED` when routed but unavailable.

Tooling owns `ToolEnvRunner`. Compute/HPC owns `ComputeRunner`. Quality remains
the required gate for publication and post-tooling validation.

## Prompt And Plan Schemas

Updated `TOP_LEVEL_LOOP_PROMPT.md` with full required sections:

- `model_label`
- `loop_id`
- `task_id`
- `goal`
- `non_goals`
- `context_sources`
- `allowed_actions`
- `feedback_channels`
- `state_paths`
- `stop_boundaries`
- `budget`
- `authorizations`
- `owner_thread_plan`
- `owner_subagent_plan`
- `write_scope`
- `protected_paths`
- `plan_gate`
- `delivery_gate`
- `pr_behavior`
- `final_allowed_states`
- `hard_stops`
- `expected_artifacts`
- `tool_memory_policy`
- `compute_execution_policy`

The template keeps `gpt-5.5`, uses placeholders for prompt-supplied budget and
concurrency values, and does not introduce numeric future budget defaults.

## New Runtime Templates

Created:

- `OWNER_THREAD_START.md`: pasteable Owner startup/refresh prompt with
  `ROLE_REFRESHED_FOR_GVLA_LOOP_V2` handshake.
- `OWNER_TASK_PACKET.md`: Manager-to-Owner dispatch packet.
- `OWNER_SUBAGENT_PLAN.yaml`: parseable child-agent plan template.
- `OWNER_REPORT.md`: Owner report requiring child-agent evidence and
  retirement ledger.
- `SUBAGENT_REPORT.md`: child-agent report requiring parent Owner, scope,
  evidence, result, risks, and retirement status.

## Portable Artifact Updates

Updated `plan.md`, `delivery-N.md`, `state.json`, and `run-log.md` so they carry:

- Owner thread plan;
- Owner packets;
- child-agent plan;
- child-agent report references;
- Owner reports;
- plan gate reviewers;
- delivery gate reviewers;
- concurrency and serial write plan;
- Owner refresh status;
- child state;
- retirement state;
- checkpoints.

## Protocol And Operating Model Updates

Updated prompt protocol, Manager startup, Team model, New Thread bootstrap, and
Loop Harness governance so:

- Manager dispatches to Owner threads;
- Owner threads launch child agents;
- Manager cannot directly spawn domain child agents except authorized bootstrap
  fallback;
- plan and delivery gates require Owner reports;
- child-agent reports cannot bypass Owner reports;
- completed Owner turn with no output remains non-approval.

## run-loop.py Validator Changes

`coordination/loops/templates/run-loop.py` remains validator-only. It now blocks:

- missing `owner_thread_plan`;
- missing `owner_subagent_plan`;
- routed Owner without subagent plan;
- routed Owner without thread metadata;
- Tooling or Compute/HPC routed without persistent Owner metadata;
- Tooling or Compute/HPC routed with invalid lifecycle;
- missing Owner packet path;
- missing Owner report path;
- missing plan or delivery gate;
- child-agent depth greater than one;
- unresolved placeholders.

Python docstrings and comments remain Chinese.

## Validation Evidence

Workspace preflight:

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/governance-prompt-loop-v2-owner-retain`
- git root: same path
- branch: `dev/governance-prompt-loop-v2-owner-retain`
- HEAD: `46036868dabe93b8819ccac23fe0ee9246d8cff4`
- starting status: clean

TDD red check:

- Before patch, `red-valid-without-owner-thread-plan.json` passed the old
  validator even though it omitted the new Owner runtime fields.
- After patch, the same fixture blocks as `BLOCKED_LOOP_SPEC`.

Required validator negative tests:

- missing `owner_thread_plan`: `BLOCKED_LOOP_SPEC`
- missing `owner_subagent_plan`: `BLOCKED_LOOP_SPEC`
- routed Owner without subagent plan: `BLOCKED_LOOP_SPEC`
- Tooling/Compute routed as invalid non-persistent roles: `BLOCKED_LOOP_SPEC`
- child-agent depth greater than one: `BLOCKED_LOOP_SPEC`

Valid concrete spec:

- `valid-thread-owner-runtime.json`: `PASS loop spec required fields present`

Parse and syntax checks:

- YAML OK:
  - `coordination/OWNER_ROLE_REGISTRY.yaml`
  - `coordination/PROGRAM_STATE.yaml`
  - `coordination/THREAD_REGISTRY.yaml`
  - `coordination/loops/templates/OWNER_SUBAGENT_PLAN.yaml`
- JSON OK:
  - `coordination/loops/templates/state.json`
  - `coordination/loops/templates/loop.resolved.json`
- Python syntax OK:
  - `coordination/loops/templates/run-loop.py`

Semantic scans:

- no forbidden registry wording in Owner registry Markdown/YAML;
- required runtime/template files exist;
- `owner_thread_plan` and `owner_subagent_plan` present in prompt/protocol/validator;
- plan, delivery, state, and run-log templates include Owner and child-agent state;
- `gpt-5.5` present;
- no active future model-label drift found;
- no numeric future budget default knobs found;
- forbidden source/test/runtime/dependency path scan clean;
- `git diff --check` clean.

## Residual Risks

- This is governance-only. It defines the runtime contract and validator checks;
  it does not prove real Codex thread creation, real Owner refresh, or connector
  publication.
- Tooling and Compute/HPC are recorded as thread-level Owners when routed, but
  live runtime thread ids are intentionally not invented.
- Existing `loop.yaml` and `loop.resolved.json` remain unresolved example
  templates; concrete loops must provide the new Owner runtime fields before
  execution.
- This Q-W1 task did not commit, push, update PR #7, or run Wave 3 final
  reviewers.

## Rollback Instructions

Revert the governance-only files listed in this report. No source, dependency,
dataset, checkpoint, Slurm, PR #6, or M3 runtime files need rollback.

## Final Conclusion

PASS
