# M1-T · Codex Thread-Team Coordination Validation

## Purpose

`M1-T` is a blocking validation node added after M1 started. It verifies the Codex-only Manager and persistent Owner-thread workflow before the project relies on it for normal AutoVLA implementation.

This node is governance and coordination only. It must not change model, data, training, deployment, Slurm, dataset, checkpoint, robot, or runtime behavior.

## Scope

In scope:

- Manager startup recovery from `docs/coordination/MANAGER_ENTRYPOINT.md`.
- Program state recovery from `coordination/PROGRAM_STATE.yaml`.
- Task discovery from `coordination/TASK_INDEX.yaml`.
- Owner boundary recovery from `docs/coordination/owners/*.md`.
- Task-card validation using `coordination/templates/TASK_CARD.yaml`.
- Owner-report validation using `coordination/templates/OWNER_REPORT.md`.
- Single-writer and protected-path rules.
- Worker coverage ledger for M1 and later tasks.
- Subagent retirement ledger and context cleanup evidence.
- Owner parallel write proposal routing through Manager and the user-facing gate.
- Real thread startup smoke for disposable Codex thread creation, response, evidence capture, and archive or retire cleanup.
- Meta tests proving that the control-plane files exist and agree.

Out of scope:

- Changing AutoVLA source behavior.
- Changing StarVLA baseline behavior.
- Running training, inference, deployment, robot, dataset conversion, Slurm jobs, or external services.
- Publishing a milestone PR.

## Acceptance criteria

M1-T passes only when all criteria below are satisfied:

1. Seven persistent top-level thread prompts exist.
2. Six Owner charters exist and name their primary authority, write scope, review duties, and report duties.
3. `coordination/PROGRAM_STATE.yaml` declares `active_milestone: M1` and `blocking_gate: M1-T`.
4. `coordination/TASK_INDEX.yaml` lists `GVLA-M1T-001` as active.
5. `coordination/tasks/active/GVLA-M1T-001.yaml` has a Primary Owner, required reviewers, write scope, protected paths, acceptance criteria, and required commands.
6. The task card does not authorize model, data, training, deployment, Slurm, dataset, checkpoint, robot, or runtime behavior changes.
7. Generic Owner subagent configs exist for Explorer, Implementer, Reviewer, and Tester.
8. Repository meta tests validate the coordination control-plane files.
9. Active Codex-only startup files do not require root `CLAUDE.md`.
10. Owner reports must include subagent retirement ledger evidence before Manager acceptance.
11. Owners must submit a parallel write proposal instead of directly launching parallel write-capable workers; Manager approval and a user-facing gate are required before splitting disjoint write scopes into separate task cards or worker threads.
12. M1-T defines a real thread startup smoke using `create_thread` and `read_thread`: create one disposable Owner-style thread, send or include a no-write startup prompt, confirm a post-dispatch response, record evidence, then archive or retire the disposable thread. This smoke must not replace formal implementation validation.
13. `python -m pytest tests/meta/test_repo_policy.py -v` passes.

## Real thread startup smoke protocol

The real thread startup smoke is a lightweight control-plane check, not an implementation task.

1. Use the Codex app thread tools to `create_thread` for one disposable Owner-style thread in the project or a safe projectless target.
2. Prompt the disposable thread to read its Owner prompt or a no-write startup prompt and report back without editing files.
3. Use `read_thread` to confirm the thread produced a post-dispatch response.
4. Record thread id, prompt summary, response summary, command/tool evidence, and cleanup status in the Manager report.
5. After evidence is recorded, archive or retire the disposable thread.

This smoke proves only that the Codex thread plumbing can start and respond. It must not replace formal implementation validation, Owner approval, Reviewer evidence, Tester evidence, or task-specific acceptance commands.

## Evidence record

The Manager records M1-T evidence in:

```text
coordination/reports/GVLA-M1T-001/OWNER_REPORT.md
coordination/reports/GVLA-M1T-001/MANAGER_REPORT.md
```

The reports may be initialized as pending. They become acceptance evidence only after the commands above pass and the Manager updates the status.

## Exit rule

Until M1-T passes, further AutoVLA work may continue only as explicit user-directed exceptions. Normal thread-team implementation should wait for the M1-T gate to be marked passed in `coordination/PROGRAM_STATE.yaml`.
