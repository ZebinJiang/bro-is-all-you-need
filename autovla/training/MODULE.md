# autovla.training

## Purpose

Training modules own deterministic local runner contracts, dry-run manifests,
and future training orchestration boundaries.

## Public Contracts

- Dry-run code must not start real training.
- Local smoke paths use tiny fixtures and deterministic CPU-only behavior.
- Fine-tune entrypoints must select an environment profile before execution.

## Extension Rules

- Separate config validation from runtime execution.
- Keep Slurm, GPU, W&B, Hugging Face, and checkpoint behavior behind explicit
  task authorization.
- Preserve PR #16 as backend research until the user makes a decision.
