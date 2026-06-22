---
description: Load these instructions when modifying Python source files, tests, packaging metadata, or implementation-related documentation.
---

# Python Change Instructions

## Core Expectations

- Keep changes compatible with the project's Python version and public APIs unless the task allows otherwise.
- Reuse existing patterns, helpers, constants, and types before adding new ones.
- Keep new logic focused and efficient; avoid abstraction added only for style.
- Do not silently swallow exceptions. If catching one, preserve enough context to debug it.
- Preserve the GR00T 1.7 baseline path unless direct edits are explicitly scoped.

## Typing

- Preserve or add type annotations when touching function signatures or return values.
- Prefer complete type hints for public APIs, key helpers, model/dataset/pipeline entrypoints, and newly added functions.

## Documentation and Comments

- New or modified code comments and docstrings must be Chinese.
- Public classes/functions should document purpose, inputs, outputs, key tensor/shape transformations when relevant, and assumptions.
- Add comments only where they clarify non-obvious control flow, tensor/data movement, performance constraints, or baseline/optimized path separation.

## Performance

- Avoid unnecessary CPU↔GPU transfers, copies, synchronization barriers, and repeated preprocessing.
- For neural-network changes, report shape assumptions, memory pressure, batch/sequence scaling, and distributed/parallel implications.

## Dependencies

- Avoid new dependencies unless clearly necessary and approved by the task scope.
