# RFC 000: AutoVLA Architecture

| Field | Value |
| --- | --- |
| Status | Accepted for M0 baseline |
| Date | 2026-06-18 |
| Scope | governance and architecture contract only |

## Summary

AutoVLA is the target platform built on the current StarVLA engineering base.
M0 establishes governance, documentation, and quality gates, but it does not
implement model, data, runner, serving, deployment, or robot behavior.

## Goals

- Establish the AutoVLA identity for future native platform work.
- Define the seven-layer architecture vocabulary used by follow-up RFCs.
- Create an independent quality gate through `make autovla-check`.

## Non-Goals

- No model implementation is introduced in M0.
- No dataset execution, conversion, indexing, or training data movement is performed.
- No Slurm jobs, compute-node debug sessions, or cluster configuration changes are run.
- No StarVLA baseline paths are modified.

## Relationship To StarVLA

StarVLA remains the current engineering base and legacy baseline. New AutoVLA
code enters `autovla/` only when an approved milestone introduces that scope.
The `starVLA/` tree stays untouched during M0, and legacy backlog work remains
separate from the AutoVLA gate.

## Seven-Layer Architecture

The AutoVLA seven-layer architecture is the governance frame for future work:

- Core: shared interfaces, errors, registry contracts, and lifecycle primitives.
- Config: typed configuration schemas, validation, defaults, and migration rules.
- Data: dataset manifests, transforms, sampling contracts, and cache policies.
- Model: backbone, tokenizer, policy head, and checkpoint-loading contracts.
- Runner: training, evaluation, inference, and local execution orchestration.
- Deployment: serving adapters, endpoint contracts, packaging, and release checks.
- Acceleration: distributed execution, memory policy, precision, and kernel choices.

## Initial Directory Policy

`autovla/core` and `autovla/config` are the initial strict targets for M0
typing and package boundaries. `docs/autovla/` owns AutoVLA RFCs and
standards. Future directories are added only through approved RFC or milestone
scope.

## Quality Gate

`make autovla-check` is the M0 quality gate. It is scoped to AutoVLA-owned
paths and policy tests, so it remains independent from old StarVLA backlog while
still providing a strict bar for new work.

## Future RFCs

M1 and later RFCs will define core contracts, typed config behavior, runtime
interfaces, and validation evidence before any implementation is treated as
supported platform behavior.
