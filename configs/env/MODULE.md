# configs/env

## Purpose

`configs/env` stores uv environment profile metadata for AutoVLA.

## Public Contracts

- Every profile has a `profile_id`, `uv_project`, dependency tier, sync policy,
  risk, lock status, install status, and manual authorization flag.
- No profile may represent an all-model-zoo environment.
- Model-special profiles default to manual sync.

## Extension Rules

- Add a profile before a fine-tune config references it.
- Keep generated environments and downloaded dependencies out of git.
