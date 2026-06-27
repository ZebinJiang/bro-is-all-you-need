# Owner Quality Tooling Repair

Task: GVLA-GOVERNANCE-PR7-ACTIVATION-GATE-HARDENING-001
Worker: Q-W1R2
Conclusion: PASS

## Repair Summary

- Hardened `docs/coordination/LOOP_ACTIVATION_GATE.md` so consulted or routed Tooling must have a Tooling Owner packet/report and child retirement recorded through the Tooling Owner report. Tooling can be skipped only when not routed or consulted, with a reason.
- Hardened `coordination/loops/templates/run-loop.py` so `owner_routes.consulted` participates in routed Owner validation.
- Hardened PR exact-head validation so `connector_action_policy.exact_head_required=true` requires `pr_visibility_gate.expected_remote_head == expected_head` for PR or remote targets, including review-only specs with `authorized_actions=["none"]`.
- Hardened activation validation so `activated=true` requires `installed=true`, and normal loop allowance requires both installed and activated.
- Added negative fixtures for consulted Tooling without Owner metadata, PR #6 review-only stale head, and activated-without-installed.

## Validation Evidence

- Python syntax: `python3 -m py_compile coordination/loops/templates/run-loop.py` passed.
- Positive examples: `coordination/loops/examples/owner-runtime-smoke.resolved.json` and `coordination/loops/examples/pr6-exact-head-review.resolved.json` passed.
- Negative examples: all 22 files under `coordination/loops/examples/negative/*.resolved.json` failed nonzero with `BLOCKED_LOOP_SPEC` or `LOOP_NOT_ACTIVATED`.
- New Tooling fixture: `consulted-tooling-without-owner-thread.resolved.json` failed with `BLOCKED_LOOP_SPEC owner_thread_missing=tooling owner_subagent_plan_missing=tooling`.
- New PR #6 fixture: `pr6-review-head-mismatch.resolved.json` failed with `BLOCKED_LOOP_SPEC pr_expected_remote_head_mismatch`.
- New activation fixture: `activated-without-installed.resolved.json` failed with `LOOP_NOT_ACTIVATED activated_without_installed`.
- `git diff --check` passed.
- Changed-path guard passed: no source, test, runtime, dependency, Slurm, training, staging, commit, push, PR update, or PR #6 remote mutation was performed.
- Model label guard passed: active `gpt-5.5` is preserved by JSON `model_label` parsing and edited-surface grep; the forbidden 5.6 model label appears only in the existing negative model-drift fixture. A broader literal report-directory grep also finds a pre-existing non-active review note in `owner-quality-implementation.md`; this repair did not modify it or introduce active model drift.

## Risk And Rollback

- Risk: low; changes are governance validator/documentation/fixture-only and do not touch runtime source, tests, dependencies, Slurm, training, or PR state.
- Rollback: revert the scoped changes to `docs/coordination/LOOP_ACTIVATION_GATE.md`, `coordination/loops/templates/run-loop.py`, and the three new negative fixtures.
