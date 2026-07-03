# UV Environment Strategy

AutoVLA rejects a single universal all-model-zoo environment. Model families
have different CUDA, tokenizer, framework, and asset expectations; forcing them
into one environment makes dependency conflicts and hidden downloads more
likely.

## Strategy

- Use one uv project per environment profile under `envs/<profile>/`.
- Keep `autovla-core` small and governance-safe.
- Keep data-format profiles separate from model-special profiles.
- Treat model-special profiles as manual-sync only unless a task explicitly
  authorizes dependency installation.
- Fine-tune configs must select an environment profile before any run can be
  considered.

## Root Branch Mode

When root is clean and synced to `origin/main`, root branch mode is the default.
New worktrees are reserved for explicit branch isolation or unsafe root state.
The uv matrix is designed to work in root branch mode without depending on
worktree-local `runs/tmp/m1-tool-venv` state.

## Non-goals

- No model-special dependency sync in this task.
- No checkpoint, tokenizer, Hugging Face, W&B, Slurm, GPU, endpoint, or robot
  action.
- No universal all-model-zoo environment.

## Next Goal

After this matrix is published, the next bounded task is
`AUTOVLA-M3-GR00T-N1D6-WEBDATASET-TELEMETRY-DRYRUN-ENV-GATE-001`. That task is
an environment-readiness gate for the WebDataset telemetry route; it is not a
fine-tune launch, backend finalization, model load, or checkpoint/tokenizer
operation.
