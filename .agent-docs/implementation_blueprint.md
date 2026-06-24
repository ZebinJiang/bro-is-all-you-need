# Implementation Blueprint

## Baseline-protected architecture

All registered VLA baselines are protected. New work should follow the selected baseline or platform path when one exists, and attach through natural extension points.

Preferred order:

1. Reuse an existing component without modification.
2. Add a configuration overlay or registry entry.
3. Add an adapter or subclass when reuse is natural.
4. Add a new module in a reasonable GenesisVLA-native location when reuse would contaminate a protected StarVLA baseline.
5. Directly edit protected baseline code only when explicitly required, justified, validated, and paired with rollback notes.

## Actual repository layout

Do not assume all code lives under `src/`. The Manager must inspect actual package, model, dataset, transform, tokenizer, ops, script, and config locations before scoping and delegating edits.

Optional future source locations include `genesisvla/`, `models/`, `engines/`, `datasets/`, `transforms/`, `tokenizers/`, `ops/`, `configs/<family>/`, and `scripts/` entrypoints. Introduce them only through a scoped implementation plan and exactly one write-capable task-specific implementation subagent.

## Implementation ownership

Design/architecture implementation, code modification, optimization, debugging/fix implementation, structural/source/module/script/test/config-contract/model-path/performance/Slurm-wrapper/dataset execution, and inference execution changes must be implemented by exactly one write-capable task-specific subagent by default. The Manager does not wait for an explicit user request for subagents.

The Manager scopes and intakes the task, chooses the narrow writable path set, delegates to one implementation subagent, reviews the output, runs or records validation, captures evidence/risks/rollback notes, retires the subagent context, and decides completion state. Manager-only work is limited to read-only analysis, validation commands, progress/user communication, and documentation-only governance edits that do not alter code behavior.

## Code-input integration

Prepared code from `code-input/` should be mapped to target locations based on actual call flow, data flow, model touchpoints, and validation needs. Do not copy staged code blindly.

## Related-assets implementation

Paper/source-code-based ideas must go through superpowers planning and produce a frozen implementation plan before structural edits.

Planning must identify baseline/model family, VLM/LLM/vision backbone, tokenizer, action head, dataset format, training engine, evaluation benchmark, inference/serving path, and robot embodiment assumptions when relevant.

## Dataset and asset implementation

Original dataset sources stay under `datasets/readonly/`. Derived conversions, indexes, manifests, and caches go under `datasets/working/` or `datasets/cache/`. Runs store references, manifests, checksums, metrics, and small samples rather than full dataset copies.

## Daily operational tasks

Ordinary cleanup, dataset placement, git-history work, and storage-transfer requests must go through superpowers-style clarification before execution. Cleanup requires a proposal and user confirmation before deletion.

## Performance requirements

For every nontrivial implementation, the Manager must review:

- time complexity;
- space complexity;
- data movement;
- tensor shape changes;
- CPU/GPU transfer behavior;
- parallel/distributed efficiency;
- memory pressure;
- synchronization points;
- impact on every protected baseline path.

## Documentation requirements for code

New or modified code must use Chinese docstrings and comments. For public classes/functions, include:

- overall function;
- inputs;
- outputs;
- important tensor/shape transformations;
- assumptions and constraints.
