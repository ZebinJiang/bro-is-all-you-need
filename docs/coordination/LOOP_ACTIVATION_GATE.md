# Loop Activation Gate

## Purpose

This document defines the activation lifecycle for prompt-controlled loop v2.
It separates having governance text in a branch or merged PR from being allowed
to use the loop as normal runtime.

## Lifecycle States

### GOVERNANCE_DRAFT

The governance artifacts are still being authored or reviewed. The Manager may
run local specification validation examples, but must not treat the loop as a
normal execution mode.

Allowed work:

- read and write scoped governance artifacts;
- run local YAML, JSON, Markdown, and Python syntax checks;
- run `coordination/loops/templates/run-loop.py` against positive and negative
  examples;
- record review reports and blockers.

Blocked work:

- normal loop dispatch;
- PR #6 loop-mode review;
- PR mutation, publication, ready transition, merge, branch mutation;
- source, test, runtime, dependency, dataset, checkpoint, compute, Slurm, or
  training changes.

### GOVERNANCE_INSTALLED

The governance artifacts may be present on an approved branch or after PR #7 is
merged. Installation is not activation.

PR #7 merge alone must not enable normal prompt-controlled loop mode. After
installation, normal loop mode remains blocked until
`GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` passes and the Manager records accepted
runtime smoke evidence.

### GOVERNANCE_ACTIVATED

The loop becomes active only after all activation requirements pass:

- `GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` completed;
- Quality Owner report exists and passes;
- Architecture Owner report exists and passes;
- if Tooling is routed or consulted for activation smoke, the Tooling Owner
  packet and Tooling Owner report exist and the Tooling Owner report records
  child-agent collection and retirement;
- if Tooling is not routed or consulted for activation smoke, Tooling is
  explicitly skipped with a reason;
- every expected child agent is depth one, reported, collected, and retired
  before its parent Owner report;
- Manager records the smoke pass in loop state, run log, checkpoint, and
  activation evidence;
- activation keeps compute, Slurm, dependency recovery, source writes, PR
  mutation, and PR #6 mutation out of scope.

Only after this state may normal loop mode be used for work such as the PR #6
exact-head review.

## Required Statuses

Activation-gated specs and state files use these status names:

- `BLOCKED_LOOP_SPEC`: missing, empty, contradictory, or unresolved loop spec
  fields.
- `LOOP_NOT_ACTIVATED`: normal loop mode was requested while lifecycle state is
  not activated or while runtime smoke evidence is absent.
- `BLOCKED_OWNER_DISPATCH`: Owner dispatch cannot safely proceed because a
  required Owner route, packet, report path, role refresh, or liveness proof is
  missing.
- `OWNER_THREAD_REQUIRED`: a routed persistent Owner thread does not exist or
  has not been refreshed/constructed with authorization.
- `OWNER_THREAD_COMPLETED_NO_OUTPUT`: an Owner turn ended without visible
  output or without the required report.

## PR #6 Gate

PR #6 waits for activation. A PR #6 exact-head loop spec may exist as a durable
example, but it is not operational acceptance evidence until lifecycle state is
`GOVERNANCE_ACTIVATED` and the runtime smoke pass is recorded.

The PR #6 review path is review-only unless a later top-level prompt explicitly
authorizes mutation. Review-only means no PR body update, no comment, no state
change, no ready transition, no merge, no branch update, and no remote mutation.

## Spec Validation Is Separate From Runtime Proof

`coordination/loops/templates/run-loop.py` validates resolved JSON fields and
fail-closed policy relationships. A passing result proves only that the spec is
well formed. It does not prove that Owner threads were refreshed, packets were
sent, child agents ran, reports were written, or runtime dispatch succeeded.

Runtime proof requires Owner packets, Owner reports, child retirement evidence,
validation ledger, run log, checkpoint, and Manager review.
