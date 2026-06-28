# Repository Layout Policy

## Purpose

AutoVLA work is governed by actual-layout inspection, not by a template-owned source tree. The Manager must inspect the current StarVLA repository layout before deciding where model, data, training, evaluation, inference, tokenizer, transform, ops, or config changes belong.

This policy does not create or claim a production VLA implementation. Future source directories are introduced only by scoped implementation plans with evidence.

## Added sandbox/governance directories

These directories are intentionally added by the governance harness:

```text
.agents/
.codex/
assets/input/
code-input/
related-assets/
configs/slurm/
configs/experiments/
.agent-docs/
datasets/readonly/
datasets/working/
datasets/cache/
runs/
scripts/slurm/
scripts/sandbox/
scripts/data/
scripts/maintenance/
```

## Optional future platform locations

If a later implementation introduces first-class AutoVLA source, natural locations may include:

```text
autovla/
models/
engines/
datasets/
transforms/
tokenizers/
ops/
configs/<family>/
scripts/train.py
scripts/eval.py
scripts/inference.py
scripts/serve.py
```

These paths are optional examples, not required structure. Do not create them merely because this policy lists them.

## Source-code placement rule

When integrating code, the Manager must inspect the current repository tree and place code in the natural existing locations. Do not create duplicate paths only because the sandbox harness has a preferred layout.

Examples:

- If the repository already has model modules under a package-specific directory, use that directory.
- If training, evaluation, inference, or serving entrypoints already exist, extend those entrypoints only when appropriate.
- If a new module would contaminate a protected baseline path, add a clearly named extension module in the closest reasonable package or config-controlled location.
- If no source implementation exists yet, plan the source layout before adding files.

## Baseline protection

All registered VLA baselines remain available and reproducible. Experimental paths should be enabled through explicit registry entries, config overlays, adapters, subclasses, or separate entrypoints unless the user explicitly authorizes a direct baseline edit with rollback notes.

A baseline family listed in governance text is not implemented until source, configs, assets, and validation evidence exist.
