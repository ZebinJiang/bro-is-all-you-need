# GVLA-M2-HARDEN-001 Wave 2 Data Dispatch

## Manager Gate

- Parent task: `GVLA-M2-HARDEN-001`
- Child task: `GVLA-M2-DATA-HARDEN-002`
- Canonical worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- Canonical branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- Published head before hardening: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`

## Preconditions

- Q-W1 remote CI/toolchain local hardening: `PASS`
  - Report: `coordination/reports/GVLA-M2-REMOTE-CI-003/owner-quality.md`
  - Architecture review: `APPROVE`
  - Review report: `coordination/reports/GVLA-M2-REMOTE-CI-003/owner-architecture-review.md`
- A-W1 contract hardening: `PASS`
  - Report: `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-architecture.md`
  - Data review: `APPROVE`
  - Data review report: `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-data-review.md`
  - Quality review: `APPROVE`
  - Quality review report: `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-quality-review.md`

## Dispatch Decision

Data D-W1 may proceed as the only Wave 2 writer. The dispatch is serial: no
Architecture, Quality, Training, Model, or Manager writer is active concurrently.

## Scope Guardrails

- D-W1 must use the A-W1 contract surface instead of redefining parallel public
  types.
- D-W1 must not reopen Architecture-owned core contracts unless it reports a
  blocker and Manager routes a new plan.
- D-W1 must not use DevSpace MCP, stage, commit, push, update PRs, merge, stash,
  reset, restore, clean, remove files, or touch completion/pass state.
- D-W1 must write its Owner report to
  `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data.md`.

## Parallelism

- Read-only planning/review ran in parallel.
- Data D-W1 is a single serial writer.
- No parallel write is approved.
