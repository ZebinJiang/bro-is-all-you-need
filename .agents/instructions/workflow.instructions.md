---
description: Load these instructions when validating changes or working with repository workflows, tests, Slurm jobs, documentation builds, or developer tooling.
---

# Workflow and Validation Instructions

## Sources of Truth

- Use `AGENTS.md` and `boundaries.txt` first.
- Use `Makefile` when a relevant target exists in the StarVLA engineering base.
- Use `pyproject.toml` and pytest config for Python tooling behavior.
- Prefer source files over generated artifacts.
- If workflow files disagree, report the mismatch instead of guessing.

## Model Routing

- Read `coordination/MODEL_ROUTING_POLICY.yaml` as the canonical routing value.
- The President Manager uses `gpt-5.6-sol / max`.
- Every non-President Owner, worker, validator, compute executor, repair or
  publication agent, and follow-up executes with `gpt-5.6-sol / medium`.
- Every non-President Manager-facing blocker or final return uses
  `gpt-5.6-sol / max`.
- Silent reasoning aliases are invalid.
- When model or reasoning fields are absent, record
  `gpt-5.6-sol / medium requested/not exposed`.
- Prefer same-thread max return. If the runtime cannot switch the execution
  thread, exactly one read-only max Return Synthesizer may emit the structured
  return without implementation, reruns, expansion, or descendants.

## Validation

- Choose the smallest validation that matches changed files and impact.
- Lightweight local smoke validates sandbox structure only.
- Add or update tests when behavior changes.
- Real debug/test/evaluation should run on compute nodes, not login nodes.
- Broaden validation for shared behavior, model-path changes, public APIs, packaging, config, dataset, or Slurm changes.
- Slurm-dependent work requires config discovery if `TO_FILL`, compute-node debug/preflight when relevant, wrapper dry-run, and formal Slurm job submission before acceptance.
- If validation is partial or blocked, state what ran, what did not, and the remaining risk.
