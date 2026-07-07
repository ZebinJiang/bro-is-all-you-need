# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Owner Architecture Plan

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`: branch matches `origin/main`; only task-local untracked planning files are present.
- `workspace_check`: PASS

## Evidence Reviewed

- Owner packet:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-packets/architecture-plan.md`
- Task card:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- Current code and benchmark surfaces:
  - `autovla/dataloader/perf/bakeoff.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/format_pipeline/pipeline.py`
  - `autovla/training/baseline_metrics.py`
  - `README.md`
  - `docs/benchmarks/DATA_PIPELINE_BACKEND_BAKEOFF.md`
  - `docs/benchmarks/README.md`
- Dependency and package-boundary truth:
  - `pyproject.toml`
  - `requirements/quality/quality-requirements.txt`
  - `requirements/quality/quality-constraints.txt`
- Current dataloader module layout via read-only directory inspection.

## Architecture Assessment

### 1. Abstraction Boundary

The new multiformat work should live under `autovla/dataloader/stores/**` as a store-oriented layer, not as a rewrite of `autovla/dataloader/perf/**` or `autovla/dataloader/format_pipeline/**`.

- `autovla/dataloader/perf/**` should remain the benchmark/reporting and comparison surface.
- `autovla/dataloader/format_pipeline/**` should remain the build/validate/benchmark conversion surface for the existing format-pipeline suite.
- `autovla/dataloader/stores/**` should introduce only the shared store abstractions needed for this bakeoff:
  - deterministic sample/window manifest contract;
  - bounded read/build interfaces for raw, WebDataset-native, Robo-DM-style, and dependency-blocked LeRobot v3 routes;
  - store metadata and result schemas that can be consumed by perf and telemetry code.

Architecture should not allow the new store path to absorb telemetry logic, model-family runtime logic, or broad benchmark publication logic. Training telemetry should stay under `autovla/training/telemetry/**`, with the store layer providing only read-only data access and manifest inputs.

### 2. Upstream Reuse Boundary

The safe reference-guided boundary is:

- WebDataset:
  - already approved and pinned on this branch as an existing performance dependency route;
  - acceptable as an implementation dependency behind AutoVLA-native store interfaces;
  - must not leak raw `webdataset` package semantics into README/docs as if it were the final training backend choice.
- Robo-DM:
  - must remain AutoVLA-owned native or prototype-style implementation unless a separate dependency/license route is explicitly approved;
  - docs must continue to say this is not a claim of upstream Robo-DM package support.
- LeRobot v3:
  - official package/runtime route is still dependency-gated;
  - for this planning gate it is acceptable to keep LeRobot v3 as a mandatory comparison row represented by a fail-closed dependency-blocked store candidate unless later user authorization explicitly opens the dependency route.

No-copy/no-vendor/no-wholesale-upstream-repo reuse remains the correct boundary for this task. The current repository pattern already favors reference-guided native implementations with explicit dependency truth, and this task should follow the same rule.

### 3. README / Docs Benchmark Surface Discipline

README and `docs/benchmarks/**` must keep decision-record discipline:

- The multiformat bakeoff is decision-support and telemetry preparation, not final backend selection.
- Numeric results may compare candidate stores, but must not overclaim training readiness, fine-tune readiness, model-runtime readiness, or deployment readiness.
- The benchmark surface should preserve current candidate semantics:
  - raw baseline remains baseline;
  - WebDataset-native remains a first-class AutoVLA candidate, not an irrevocable final backend winner;
  - Robo-DM-style remains AutoVLA-owned prototype/candidate work;
  - LeRobot v3 remains either runnable through an approved route or explicitly dependency-blocked.
- Raw logs, generated stores, media payloads, and telemetry artifacts must stay out of tracked docs and remain under governed ignored output paths.

## Required Planning Guardrails

- Do not mutate `requirements/**`, `pyproject.toml`, or `Makefile`.
- Do not mutate `datasets/readonly/**`.
- Do not add model/runtime/training/checkpoint/tokenizer/HF/W&B/endpoint/robot behavior.
- Do not let `autovla/dataloader/stores/**` become a second benchmark CLI stack that bypasses `autovla/dataloader/perf/**`.
- Keep the shared sample/window manifest contract deterministic and reusable by both the store bakeoff and the later GPU200 telemetry step.
- Keep README and docs phrased as decision-support evidence, not backend adjudication or training authorization.

## Candidate Dependency Decision Review

- `raw`: no user dependency decision required.
- `webdataset_native`: no new user dependency decision required for planning because WebDataset is already approved and pinned in the current repository dependency surface.
- `robodm_style`: no user dependency decision required if it remains AutoVLA-native and prototype-owned.
- `lerobot_v3`: do not force `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY` at this planning stage, provided the task plan preserves LeRobot v3 as a fail-closed comparison candidate that may remain `NOT_RUN_DEPENDENCY_BLOCKED` unless a later explicit dependency authorization is granted.

If the implementation plan later requires an actual official LeRobot v3 package route to satisfy acceptance, that later step must fail closed into `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY`. Based on the current task card and repository conventions, that escalation is not required to approve the planning boundary itself.

## Findings

No blocking architecture issue was found in the current planning boundary.

The only material caution is that the new `autovla/dataloader/stores/**` layer must stay narrow. If it starts duplicating format-pipeline conversion code, re-owning perf report semantics, or implying final backend choice from benchmark outputs, the task should be returned for changes.

## DevSpace MCP Compliance

DevSpace MCP was not used.

## Subagent Retirement Ledger

- Child subagents used: none
- Retirement status: retired yes

## Conclusion

APPROVE
