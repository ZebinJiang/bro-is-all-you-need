# Daily Task Workflow

## Purpose

Daily tasks are ordinary user requests that do not start from `code-input/` or `related-assets/`. Examples include cleanup, dataset placement, moving files, git-history work, branch hygiene, storage transfer, or execution-state checks.

## Required behavior

1. Use superpowers-style clarification to identify the real intent, target paths, expected end state, and risk.
2. Classify whether the task is read-only, structural, cleanup, external transfer, git/PR, dataset-related, or Slurm-related.
3. For structural/design/code/debug/optimization implementation or fixes, use exactly one write-capable task-specific subagent by default; the Manager scopes, delegates, reviews, validates, records, and does not directly implement those changes.
4. For cleanup, use `.agent-docs/cleanup_policy.md` and wait for explicit user confirmation before deletion.
5. For external paths, use `.agent-docs/external_path_transfer_policy.md` and treat the access as one-time.
6. For Slurm work, use compute-node allocation or formal submission as required by `.agent-docs/slurm_sandbox_policy.md`.
7. Record commands, affected paths, evidence, risk, and rollback/recovery notes.

## Superpowers clarification output

For a daily task, the planning output should include:

- interpreted user goal;
- affected paths;
- whether external path access is required;
- whether deletion is involved;
- whether a dev branch/PR is involved;
- whether Slurm compute resources are required;
- proposed steps;
- validation/evidence plan;
- risk and recovery plan.
