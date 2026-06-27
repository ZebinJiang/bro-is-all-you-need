# Prompt-Controlled Loop Harness

This directory contains governance-only templates for prompt-controlled loops.

The harness validates required fields and records local evidence. It does not train models, start GPU work, submit Slurm jobs, mutate PRs, change dependencies, delete branches, or clean worktrees unless a resolved loop spec explicitly authorizes that exact action and all gates pass.

Use `templates/loop.yaml` to draft a loop, `templates/loop.resolved.json` for a parseable resolved example, and `templates/run-loop.py` for local required-field checks against a resolved JSON spec.
