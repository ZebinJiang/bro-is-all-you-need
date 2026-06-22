# Codex Manager Governance

## Purpose

This file is the active governance authority for the Codex-only GenesisVLA Manager and persistent Owner-thread workflow.

It replaces live dependence on the former Claude supervisor file for current execution. The former supervisor file may remain as a historical archive, but the Codex Manager startup path must not require reading it.

## Authority order

For active Codex-only work, read and apply:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/MANAGER_ENTRYPOINT.md`
5. `docs/coordination/TEAM_OPERATING_MODEL.md`
6. `docs/coordination/testing/M1T_COORDINATION_VALIDATION.md`
7. `coordination/PROGRAM_STATE.yaml`
8. `coordination/TASK_INDEX.yaml`
9. active task card under `coordination/tasks/`
10. relevant Owner charter under `docs/coordination/owners/`

This file does not weaken repository safety, dataset immutability, Slurm policy, external-path policy, cleanup policy, secret policy, branch policy, or publication gates.

## Codex-only supervision model

```text
User
  -> 00-MANAGER · GenesisVLA Program
  -> persistent Owner thread
  -> task-specific direct Owner subagents
  -> Owner report
  -> Manager review
  -> user-facing report
```

The Manager owns live coordination. The user can override scope and gate decisions. Owner threads own domain review and execution routing.

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

## Legacy supervisor archive

Legacy files under `.agent-docs/teamwork/` and the former root supervisor file are historical references. They may explain previous decisions, but they are not the active source of truth for Codex-only execution unless the user explicitly restores Claude-supervised mode.
