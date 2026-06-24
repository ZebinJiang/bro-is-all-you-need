---
name: feature-dev
description: Codex-guided feature development for GenesisVLA / StarVLA sandbox tasks requiring discovery, architecture, implementation, validation, and review.
---

Use this skill for non-trivial GenesisVLA / StarVLA feature work that spans code, config, dataset, Slurm, or baseline-flow changes.

For StarVLA model, backbone, action-head, dataset, benchmark, training-config, inference-bridge, or evaluation-adapter work, use `integrating-starvla-components` as the required domain skill before architecture or implementation.

## Core principles

- Understand the baseline path before editing.
- Keep GR00T 1.7 baseline behavior protected unless explicitly scoped.
- Prefer direct, efficient code over wrapper stacks.
- Use serial structural implementation: one task, one coding subagent, then Manager collection and retirement.
- Use Chinese comments/docstrings in new or modified code.
- Validate locally first, then use Slurm dry-run and formal submission when cluster behavior matters.

## Required workflow

### Phase 1 — Discovery

Understand the request, task intake mode, and scope boundaries. Classify the task as code-input integration, related-assets research implementation, daily operational task, explicit external transfer, cleanup, or direct task implementation.

### Phase 2 — Codebase exploration

Use code-explorer-style analysis to trace entry points, call chains, data flow, model/dataset paths, and baseline extension points. Exclude user-input directories unless they are the task target.

### Phase 3 — Planning and clarifying questions

Resolve underspecified behavior, baseline touchpoints, validation requirements, and Slurm requirements. For related-assets work and nontrivial daily operational tasks, invoke superpowers planning/clarification before implementation.

### Phase 4 — Architecture design

Design the minimal safe implementation. Prefer configuration overlays, adapters, subclassing, or new modules over direct baseline edits when possible. Include complexity, memory, and parallel-efficiency considerations.

### Phase 5 — Implementation

Assign exactly one appropriate coding subagent. The subagent must work only in assigned writable paths and return changed files, complexity notes, validation suggestions, Slurm requirements, risks, and rollback notes.

### Phase 6 — Quality review

Use read-only review agents as needed. Review for correctness, baseline contamination, performance, data movement, GPU/parallel efficiency, Slurm safety, dataset policy, and Chinese documentation requirements.

### Phase 7 — Validation and Slurm evidence

Run lightweight local/static validation. If debug/test/evaluation/training matters, use compute-node allocation. If cluster behavior matters, run wrapper dry-run and submit formal Slurm job(s). Record config discovery if needed, job id(s), logs, outputs, and Manager review.

### Phase 8 — Summary and state update

Manager records evidence, updates progress, and updates feature status only after validation. Subagent context is retired.
