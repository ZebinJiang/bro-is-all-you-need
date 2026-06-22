---
name: daily-task-planning
description: Superpowers-style planning for ordinary operational tasks such as cleanup, dataset placement, git history, storage transfer, and execution-state changes.
---

Use this skill when the user's request is not a code-input or related-assets task.

## Required output

- Interpreted user goal.
- Affected project paths.
- Whether external path access is required.
- Whether deletion is involved.
- Whether git branch/PR state is involved.
- Whether Slurm compute resources are required.
- Proposed steps.
- Validation/evidence plan.
- Risk and recovery plan.

## Hard limits

- Do not execute deletion directly.
- Do not touch external paths unless the user gave exact paths and scope.
- Do not modify source or shared contracts concurrently with another structural subagent.
- Do not set `passes: true`.
