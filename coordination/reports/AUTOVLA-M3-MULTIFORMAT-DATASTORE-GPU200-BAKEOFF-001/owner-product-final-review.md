# Product/Spec Final Review

Task: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
Role: `15-OWNER · Product/Spec`
Runtime override recorded: `model=gpt-5.5`, `thinking=high`
Conclusion: `REQUEST_CHANGES`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`: candidate worktree has tracked README/docs/task-state changes plus task-owned untracked implementation and report files; no staged diff was observed.

## Evidence Reviewed

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/manager-summary.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave11.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave12.md`
- `README.md`
- `docs/benchmarks/README.md`
- `docs/benchmarks/DATA_PIPELINE_BACKEND_BAKEOFF.md`
- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- `git diff -- README.md docs/benchmarks/README.md docs/benchmarks/DATA_PIPELINE_BACKEND_BAKEOFF.md docs/benchmarks/DATA_FORMAT_PIPELINE_SUITE.md`
- `git status --short --ignored -uall docs/benchmarks`
- `git check-ignore -v docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`

## Passing Product/Spec Checks

The README and benchmark-index wording is product/spec honest in substance. It describes Wave 11 as bounded 200-step telemetry evidence for `zjh_lerobot_v21_raw` and `zjh_lerobot_v3_local`, records `dataloader_num_workers=0`, and keeps WebDataset tar plus RoboDM-style container rows as load-benchmark context for this tranche.

The linked telemetry dashboard also uses appropriate decision-support language. It states that the evidence does not select a final backend, authorize long training, prove model quality, authorize model download, use Hugging Face network access, enable W&B online sync, expose an endpoint, or authorize robot behavior. Its candidate table clearly marks WebDataset and RoboDM-style rows as not run for Wave 11 telemetry.

The next-action language remains conservative enough for Product/Spec: current docs continue to frame this as bounded telemetry and decision-support evidence, not a permanent backend selection, model-quality result, deployment claim, or training-readiness claim.

## Blocking Finding

The tracked README/docs publication surface links to `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`, but that linked dashboard file is ignored and untracked in the current worktree.

Evidence:

- `git ls-files docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` did not list the file.
- `git status --short --ignored -uall docs/benchmarks` reports `!! docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`.
- `git check-ignore -v docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` reports `.gitignore:235:*/**/*.md`.
- `git diff -- docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` has no tracked diff for that file.

This makes the publication surface incomplete: PR-visible README/docs would point readers at a benchmark dashboard that is not included unless the publisher explicitly force-adds the exact dashboard path or removes/rewrites the links and summaries that rely on it.

## Required Repair

Before Product/Spec can approve final publication, the publisher must do one of the following:

- Force-add the exact linked dashboard file `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` so the README/docs links resolve in the PR candidate.
- Or remove/rewrite the tracked README/docs links and summaries so the PR-visible surface does not depend on an ignored dashboard.

Do not add generated run outputs, logs, checkpoints, datasets, or `runs/tmp/**` evidence to solve this. The repair should be limited to the publication surface.

## Boundary Confirmation

- Final backend winner overclaim: not present in reviewed wording.
- Long training readiness claim: not present in reviewed wording.
- Model-quality claim: not present in reviewed wording.
- Deployment, endpoint, robot, W&B/HF network, model-download authorization: not present in reviewed wording.
- PR mutation, stage, commit, push, merge: not performed by Product/Spec.
- Source/tests/config/Slurm/dependency/dataset/checkpoint/runtime edits: not performed by Product/Spec.
- DevSpace MCP: not used.

## Subagent Ledger

- Child subagents used: none.
- Retired: yes.

## Conclusion

`REQUEST_CHANGES`

Reason: the messaging content is Product/Spec-honest, but the tracked README/docs currently link to an ignored/untracked telemetry dashboard. This must be repaired before final Product/Spec approval for publication.
