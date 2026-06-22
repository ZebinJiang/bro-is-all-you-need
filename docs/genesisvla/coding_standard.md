# GenesisVLA Coding Standard

## Scope

This standard applies to `genesisvla/` and GenesisVLA-owned tests and documents.
It does not retroactively enforce legacy StarVLA code or convert existing
baseline paths into GenesisVLA implementation.

## Python Baseline

GenesisVLA code targets Python 3.10. The package includes `py.typed` so typed
consumers can rely on declared package boundaries once real modules are added.

## Formatting

Black is the formatter for GenesisVLA Python paths. GenesisVLA uses line length
100 through explicit quality-gate command arguments. Existing StarVLA global
line length remains 121.

## Linting

Ruff runs on GenesisVLA paths. Wildcard imports are not allowed, and library code
must not use `print` for runtime reporting. New code should keep dependencies
explicit and local to the layer that owns them.

## Typing

Pyright runs in strict mode on `genesisvla/` and `tests/meta`. Public APIs should
use concrete types across layer boundaries. Avoid `dict[str, Any]` across core
boundaries unless the RFC or implementation record explains why a structured
type is not yet appropriate.

## Documentation

New or modified Python code uses Chinese docstrings and comments per `AGENTS.md`.
Chinese docstrings for public functions and classes document purpose, inputs,
outputs, assumptions, and important tensor or shape transformations when
relevant.

## Runtime Safety

GenesisVLA code must not call implicit `.cuda()`, hide device transfers inside
transform code, mutate global environment variables, or assume a specific cluster
runtime. Device, precision, and distributed behavior must be explicit in the
owning layer.

## Branch Policy

Agent-created GenesisVLA work uses `dev/*` branches. PRs require the
`make genesis-check` result. Do not push or create PRs unless the user explicitly
asks. Keep StarVLA baseline edits out of GenesisVLA governance PRs unless they
are explicitly scoped and reviewed.

## Quality Gate

`make genesis-check` must pass before M0 acceptance. The gate enforces Black,
Ruff, Pyright, and meta policy tests only on GenesisVLA-owned scope.
