# GVLA-M2-HARDEN-001 Wave 4 Publication Dispatch

## Preconditions

- Wave 2 implementation and reviews: approved.
- Wave 3 local canonical gate: `PASS`.
- Wave 3 report: `coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave3-gate.md`.

## Dispatch Decision

Dispatch `60-OWNER · Quality` as the sole Wave 4 publication writer.

Wave 4 may stage explicit pathspecs, run staged scans, commit, push the existing branch without force, update existing Draft PR #2, and inspect remote exact-SHA evidence. It must not create a new PR, merge, force push, mark M2 complete, start M3, or modify `.agent-docs/feature_list.json` pass fields.

## Explicit Staging Scope

Stage only these explicit pathspec groups:

- `.github/workflows/genesisvla.yml`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- `docs/genesisvla/m2_transform_data_contract.md`
- `genesisvla/dataloader`
- `genesisvla/testing/fixtures/tiny.py`
- `tests/dataloader`
- `coordination/PROGRAM_STATE.yaml`
- `coordination/TASK_INDEX.yaml`
- `coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
- `coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml`
- `coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
- `coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml`
- `coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
- `coordination/tasks/active/GVLA-M2-PR2-VERIFY-003.yaml`
- `coordination/reports/GVLA-M2-REMOTE-CI-003`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002`
- `coordination/reports/GVLA-M2-DATA-HARDEN-002`
- `coordination/reports/GVLA-M2-HARDEN-001`
- `coordination/reports/GVLA-M2-PR2-VERIFY-003`
- `coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/manager-summary.md`
- `coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`
- `coordination/reports/GVLA-M2-MILESTONE-AUDIT-001`

Do not stage `runs/tmp/**` evidence.

## Required Publication Checks

- `git diff --cached --check`
- staged name/status and stat review
- staged secret/artifact/large-file/large-diff scans from `.agent-docs/git_workflow.md`
- protected path scan
- no staged `runs/**`, `datasets/**`, `checkpoints/**`, `code-input/**`, model weights, or feature-list pass fields
- non-force commit and push
- existing Draft PR #2 update, not new PR creation
- exact remote branch SHA and PR head SHA inspection

## Current Parent State

- Parent remains `BLOCKED_TEST` until publication and remote evidence complete.
- `request_changes` remains true.
- M2 milestone remains not complete.
