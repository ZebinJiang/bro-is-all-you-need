# Q-W1R Owner Quality Repair Report

Task: `GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001`
Worker: `Q-W1R`
Conclusion: `PASS`

## Scope

Fixed only the final review blockers assigned to Q-W1R:

- `run-loop.py` now fails closed unless both `plan_gate` and `delivery_gate` set `child_reports_cannot_bypass_owner_report` to literal `true`.
- Gate `required_owner_reports` must be a mapping to routed persistent Owner reports, must not point at child/subagent report paths, and must exactly match `owner_thread_plan.owner_report_paths`.
- Gate reviewers and required report owners must be routed persistent Owners.
- Compute policy now blocks contradictory compute/Slurm authorization, raw/non-wrapper Slurm action specs, missing persistent `Compute/HPC` Owner routing for execution actions, and authorized compute/Slurm/scheduler execution without a depth-1 `ComputeRunner` retiring before the Compute/HPC Owner report.
- `LOOP_BACKLOG.yaml` no longer describes Tooling or Compute/HPC as short-lived reviewer roles; it records refresh/construction of persistent Owner thread ids as required when routed.

## Changed Files

- `coordination/loops/templates/run-loop.py`
- `coordination/loops/templates/TOP_LEVEL_LOOP_PROMPT.md`
- `coordination/loops/templates/plan.md`
- `coordination/loops/templates/delivery-N.md`
- `coordination/LOOP_BACKLOG.yaml`
- `runs/tmp/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/quality/validator-specs/missing-gate-bypass-flags.json`
- `runs/tmp/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/quality/validator-specs/child-report-required-owner-report.json`
- `runs/tmp/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/quality/validator-specs/unauthorized-slurm-action.json`
- `runs/tmp/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/quality/validator-specs/authorized-slurm-without-computerunner.json`
- `coordination/reports/GVLA-GOVERNANCE-PR7-THREAD-OWNER-LOOP-RUNTIME-001/owner-quality-repair.md`

Pre-existing dirty/untracked governance files outside this list were observed at startup and left untouched.

## Validation Evidence

- `python3 - <<'PY' ... compile(run-loop.py) ... PY`
  - Result: `python syntax ok coordination/loops/templates/run-loop.py`
- `python3 - <<'PY' ... json.loads(...) ... PY`
  - Result: `json ok 11 specs`
- `python3 - <<'PY' ... yaml.safe_load(coordination/LOOP_BACKLOG.yaml) ... PY`
  - Result: `yaml ok coordination/LOOP_BACKLOG.yaml via python3`
- `python3 - <<'PY' ... validator matrix ... PY`
  - Result: valid spec returned `PASS`; 10 negative specs returned `BLOCKED_LOOP_SPEC`.
  - New gate specs:
    - `missing-gate-bypass-flags.json`: blocked on missing plan and delivery bypass fields.
    - `child-report-required-owner-report.json`: blocked on child report path and owner report path mismatch.
  - New compute specs:
    - `unauthorized-slurm-action.json`: blocked on unauthorized Slurm action, missing Slurm authorization, scheduler ack, wrapper, and Compute/HPC route.
    - `authorized-slurm-without-computerunner.json`: blocked on `compute_runner_missing`.
- Path scan over `git status --short`
  - Result: `path scan ok: no source/test/dependency/M3/PR6 status paths matched`
- Model scan over touched validation surface
  - Result: `model scan ok: gpt-5.5 present; gpt-5.6 absent in touched validation surface`
- Numeric future budget default scan over touched templates/runtime/backlog
  - Result: `budget scan ok: no numeric future budget defaults in touched templates/runtime/backlog`
- `git diff --check`
  - Result: exit `0`.

## Notes

- No source, test, dependency, M3 runtime, PR #6, AGENTS.md, staging, commit, push, or PR mutation was performed.
- `py_compile` initially generated `coordination/loops/templates/__pycache__/run-loop.cpython-312.pyc`; the generated cache was removed and syntax validation was rerun with in-memory `compile()`.
- Two temporary `/tmp` JSON probes used during the first RED check were removed. The permanent RED/GREEN evidence is represented by project-local validator specs under `runs/tmp/.../quality/validator-specs/`.
- No Slurm or compute job was submitted; the repair is governance-validator-only.
