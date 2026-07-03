# configs/finetune

## Purpose

`configs/finetune` stores future fine-tune config schemas and examples.

## Public Contracts

- Fine-tune configs must include an `environment` block.
- The environment block must name a known uv profile.
- Model-special profiles require manual authorization and locked/offline policy.

## Extension Rules

- Examples are dry-run/governance examples unless a task authorizes training.
- Do not include private endpoints, secrets, checkpoint payloads, or dataset
  dumps.
