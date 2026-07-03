# scripts/env

## Purpose

`scripts/env` contains lightweight environment governance tooling.

## Public Contracts

- Tools may list, inspect, validate, and render profile commands.
- Tools must not install dependencies by default.
- Sync requires explicit command flags and any additional task authorization.

## Extension Rules

- Keep scripts stdlib-only unless dependency changes are explicitly approved.
- Do not load models, checkpoints, datasets, Hugging Face assets, W&B, Slurm, or
  endpoints.
