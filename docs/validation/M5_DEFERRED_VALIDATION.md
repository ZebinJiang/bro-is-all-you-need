# M5 Deferred Validation Plan

## Current Gate

Only static source validation is authorized for Integration-W1. Source
implementation is complete or explicitly specification-only; all runtime
claims remain deferred.

## Future Authorized Validation

1. Verify package/config inspection imports remain lightweight in fresh
   interpreters and selected extras fail with one actionable error.
2. Validate named preset composition and overrides, then construct the selected
   DataModule and local GR00T components from explicit governed assets.
3. Compare processor shapes, strict masks, normalization, relative actions,
   masked loss, and four-step sampling against pinned source semantics.
4. Run uninterrupted-versus-resumed checkpoint equivalence, malformed payload,
   cadence, callback failure, and rank-local RNG/Data restore checks. Exercise
   callback-requested stops separately at an empty accumulation window and a
   partial accumulation window; the partial-window case intentionally emits no final
   resumable checkpoint because checkpoint v2 does not persist accumulated
   gradients.
5. Validate optimizer parameter coverage, scheduler advancement, accumulation,
   nonfinite handling, and single-device behavior.
6. Run separately authorized DDP and FSDP2 jobs through project Slurm wrappers;
   record job IDs, logs, outputs, collective liveness, and state-dict parity.
7. Compare WebDataset, RoboDM-container, and local LeRobot only under a governed
   benchmark contract. Preserve `NO_BACKEND_WINNER` until accepted evidence
   explicitly changes that decision.

These steps require new authorization and suitable local assets/environments.
They must not infer model quality, production readiness, deployment readiness,
or robot safety from source completeness.

Exact deterministic cursor validation currently replays the consumed selection
prefix. For consumed samples `S` and configured datasets `D`, the conservative
restore bound is `O(S * D)` time and `O(D)` memory. Runtime profiling and a
bounded optimization or compact-proof decision are required before large-scale
resume or performance-readiness claims.

This milestone remains a stacked open draft: do not mark it ready or merge it.
No runtime validation above has been run, no runtime-readiness claim is made,
and the data-backend decision remains `NO_BACKEND_WINNER`.
