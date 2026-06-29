# autovla.models Module Guide

## Purpose

`autovla.models` owns AutoVLA-native model registry metadata and adapter skeletons.
It records model-family contracts without importing real model runtimes, tokenizer
packages, checkpoint readers, GPU code, Slurm helpers, or training entrypoints.

## Public contracts

- `ModelZooEntry` describes one model registry key and its policies.
- `ModelAssetMetadata` describes governed source/checkpoint availability.
- `get_model_zoo_entry` and `list_model_zoo_keys` expose deterministic lookup.
- `Gr00tN1D6AdapterSkeleton` is fail-closed until source/checkpoint assets are
  explicitly governed by a later task.

## Directory structure

- `contracts.py`: model-zoo metadata dataclasses and fail-closed errors.
- `registry.py`: eager metadata registry for model family entries.
- `gr00t_n1d6/`: GR00T N1.6/N1.6.1 skeleton boundary.

## Naming conventions

- Registry keys are lowercase kebab-case, for example `gr00t-n1d6`.
- Candidate series names may include roadmap suffixes such as `pi0-roadmap`.
- Skeleton modules should use source-family names but must not create legacy
  compatibility import aliases.

## Extension points

- Add new model-family metadata entries through `registry.py`.
- Add a new adapter skeleton package when a family needs a distinct boundary.
- Add real runtime adapters only after source/license/checkpoint/tokenizer/action
  head evidence is available and reviewed.

## Modify vs extend rule

Extend the model zoo with new metadata entries or skeleton packages. Modify
shared contracts only when every model-family entry needs the new field and tests
prove existing entries remain deterministic and fail closed.

## Invariants

- No model/tokenizer/checkpoint load in metadata lookup.
- No Hugging Face, W&B, endpoint, robot, GPU/CUDA, Slurm, or training execution.
- No `genesisvla` compatibility shim.
- Missing runtime assets must raise `ModelAssetsUnavailableError`.

## Performance requirements

- Registry lookup must be CPU-only, IO-free, deterministic, and cheap enough for
  tests/meta policy checks.
- Future heavy runtime checks belong in separately authorized Model/Training
  tasks, not in model-zoo import.

## Tests and gates

- Focused tests live under `tests/training/test_model_zoo_readiness.py`.
- Meta tests verify docs and no compatibility shim policy.
- Black/Ruff/Pyright checks must not require model runtime dependencies.

## Agent workflow

1. Verify worktree, branch, HEAD, and tracked `genesisvla/**` count.
2. Keep model-zoo edits in `autovla/models/**` and focused tests.
3. Do not import heavy runtime modules during review.
4. Record source/license/checkpoint uncertainty in reports instead of copying
   unsafe upstream code.

## Anti-patterns

- Calling `from_pretrained`, tokenizer constructors, cache probes, or checkpoint
  readers from registry lookup.
- Vendoring an external model repository into AutoVLA without license review.
- Claiming runtime support from a metadata-only skeleton.
