# Owner Runtime Smoke

## M10 Status

This persistent-Owner smoke is historical and inactive for M10. M10 does not
launch, refresh, or route persistent Owners. Its runtime gate instead validates
prompt-scoped ephemeral children: explicit `gpt-5.6-sol / medium` execution
and return, parent inheritance disabled, exact scope and ownership, structured
handoff, immediate closure, and zero active children at every wave barrier.
The President Manager remains `gpt-5.6-sol / max`.

## Task

`GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001`

## Purpose

This smoke proves that prompt-controlled loop v2 can route through persistent
Owner threads and Owner-owned child agents before normal loop mode is activated.
It is intentionally governance-only and local-static.

Spec validation is not runtime dispatch proof. The smoke must collect real
Owner packet, Owner report, child retirement, state, run-log, checkpoint, and
Manager-review evidence.

All future runtime-smoke dispatch and return records must follow
`coordination/MODEL_ROUTING_POLICY.yaml`: every non-President execution thread
uses `gpt-5.6-sol / medium`; every non-President Manager-facing blocker or
final return also uses `gpt-5.6-sol / medium`, while only the President Manager
uses `gpt-5.6-sol / max`. Return switching and Return Synthesizer fallback are
inactive. The completed historical smoke is preserved and is not rerun.

## Route

Primary Owner:

- Quality

Required reviewer:

- Architecture

Consulted Owner:

- Tooling

Skipped Owners:

- Compute/HPC: skipped because the smoke authorizes no compute, GPU, Slurm,
  scheduler, dependency, or external execution action.
- Training: skipped because the smoke authorizes no real training and no M3
  source/runtime/dependency work.
- Data, Model, Deployment: skipped because the smoke touches only governance
  activation artifacts.

## Expected Child Agents

Quality Owner may use:

- Quality Planner
- Quality Reviewer

Architecture Owner may use:

- Architecture Reviewer

Tooling Owner may use:

- Tooling Reviewer

All child agents have depth one. Child reports are incomplete evidence until
the parent Owner report cites them, summarizes risks, and records retirement.

## Explicitly Forbidden

The smoke must not launch or authorize:

- ToolEnvRunner;
- ComputeRunner;
- dependency recovery, wheelhouse fill, venv mutation, or toolenv repair;
- connector mutation;
- PR body update, PR comment, ready transition, merge, branch update, push, or
  publication;
- PR #6 mutation;
- source, test, runtime, dependency, M3, dataset, checkpoint, training, GPU,
  compute, Slurm, scheduler, endpoint, or robot action.

## Required Artifacts

The smoke records these portable artifacts:

- loop spec: `coordination/loops/examples/owner-runtime-smoke.loop.yaml`
- resolved spec: `coordination/loops/examples/owner-runtime-smoke.resolved.json`
- Owner packets:
  `coordination/loops/examples/owner-runtime-smoke/owner-packets/`
- Owner reports:
  `coordination/loops/examples/owner-runtime-smoke/owner-reports/`
- child reports:
  `coordination/loops/examples/owner-runtime-smoke/child-reports/`
- state:
  `coordination/loops/examples/owner-runtime-smoke/state.json`
- run log:
  `coordination/loops/examples/owner-runtime-smoke/run-log.md`
- checkpoint:
  `coordination/loops/examples/owner-runtime-smoke/checkpoints/activation-smoke.json`
- validation ledger:
  `runs/tmp/GVLA-GOVERNANCE-PR7-ACTIVATION-GATE-HARDENING-001/quality/validation-ledger.md`
- Manager summary:
  `coordination/reports/GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001/manager-summary.md`

## Passing Status

The expected final smoke status is:

`LOOP_V2_OWNER_RUNTIME_SMOKE_PASS`

Any missing Owner packet, missing Owner report, completed Owner turn with no
output, child report that bypasses the Owner report, missing child retirement
ledger, missing validation ledger, or attempted forbidden action blocks
activation.
