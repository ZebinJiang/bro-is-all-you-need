# Code-Input Integration Workflow

## Purpose

`code-input/` is the fixed staging directory for user-written code. The Manager integrates staged code into actual StarVLA or approved AutoVLA model, data, training, evaluation, inference, tokenizer, transform, ops, or config paths while preserving protected baselines and keeping changes auditable.

Do not assume staged code should be moved into a template-owned `src/` directory. Inspect the actual repository layout first.

## Input contract

User-staged code may include:

- source files;
- patches;
- module snippets;
- test snippets;
- target-path notes;
- implementation notes.

The Manager should ask the user to include a short manifest when possible:

```text
Task id:
Staged code path:
Intended target path:
Expected behavior:
Baseline/model family touched:
Dataset or asset assumptions:
Tests or examples included:
Known assumptions:
```

## Required process

1. Inventory staged files and record them in `.agent-docs/asset_manifest.md` if they are used.
2. Treat staged files as read-only input unless the user explicitly asks to edit them.
3. Inspect the actual StarVLA repository layout and relevant baseline/model/data/execution flow before editing.
4. Decide whether the staged code should be integrated by reuse, registry entry, subclassing, adapter, configuration overlay, or new module in a natural existing location.
5. Assign exactly one coding subagent for the integration task.
6. Require the subagent to report complexity, memory behavior, data movement, GPU/distributed implications, baseline contamination risk, and rollback notes.
7. Run lightweight local/static validation.
8. Run compute-node debug/test when behavior needs actual runtime resources.
9. If the change affects cluster behavior, perform Slurm dry-run and formal Slurm submission through the wrapper.
10. Record evidence and update feature/progress records.

## Do not

- Blindly copy staged code into target directories without reading execution flow.
- Modify `code-input/` unless explicitly requested, except for approved governance updates to this README guidance file.
- Merge staged code into a protected baseline path when an extension point would preserve baseline behavior.
- Create a duplicate `src/` source tree that competes with the actual repository layout.
- Add deep wrapper stacks just to avoid understanding the target code path.
- Claim a listed baseline family is implemented without registered source, assets, configs, and evidence.
