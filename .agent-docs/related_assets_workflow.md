# Related-Assets Research Workflow

## Purpose

`related-assets/` contains user-provided ideas, papers, notes, patches, or open-source references. When implementation is based on these materials, the Manager must use the superpowers planning skill before writing code.

Reference material may inspire GenesisVLA design, but external source code, datasets, weights, checkpoints, and private assets must not be imported unless the user explicitly authorizes a separate task.

## Required process

1. Inventory assets under `related-assets/` and register used assets in `.agent-docs/asset_manifest.md`.
2. Use the superpowers planning skill to analyze the idea before implementation.
3. Produce a planning record covering:
   - problem statement;
   - relevant paper/source-code claims;
   - assumptions and unknowns;
   - baseline/model family touchpoints;
   - VLM/LLM/vision backbone implications;
   - tokenizer and action-head implications;
   - dataset format and conversion implications;
   - training engine and evaluation benchmark touchpoints;
   - inference/serving path;
   - robot embodiment assumptions;
   - actual-layout integration point;
   - implementation hypothesis;
   - minimal implementation path;
   - validation metrics;
   - validation comparison plan;
   - Slurm run requirements;
   - risks and rollback path.
4. Update `.agent-docs/feature_list.json` only after the implementation scope is clear.
5. Assign a coding subagent only after the plan is frozen.
6. Validate with lightweight local/static checks, compute-node debug/test, and formal Slurm jobs when cluster behavior matters.
7. Record actual evidence and residual risk in `.agent-docs/progress.txt`.

## Superpowers output template

```md
# Research Planning Record

## Assets reviewed

## Core idea

## Claims to test

## VLA touchpoints

## Actual-layout integration point

## Implementation plan

## Validation plan

## Config and training implications

## Slurm plan

## Risks and rollback
```

## Parallel analysis

Multiple read-only agents may analyze different papers or code references in parallel. They may not modify source code. The Manager consolidates the result into a single implementation plan.
