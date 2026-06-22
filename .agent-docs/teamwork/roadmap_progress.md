# GenesisVLA Roadmap Progress

## Current Operating Mode

Claude Code is the supervisor and planning owner.

Codex CLI is the bounded Manager dispatched through Teamwork to run one GSD stage at a time, preserve repository context, coordinate Claude-approved workers, and report back through handoff.

Project-specific Teamwork history and reports are local-only under `.agent-docs/teamwork/`.

Codex Manager session policy: one long-lived project Manager session by default; bootstrap with `codex exec`, then continue normal Claude/Codex dialogue with `codex exec resume`.

Codex Manager default profile: `model=gpt-5.5`, `model_reasoning_effort=xhigh`, explicitly passed in dispatch commands rather than silently inherited.

M1+ worker coverage policy: every implementation or user-facing governance milestone must carry a worker coverage ledger. `EXECUTE` implementation uses write-capable workers, `VERIFY` uses independent read-only workers or Claude external validation evidence, and `REVIEW` closes with independent review evidence. Defects found in `VERIFY` or `REVIEW` return to `PLAN`/`EXECUTE`; Codex Manager must not patch them inline.

Milestone publication policy: every completed GenesisVLA milestone must be committed on a `dev/*` branch, pushed, opened or updated as a PR, and reported with a PR URL before the milestone is marked complete. If publication is blocked, status is `ready_to_publish_blocked`, not complete.

GSD artifact policy: `.planning/` and similar GSD-native files are temporary or auxiliary outputs. `.agent-docs/teamwork/` remains the authoritative supervisor state.

## Active Blueprint

- Blueprint: `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
- Protocol: `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- Usage guide: `.agent-docs/teamwork/claude_supervisor_usage.md`
- Codex Manager session metadata: `.agent-docs/teamwork/codex-manager-session.json`
- Registered code-input references for M1+: `code-input/FluxVLA-main.zip`, `code-input/dexbotic-main.zip`

## Current Milestone

- Milestone id: **M1** (next, not started)
- Stage: not started
- Next actor: Claude
- Status: M0 ACCEPTED by Claude Supervisor independent verification. Awaiting M1 DISCUSS dispatch.

## Stage Log

| Milestone | Stage | Status | Report | Notes |
| --- | --- | --- | --- | --- |
| P0 | DISCUSS | **completed** | `.agent-docs/teamwork/reports/P0/DISCUSS.md` | Gate: start_plan. All 4 topics answered. |
| P0 | PLAN | **completed** | `.agent-docs/teamwork/reports/P0/PLAN.md` | Gate: approve_execute. 1× coding_integration_engineer worker approved. |
| P0 | EXECUTE | **completed** | `.agent-docs/teamwork/reports/P0/EXECUTE.md` | V1-V5 passed. Wrapper created: scripts/teamwork/dispatch_codex_manager.py. V3 PASS_WITH_CONCERN (session-use-pattern, not wrapper defect). |
| P0 | VERIFY | **completed** | `.agent-docs/teamwork/reports/P0/VERIFY.md` | V1/V2/V5 re-passed. P0 Evidence Checklist satisfied. Recommendation: accept_p0. |
| P0 | REVIEW | **accepted** | (this file) | Claude Supervisor: accept_p0. P0 COMPLETE. |
| M0 | DISCUSS | **completed** | `.agent-docs/teamwork/reports/M0/DISCUSS.md` | Scope and placement clarified for F0.1-F0.7. Gate: start_plan. |
| M0 | PLAN | **completed** | `.agent-docs/teamwork/reports/M0/PLAN.md` | Gate: approve_execute. 1× coding_integration_engineer worker approved. |
| M0 | EXECUTE | **completed** | `.agent-docs/teamwork/reports/M0/EXECUTE.md` | Artifacts created and TDD red-green captured. V3 recorded as tooling concern. |
| M0 | VERIFY | **completed** | `.agent-docs/teamwork/reports/M0/VERIFY.md` | `.gitignore` docs exception applied. V1/V2/V4/V5/V6 passed; V3 failed on Black timeout. Recommendation: request_fixes. |
| M0 | REVIEW | **accepted** | `.agent-docs/teamwork/reports/M0/REVIEW.md` | Claude Supervisor independent verification: `make genesis-check` exit 0 in non-sandboxed env. Codex sandbox Black multiprocessing limitation is environment-specific, not a code defect. **M0 COMPLETE.** |

## Decisions

- One GenesisVLA small milestone maps to one local Teamwork task.
- Each milestone task may contain `DISCUSS`, `PLAN`, `EXECUTE`, `VERIFY`, and `REVIEW` stages.
- `DISCUSS` is an interactive Claude/Codex Teamwork exchange, not a one-shot Codex report.
- `PLAN` must stop for Claude review before `EXECUTE`.
- Project-specific Teamwork files must live under `.agent-docs/teamwork/` and remain ignored by git.
- `$gsd-pause-work`, `$gsd-resume-work`, and `$gsd-thread` are auxiliary context tools only. They can inform `roadmap_progress.md` only after Claude review.
- Codex Manager dispatch must explicitly set `model=gpt-5.5` and `model_reasoning_effort=xhigh` unless Claude records a stage-specific override.
- Starting with `M1`, each milestone must record a worker coverage ledger across `PLAN`, `EXECUTE`, `VERIFY`, and `REVIEW`: implementation changes require a write-capable worker, verification requires an independent read-only worker or Claude external evidence, review requires independent evidence, and defects found in `VERIFY`/`REVIEW` must return to `PLAN`/`EXECUTE`.
- `code-input/FluxVLA-main.zip` and `code-input/dexbotic-main.zip` are registered reference-only code-input assets. M1 DISCUSS must inspect them read-only and decide which ideas influence GenesisVLA contracts/configs now vs. later. They must not be mutated or copied into implementation without Code-Input Integration Workflow, license/source attribution review, and Claude-approved worker plan.
- Every completed milestone must pass the publication gate: required git scans, local commit, push to remote, PR opened/updated, PR URL recorded and provided to Claude/user. A milestone with local REVIEW accepted but no PR URL is `ready_to_publish_blocked`, not complete.

### P0 Decisions (accepted by Claude)

- Wrapper is at `scripts/teamwork/dispatch_codex_manager.py` (716 lines, Python 3 stdlib only).
- `.agent-docs/teamwork/` is the authoritative supervisor state.
- `.planning/` artifacts are auxiliary only.
- `codex exec` for bootstrap; `codex exec resume <id>` for continuation.
- All dispatch uses `-s workspace-write`, `-m gpt-5.5`, `-c model_reasoning_effort=xhigh`.
- wrapper `.last.md` only; Claude manually promotes to canonical `.md` if needed.
- next-actor.json direct writes authorized for P0 only; M0+ must use wrapper-mediated updates.
- Future wrapper smoke must use dry-run or purpose-built non-mutating prompts (not live stage resumes).

### P0 Residual Risks (accepted)

1. Bootstrap event not in `messages.jsonl` (wrapper did not exist at bootstrap time) — acceptable; recorded.
2. `workspace/task-board.md` was stale — refreshed in this REVIEW.
3. Resumed-session prompt collision — documented, future policy set; not a wrapper defect.
4. `.agent-docs/` is git-ignored, so git status cannot show Teamwork changes — use stage reports as evidence.

## Active Codex Manager Session

- Session id: `019ed892-624f-7453-ad1a-3131b2000cce`
- Session file: `.agent-docs/teamwork/codex-manager-session.json`
- Wrapper: `scripts/teamwork/dispatch_codex_manager.py`

## Open Questions

- None blocking. M1 (Core Contract + Typed Config) is next per blueprint.

### M0 Residual Issues (accepted as non-blocking)

1. **Codex sandbox Black multiprocessing limitation**: Codex Manager's own validation sandbox cannot run `black --check ... directory` even with `--workers 1` (always hangs/timeout). Same command runs cleanly in normal bash. This is an environment issue specific to Codex's process sandbox, not a defect in the M0 deliverables. Documented for future milestones — Codex Manager should rely on Claude independent verification or worker-T5-style fresh-venv evidence for `make genesis-check` validation, rather than re-running it directly in its sandbox.

2. **Validation tool env in `/tmp/vla-flywheel-m0-tools`**: Not durable. Future M1+ should use a project venv setup or document install steps as part of CONTRIBUTING. M0 records this in `docs/genesisvla/testing_standard.md`.

3. **`docs/genesisvla/` files untracked**: After `.gitignore` patch they are visible but not staged. User decides if/when to commit M0.

## Next Proposed Action

Claude dispatches M1 DISCUSS — Core Contract + Typed Config (RawSample, FrameworkOutput, Protocols, dataclass config, OmegaConf bridge).

M1 PLAN must create the worker coverage ledger before execution. M1 EXECUTE cannot be Manager-only if it changes implementation, tests, configs, or quality gates.

M1 DISCUSS must use the registered FluxVLA and Dexbotic source archives as read-only references for runner/config/registry/transform design decisions.

Use `scripts/teamwork/dispatch_codex_manager.py --milestone M1 --stage DISCUSS`.
