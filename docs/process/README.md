# AutoVLA Process Archive

This directory contains concise mainline records for governance, publication,
worktree, and environment decisions that would otherwise live only in local
task evidence under `runs/tmp/**`.

The archive records decisions, paths, hashes, and PR references. It does not
publish raw logs, generated datasets, checkpoints, media payloads, model
weights, or worktree-local virtual environments.

## Index

- [Project timeline](PROJECT_TIMELINE.md)
- [Worktree retirement ledger](WORKTREE_RETIREMENT_LEDGER.md)
- [Tool environment lessons](TOOL_ENVIRONMENT_LESSONS.md)
- [Open decisions](OPEN_DECISIONS.md)
- [Report index](REPORT_INDEX.md)

## Current Policy

- Root branch mode is the default when root is clean and synced to `origin/main`.
- New worktrees are not created by default; use them only when an explicit task
  requires branch isolation or root is not safe to use.
- PR #16 remains an open draft backend research artifact and must not be marked
  ready, merged, or mutated by process-archive work.
- Environment work is moving toward a uv profile matrix rather than a single
  all-model-zoo environment.
