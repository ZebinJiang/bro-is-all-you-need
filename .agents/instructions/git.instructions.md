---
description: Load these instructions when working with git history, branches, commits, GitHub pull requests, or GitLab merge requests.
---

# Git and Pull Request Instructions

## Branch Workflow

- Every new task must be developed on a `dev/*` branch.
- Do not make task changes directly on `main` or `master`.
- If a previous PR was merged, sync the base branch and recreate or rebase the dev branch before new work.
- Do not append unrelated changes to an existing dev branch.
- The Manager may open a PR after a complete task.
- The Manager may merge only if the user explicitly asks the Manager to review and merge.

## Commit Conventions

Commit message format:

```text
<type>(<scope>): <Description>.
```

Allowed types:

```text
feat, fix, bugfix, docs, style, refactor, perf, test, chore, scm
```

Use this body structure:

```md
## Summary

## Why

## Impact

## Validation

## Slurm Evidence

## Risks / Notes
```

## PR Description

Base the PR title and description on the full branch diff. Include validation, Slurm evidence when relevant, complexity/performance notes, and rollback notes.
