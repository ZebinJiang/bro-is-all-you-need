# GVLA-M2-HARDEN-001 Wave 3 Quality Gate Dispatch

## Preconditions

- Q-W1 remote CI/toolchain local hardening: `PASS`.
- A-W1 contract hardening: `PASS`.
- A-W1 Data review: `APPROVE`.
- A-W1 Quality review: `APPROVE`.
- D-W1 Data implementation: `PASS`.
- D-W1 Architecture review: `APPROVE`.
- D-W1 Quality re-review after static cleanup: `APPROVE`.

## Dispatch Decision

Dispatch `60-OWNER · Quality` for Wave 3 local canonical full gate.

This dispatch is verification only. It does not authorize staging, commit, push, PR update, merge, force push, stash, reset, restore, clean, rm, M2 completion, or M3 start.

## Expected Report

- `coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave3-gate.md`

## Required Evidence

Quality should verify the canonical worktree and collect local gate evidence including:

- project-local bootstrap
- `make genesis-check`
- `make governance-check`
- `make genesis-build-check`
- focused pytest over `tests/core tests/config tests/dataloader tests/meta`
- strict Pyright
- `git diff --check`
- scope/protected-path scan
- static suppression scan
- bidi scan
- artifact/large-file/security-oriented local scans appropriate before later publication

## Current Parent State

- Parent remains `BLOCKED_TEST`.
- `request_changes` remains true.
- Wave 4 publication remains blocked until Wave 3 local gate passes.
