# Training Runner Efficiency Harness

This tranche adds a CPU-only AutoVLA training-runner dry-run harness on top of
the merged training spine and model-family contracts.

## Scope

- Runs only with the in-memory `tiny` fixture.
- Uses the `gr00t-n1d6` dry-run batch adapter through the model-family
  registry.
- Calls a deterministic CPU policy test double.
- Computes masked action MSE with strict bool action masks.
- Emits small deterministic JSON artifacts under the caller-provided
  `output_dir`.
- Performs metadata-only checkpoint/resume compatibility validation.

## Outputs

The CLI command

```bash
python -m autovla.training.cli dry-run --family gr00t-n1d6 --fixture tiny --steps 2 --output-dir <path>
```

writes:

- `run_manifest.json`
- `runner_state.json`
- `efficiency_telemetry.json`
- `step_metrics.json`
- `checkpoint_manifest.json`
- `resume_validation.json`

## Runtime Boundary

The harness does not run real training, import GR00T runtime, load models,
checkpoints, tokenizers, or processors, read real datasets, use GPU/CUDA,
submit Slurm jobs, contact W&B/Hugging Face, or call endpoints/robots.

## Reuse Decision

Reference projects were considered for design vocabulary only. No upstream code
was copied or adapted in this tranche, so no new dependency, SPDX header,
third-party notice, or reuse manifest update is required.
