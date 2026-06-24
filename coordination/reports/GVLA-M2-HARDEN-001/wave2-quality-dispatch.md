# GVLA-M2-HARDEN-001 Wave 2 Quality Dispatch

## Dispatch

- Owner: `60-OWNER - Quality`
- Thread id: `019eeea5-b5e8-71a1-b0a0-fe7ae4a9e147`
- Child task: `GVLA-M2-REMOTE-CI-003`
- Dispatch time: 2026-06-24 Asia/Shanghai session
- Reasoning setting requested: `xhigh`
- Speed/latency setting: not exposed in `send_message_to_thread` schema and not requested.
- Writer mode: single writer.
- Parallel write: none.

## Inputs

- `coordination/reports/GVLA-M2-HARDEN-001/wave1-manager-synthesis.md`
- `runs/tmp/GVLA-M2-HARDEN-001/quality/remote-ci-plan.md`
- `runs/tmp/GVLA-M2-HARDEN-001/findings.yaml`
- `coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml`

## Allowed Write Scope

- `.github/workflows/genesisvla.yml`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `Makefile`
- `requirements/quality/**`
- `tests/meta/**`
- `docs/genesisvla/m2_transform_data_contract.md` only if needed for Quality/public gate wording
- `coordination/reports/GVLA-M2-REMOTE-CI-003/**`
- `runs/tmp/GVLA-M2-HARDEN-001/**` evidence only

## Prohibited

- DevSpace MCP or any `vla-flywheel-devspace` connector as execution evidence.
- New worktree or new Python environment.
- Stage, commit, push, PR edit/create, merge, force push, stash, reset, restore, clean, or rm.
- Source contract/data/model/training changes.
- M2 completion, M3 start, or `.agent-docs/feature_list.json` pass-field updates.

## Expected Report

`coordination/reports/GVLA-M2-REMOTE-CI-003/owner-quality.md`

## Current Conclusion

`BLOCKED_TEST`

Waiting for Q-W1 implementation, validation, and report.
