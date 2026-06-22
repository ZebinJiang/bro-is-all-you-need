---
description: Load these baseline Codex instructions for any task in this repository.
---

# Project Instructions

## Defaults

- Reply in the same language as the user unless asked otherwise.
- Read the relevant code, call sites, configs, tests, and governance files before editing.
- Exclude vendored, generated, dataset, and external-code directories from default code search unless the task explicitly targets them.
- Keep comments and docstrings aligned with the implementation; new or modified code comments/docstrings must be Chinese.
- Prefer concise, minimally fragmented helper functions. Avoid wrapper stacks unless they materially improve correctness or reuse.
- If documentation conflicts with code, report the mismatch and follow `AGENTS.md` / `boundaries.txt` for safety-sensitive decisions.

## Scope and Safety

- Stay inside the project repository.
- Stay within files and behavior directly related to the task.
- Avoid unrelated refactors, renames, structural changes, and edits under generated directories.
- Treat `code-input/`, `related-assets/`, `datasets/readonly/`, and `assets/input/` as read-only user input unless explicitly authorized.
- Call out risk before proposing or making breaking, destructive, expensive, cluster-dependent, privacy-sensitive, or security-sensitive changes.
- Do not assume external services, network access, GPU access, or Slurm availability until confirmed.

## Reporting

- List changed files when code or docs are modified.
- Separate implementation changes, validation results, Slurm evidence, complexity/performance notes, risks, and rollback notes.
- Recommend the minimum useful validation commands, then formal Slurm submission when cluster behavior is part of acceptance.
