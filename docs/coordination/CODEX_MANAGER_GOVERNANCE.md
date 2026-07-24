# Codex Manager Governance

## Active M12 Override

For
`AUTOVLA-M12-ARCHITECTURE-FIRST-RUNTIME-SUBSTRATE-OFFICIAL-FAMILY-ACTIVATION-001`,
the President Manager is the sole control, integration, acceptance, compute
budget, and publication authority. Its route is immutable
`gpt-5.6-sol / ultra`. Persistent Owner threads and automatic Owner fan-out are
disabled. Every child is a fresh prompt-scoped one-shot task agent using
`gpt-5.6-sol / high` for execution and return with parent inheritance
disabled. Writers require isolated branches/worktrees and disjoint ownership;
only the President writes the integration branch or mutates PRs. Completed
children close immediately, wave barriers require prior children closed, and
publication requires zero active children. Exactly one fresh four-agent final
review swarm is allowed; all reviewers close before fresh scoped repair waves,
and no second review swarm is permitted. The canonical machine-readable rules
are `coordination/MODEL_ROUTING_POLICY.yaml`,
`coordination/AGENT_LIFECYCLE_POLICY.yaml`,
`coordination/PARALLEL_EXECUTION_POLICY.yaml`, and
`coordination/VALIDATION_POLICY.yaml`. Older Owner-thread sections below are
historical compatibility material and do not authorize M12 routing.

## Purpose

This file is the active governance authority for the Codex-only AutoVLA Manager workflow.

It replaces live dependence on the former Claude supervisor file for current execution. The former supervisor file may remain as a historical archive, but the Codex Manager startup path must not require reading it.

## Authority order

For active Codex-only work, read and apply:

Read `coordination/MODEL_ROUTING_POLICY.yaml` and
`coordination/VALIDATION_POLICY.yaml` immediately after `AGENTS.md` for the
canonical routing, milestone mode, and validation-tier values.

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/LOOP_ACTIVATION_GATE.md`
5. `docs/coordination/OWNER_RUNTIME_SMOKE.md`
6. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
7. `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`
8. `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`
9. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
10. `docs/coordination/MANAGER_ENTRYPOINT.md`
11. `docs/coordination/TEAM_OPERATING_MODEL.md`
12. `docs/coordination/testing/M1T_COORDINATION_VALIDATION.md`
13. `coordination/PROGRAM_STATE.yaml`
14. `coordination/TASK_INDEX.yaml`
15. active task card under `coordination/tasks/`
16. relevant Owner charter under `docs/coordination/owners/`

This file does not weaken repository safety, dataset immutability, Slurm policy, external-path policy, cleanup policy, secret policy, branch policy, or publication gates.

## Codex-only supervision model

```text
User
  -> 00-MANAGER · AutoVLA Program
  -> fresh prompt-scoped child
  -> one structured handoff
  -> child retirement
  -> Manager review
  -> user-facing report
```

The Manager owns live coordination. The user can override scope and gate decisions. Owner threads own domain review and execution routing.

The canonical active routing values are defined only in
`coordination/MODEL_ROUTING_POLICY.yaml`. Markdown governance documents defer to
that machine-readable policy rather than maintaining independent defaults.

## Codex thread runtime settings

The current President Manager uses `gpt-5.6-sol / ultra`. Every non-President
Owner, worker, validator, compute executor, repair writer, publisher, and final
reviewer executes with `gpt-5.6-sol / high`. Every non-President
Manager-facing blocker or final return also uses `gpt-5.6-sol / high`.
Dispatch and return records name both profiles explicitly; absent fields are
recorded as requested/not exposed. Reasoning levels are never silently aliased.
Return switching and Return Synthesizer fallback are inactive for this routing.

The default mode is `architectural_construction_first`: bootstrap governance,
inspect bounded sources, construct one coherent architecture, run bounded
validation, freeze once, perform exactly one final Owner fan-out, run one
consolidated repair, run mapped post-repair checks, publish a Draft, and stop.
There is no Owner re-review after repair and no repeated audit of unchanged CI,
runtime, asset, or parity limitations.

For an architecture Draft, remote CI, CPU model runtime, FSDP/FSDP2, broad
suites, coverage, repeated parity, performance benchmarking, backend-winner
selection, and a second independent review are advisory unless the top-level
goal explicitly promotes one to primary scope. Safety, branch identity,
secrets, protected paths, asset staging, dataset immutability, license truth,
and remote-code boundaries remain hard gates.

## Prompt-controlled loops

Prompt-controlled loops are governed by `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`.

Prompt-controlled loop v2 has three lifecycle states:

- `GOVERNANCE_DRAFT`;
- `GOVERNANCE_INSTALLED`;
- `GOVERNANCE_ACTIVATED`.

PR #7 merge alone is not activation. Normal loop mode stays blocked as
`LOOP_NOT_ACTIVATED` until
`GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` passes and the Manager records accepted
runtime smoke evidence. PR #6 exact-head review waits for that activation.

The Manager proceeds from the top-level prompt and resolved loop spec. The Manager does not conduct a default interview. User questions are reserved for missing or ambiguous required fields, authorization, budget policy, timeout policy, validation evidence paths, connector actions, compute actions, deletion, credentials, endpoint use, publication, or conflicting governance.

Missing required loop fields, missing budget or timeout policy, ambiguous authorization, or missing validation evidence paths are `BLOCKED_LOOP_SPEC`.

Budget and timeout values must be supplied by the top-level prompt or resolved loop spec. The Manager must not invent fallback values.

Owner Dispatch Memory lives in `coordination/OWNER_DISPATCH_MEMORY.yaml` and is separate from Tool Memory. Tool Memory is advisory only and must not replace validation, approval, PR mutation, or completion-state decisions.

A completed Owner turn with no visible output or missing report is classified as `OWNER_THREAD_COMPLETED_NO_OUTPUT`. If the channel cannot be trusted for dispatch, record `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`. That condition cannot satisfy required Owner approval.

During activation, completed-no-output blocks runtime smoke and therefore blocks
normal loop activation. Child-agent reports may be cited only through the parent
Owner report.

## Stage rules

| Stage | Active owner |
| --- | --- |
| DISCUSS | Manager with user input when needed |
| PLAN | Manager and Primary Owner |
| EXECUTE | Primary Owner through approved write worker when behavior changes |
| VERIFY | independent read-only reviewer, tester, or recorded validation evidence |
| REVIEW | Manager with required Owner approvals |

Plan output is never self-accepted for behavior-changing tasks. Verification and review are not fix stages. If defects are found, create or reopen a scoped task and send it back through PLAN or EXECUTE.

## Worker coverage rule

Starting with M1, every task that changes source, scripts, configs, tests, quality gates, dataset or run behavior, Slurm behavior, model paths, training paths, deployment paths, or user-facing governance must carry a worker coverage ledger.

The ledger must record:

- whether exploration was used or skipped;
- which write-capable worker owns implementation changes;
- which independent reviewer or tester verifies the result;
- what evidence supports final review;
- skipped categories and compensating evidence.

## Manager limits

The Manager may directly write governance documents, task cards, program state, reports, and meta-test wiring when the user explicitly asks for control-plane changes.

The Manager must not directly implement behavior-changing source, scripts, configs, tests, dataset execution, model execution, training, deployment, Slurm wrappers, robot endpoints, or runtime paths when the task requires Owner routing. Those changes require the relevant Owner and one approved write-capable worker.

## Publication gate

Completed milestones still require the repository git workflow: required scans, local commit on a dev branch, push, PR creation or update, PR URL recording, and user-visible PR URL. If blocked, record `ready_to_publish_blocked` rather than marking the milestone complete.

Draft PR publication or `REQUEST_CHANGES` follow-up publication requires scan success, exact-head verification, and PR visibility verification. Scan blockers stop publication. Draft state is preserved unless the top-level prompt explicitly authorizes a ready-for-review transition.

## Legacy supervisor archive

Legacy files under `.agent-docs/teamwork/` and the former root supervisor file are historical references. They may explain previous decisions, but they are not the active source of truth for Codex-only execution unless the user explicitly restores Claude-supervised mode.
