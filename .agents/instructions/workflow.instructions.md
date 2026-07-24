---
description: Load these instructions when validating changes or working with repository workflows, tests, Slurm jobs, documentation builds, or developer tooling.
---

# Workflow and Validation Instructions

## M12 Prompt-Scoped Child Rule

- Persistent Owner threads and automatic Owner fan-out are disabled.
- The President Manager is fixed at `gpt-5.6-sol / ultra`.
- Every child explicitly uses `gpt-5.6-sol / high` for execution and return;
  parent model/reasoning inheritance is false.
- Writers use isolated worktrees and disjoint paths. Only the President writes
  the integration branch or PR.
- Every child closes after one handoff; wave barriers and publication require
  prior children closed.
- The final review is exactly one fresh four-agent read-only swarm; fresh
  focused repair waves follow without a second swarm.

## Sources of Truth

- Use `AGENTS.md` and `boundaries.txt` first.
- Use `Makefile` when a relevant target exists in the StarVLA engineering base.
- Use `pyproject.toml` and pytest config for Python tooling behavior.
- Prefer source files over generated artifacts.
- If workflow files disagree, report the mismatch instead of guessing.

## Model Routing

- Read `coordination/MODEL_ROUTING_POLICY.yaml` as the canonical routing value.
- The President Manager uses `gpt-5.6-sol / ultra`.
- Every non-President Owner, worker, validator, compute executor, repair or
  publication agent, and follow-up executes with `gpt-5.6-sol / high`.
- Every non-President Manager-facing blocker or final return uses
  `gpt-5.6-sol / high`.
- Silent reasoning aliases are invalid.
- When model or reasoning fields are absent, record
  `gpt-5.6-sol / high requested/not exposed`.
- Return switching and Return Synthesizer fallback are inactive.

## Validation

- Choose the smallest validation that matches changed files and impact.
- Lightweight local smoke validates sandbox structure only.
- Add or update tests when behavior changes.
- Real debug/test/evaluation should run on compute nodes, not login nodes.
- Broaden validation for shared behavior, model-path changes, public APIs, packaging, config, dataset, or Slurm changes.
- Slurm-dependent work requires config discovery if `TO_FILL`, compute-node debug/preflight when relevant, wrapper dry-run, and formal Slurm job submission before acceptance.
- If validation is partial or blocked, state what ran, what did not, and the remaining risk.
