# autovla.models.gr00t_n1d6 Module Guide

## Purpose

`autovla.models.gr00t_n1d6` records the GR00T N1.6/N1.6.1 model-zoo skeleton
boundary. It is a metadata-only readiness surface for the registry key
`gr00t-n1d6`.

## Public contracts

- `GR00T_N1D6_ENTRY` is the registry metadata entry.
- `Gr00tN1D6AdapterSkeleton` exposes metadata and fail-closed FrameworkProtocol
  shaped methods.
- `build_gr00t_n1d6_adapter_skeleton` constructs the skeleton without runtime IO.

## Directory structure

- `adapter.py`: release reference, model-zoo entry, and skeleton adapter.
- `__init__.py`: stable exports for the model-zoo registry.
- `MODULE.md`: this boundary guide.

## Naming conventions

- Public registry key: `gr00t-n1d6`.
- Release tag metadata: `n1.6.1-release`.
- Adapter classes use the `Gr00tN1D6` prefix.

## Extension points

- Add source/license/checkpoint metadata fields only after review.
- Add real adapter methods in a later task when governed assets and tests exist.
- Add shape/mask/action-head compatibility helpers only after Model approval.

## Modify vs extend rule

Extend this skeleton with more explicit metadata before adding runtime behavior.
Do not replace fail-closed behavior with real execution until a later task
authorizes source, checkpoint, tokenizer, and model loading.

## Invariants

- No upstream source vendoring in this tranche.
- No model weight download, checkpoint probing, tokenizer load, model load,
  inference, training, GPU/CUDA, Slurm, W&B/HF, endpoint, or robot action.
- Missing assets must fail with `ModelAssetsUnavailableError`.

## Performance requirements

- Import and metadata lookup must stay constant-time and IO-free.
- Future runtime performance work must be isolated from this metadata module.

## Tests and gates

- `tests/training/test_model_zoo_readiness.py` verifies lookup, fail-closed
  errors, no heavy imports, and PI/GR00T roadmap metadata.
- Full runtime tests are intentionally absent until a later authorized goal.

## Agent workflow

1. Treat NVIDIA Isaac-GR00T as a reference chain, not vendored code.
2. Record uncertain license/source status instead of copying code.
3. Keep skeleton behavior metadata-only and fail-closed.
4. Route runtime work to a future Model-owned task.

## Anti-patterns

- Importing `torch`, `transformers`, `huggingface_hub`, or upstream GR00T runtime
  from module import.
- Downloading or discovering checkpoints implicitly.
- Treating roadmap candidate names as supported runtime models.
