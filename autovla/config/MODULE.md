# autovla.config

## Purpose

Configuration modules own schema, loading, validation, and export contracts for
AutoVLA. They should not import model-heavy dependencies or trigger runtime
side effects.

## Public Contracts

- Strict config schema validation.
- Explicit environment selector handoff for future fine-tune configs.
- No implicit model, checkpoint, tokenizer, dataset, or network loading.

## Extension Rules

- Add schema fields with tests and fail-closed validation.
- Keep model-special environment behavior in profile configs and scripts.
- Do not hide dependency installation inside config loading.
