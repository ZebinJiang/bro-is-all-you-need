# GVLA-M2-HARDEN-001 Wave 0 Manager Preflight

## Conclusion

`BLOCKED_TEST`

`request_changes: true`

Wave 0 is complete enough to dispatch Wave 1 read-only Owner planning. No
source, tests, workflow, bootstrap, git index, commit, push, PR update, merge,
new worktree, or new environment was changed by Manager.

## Workspace Verification

- canonical worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- local HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- remote branch head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- PR URL: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- PR state: `OPEN`
- PR draft: `true`
- PR base: `dev/starvla-engineering-base`
- PR base SHA: `5e42b775f97d438ae58752f986284da9c4adf98b`
- PR head: `dev/feat-m2-transform-data-contract-v2-restacked`
- PR head SHA: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`

## Local Worktree Status

Initial canonical `git status --short` before Wave 0 writes showed existing
coordination/report dirtiness from the previous Manager and Owner reports:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml
 M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml
?? coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/manager-summary.md
?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md
?? coordination/reports/GVLA-M2-MILESTONE-AUDIT-001/
```

`git diff --name-status` at Wave 0 start:

```text
M	coordination/PROGRAM_STATE.yaml
M	coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml
M	coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml
M	coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml
```

`git diff --check`: PASS.

`git worktree list --porcelain` confirmed the canonical worktree exists and no
new worktree was created by this task. Old/scratch worktrees remain present and
were not cleaned.

## PR And Remote CI Evidence

The first bare `gh pr view 2` query resolved to upstream `starVLA/starVLA` PR #2
and was rejected as evidence for this task. Manager re-ran the query with
`--repo ZebinJiang/bro-is-all-you-need`, which is the correct target repo.

Correct target PR facts:

- title: `[Draft][M2] Transform Pipeline and Data Contract integration`
- repo: `ZebinJiang/bro-is-all-you-need`
- URL: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- draft: `true`
- base/head as listed above.

Remote check failures:

- `genesis-check`: FAILURE
  - `https://github.com/ZebinJiang/bro-is-all-you-need/actions/runs/28040257136/job/83004402217`
  - completed `2026-06-23T16:20:03Z`
- `genesis-check`: FAILURE
  - `https://github.com/ZebinJiang/bro-is-all-you-need/actions/runs/28040214304/job/83004245547`
  - completed `2026-06-23T16:19:15Z`

Failure classification from Quality publication report: bootstrap exit 66 due
missing offline wheelhouse distributions on GitHub runner.

## Existing Local Tool Environment

- `runs/tmp/m1-tool-venv/bin/python --version`: Python 3.10.12
- `runs/tmp/m1-tool-venv/bin/pyright --version`: pyright 1.1.410
- No new venv was created.

## Required Reading

Manager read the active governance set, state/index/registry, previous Manager
summary, all Wave 5 audit reports, publication Quality report, M2 plan,
contract doc, ADR, roadmap entries, PR body/checks/head, local diff scope, and
local/remote gate evidence.

## Normalized Finding Index

Written to:

`runs/tmp/GVLA-M2-HARDEN-001/findings.yaml`

The index routes findings only to the four authorized child tasks:

- `GVLA-M2-REMOTE-CI-003`
- `GVLA-M2-CONTRACT-HARDEN-002`
- `GVLA-M2-DATA-HARDEN-002`
- `GVLA-M2-PR2-VERIFY-003`

No finding was intentionally omitted because it was absent from the current
prompt. Additional prompt-specific items captured in Wave 0 include the PR body
F2 numbering mismatch and a bidi-control scan. The bidi scan found no matches in
the checked project paths.

## Task Cards Created

- `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
- `coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml`
- `coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-PR2-VERIFY-003.yaml`

No restack, unblock, toolenv, or integration task was created.

## DevSpace MCP Compliance

- Manager used DevSpace MCP: no.
- Evidence depends on DevSpace MCP: no.
- Owner dispatch prompt explicitly prohibits DevSpace MCP.
- Result: PASS.

Historical note: older Owner startup-smoke turns include DevSpace MCP tool calls
from before the current hard prohibition was enforced. They are not used as
execution evidence for this task.

## Wave 1 Dispatch Plan

Dispatch five persistent Owner threads concurrently:

- Quality Owner Q-RO1: remote CI/bootstrap plan.
- Architecture Owner A-RO1: public contract hardening plan.
- Data Owner D-RO1/D-RO2/D-RO3: transform/action, batch/statistics, and
  fixture/legacy/performance planning.
- Training Owner T-RO1: M3 consumer-readiness consultation.
- Model Owner M-RO1: M4 action/mask/loss-readiness consultation.

Wave 1 is read-only. All report writes are under allowed task report paths or
`runs/tmp/GVLA-M2-HARDEN-001/**`. No source writes are authorized in Wave 1.
