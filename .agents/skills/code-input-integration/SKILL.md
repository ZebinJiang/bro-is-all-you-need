---
name: code-input-integration
description: Integrate user-staged code from code-input/ into the actual StarVLA engineering base or approved GenesisVLA-native paths without mutating staged input or contaminating protected baseline paths.
---

## Required steps

1. Inventory `code-input/` and identify user-provided files relevant to the task.
2. Treat `code-input/` as read-only.
3. Inspect the actual StarVLA engineering-base layout and target baseline code path.
4. Map staged code to actual framework locations; do not assume a template-owned `src/` tree.
5. Decide reuse, subclassing, adapter, configuration overlay, or new module in a natural existing location.
6. Implement with one coding subagent only.
7. Validate with lightweight local/static checks, compute-node debug/test when relevant, and Slurm submission when cluster behavior matters.
8. Record changed files, evidence, complexity notes, risks, and rollback path.

## Output

- staged files reviewed;
- target integration map;
- chosen integration strategy;
- files changed;
- validation and Slurm evidence requirements;
- baseline contamination assessment;
- rollback notes.
