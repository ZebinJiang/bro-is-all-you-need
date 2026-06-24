# GenesisVLA Local Teamwork Task Board

## Mission

Build GenesisVLA — a 7-layer VLA platform on StarVLA base — through a supervised Claude Supervisor → Codex Manager → Codex Worker chain.

## Active Task

| Field | Value |
|-------|-------|
| Milestone | M1 — Core Contract + Typed Config |
| Stage | EXECUTE-FIX-2 completed |
| Next Actor | Claude |
| Status | **M1 EXECUTE-FIX-2 completed by Codex Manager.** Legacy metadata contract fixed in `legacy_sample.py` and `test_raw_sample.py`; targeted pytest evidence is green; awaiting Claude decision for VERIFY-2 or REVIEW. |

## Completed Tasks

| Milestone | Stage | Status |
|-----------|-------|--------|
| P0 | DISCUSS | completed |
| P0 | PLAN | completed |
| P0 | EXECUTE | completed |
| P0 | VERIFY | completed |
| P0 | REVIEW | **accepted** — P0 COMPLETE |
| M0 | DISCUSS | completed |
| M0 | PLAN | completed |
| M0 | EXECUTE | completed |
| M0 | VERIFY | completed |
| M0 | REVIEW | **accepted** — M0 COMPLETE |
| M1 | DISCUSS | completed |
| M1 | PLAN | completed |
| M1 | EXECUTE | completed — functional tests green; VERIFY pending independent review |
| M1 | EXECUTE-FIX-1 | completed — bare pytest pythonpath defect fixed |
| M1 | VERIFY | completed — independent code review recommends scoped execute fix |
| M1 | EXECUTE-FIX-2 | completed — legacy metadata contract fixed |

## P0 Deliverable

- `scripts/teamwork/dispatch_codex_manager.py` — local Codex Manager dispatch wrapper

## M0 Task Description

M0: GenesisVLA RFC 与质量闸门 (Week 1-2)

Features (from blueprint):
- F0.1 `docs/genesisvla/rfc_000_architecture.md`
- F0.2 `docs/genesisvla/coding_standard.md`
- F0.3 `docs/genesisvla/testing_standard.md`
- F0.4 `pyrightconfig.genesisvla.json`
- F0.5 pre-commit config for new directories
- F0.6 CI: lint/type/unit-smoke on `genesisvla/core` and `genesisvla/config`
- F0.7 GenesisVLA branch policy and PR template

TDD: `tests/meta/test_repo_policy.py`
Done target: `make genesis-check` 绿色, strict typing, old StarVLA backlog isolated.

## M0 Current Evidence

- F0.1-F0.7 artifacts exist.
- `tests/meta/test_repo_policy.py -v` passes with 4 tests.
- `pyright -p pyrightconfig.genesisvla.json` passes with 0 errors.
- `docs/genesisvla/*.md` are no longer ignored after `.gitignore` exception.
- **`make genesis-check` exits 0 in Claude Supervisor independent verification** (non-sandboxed bash env). Codex sandbox limitation documented as non-blocking environment issue.

## M0 Deliverables (15 files)

- F0.1: `docs/genesisvla/rfc_000_architecture.md`
- F0.2: `docs/genesisvla/coding_standard.md` (with branch policy section)
- F0.3: `docs/genesisvla/testing_standard.md`
- F0.4: `pyrightconfig.genesisvla.json`
- F0.5: `.pre-commit-config.yaml`
- F0.6: `.github/workflows/genesisvla.yml` + `Makefile` `genesis-check` target
- F0.7: `.github/PULL_REQUEST_TEMPLATE.md` (updated)
- TDD: `tests/meta/__init__.py`, `tests/meta/test_repo_policy.py`
- Stubs: `genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py`, `genesisvla/py.typed`
- Gov patch: `.gitignore` (`!docs/genesisvla/**/*.md` exception)
- Deps: `pyproject.toml` (`[dev]` += pytest, pyright)

## Comm Log

| Time | From | To | Message |
|------|------|----|---------|
| 2026-06-18 | Claude | Codex | Dispatched P0 DISCUSS bootstrap |
| 2026-06-18 | Codex | Claude | P0 DISCUSS report — start_plan |
| 2026-06-18 | Claude | Codex | Dispatched P0 PLAN |
| 2026-06-18 | Codex | Claude | P0 PLAN report — approve_execute |
| 2026-06-18 | Claude | Codex | Dispatched P0 EXECUTE |
| 2026-06-18 | Codex | Claude | P0 EXECUTE report — V1-V5 PASS — wrapper created |
| 2026-06-18 | Claude | Codex | Dispatched P0 VERIFY |
| 2026-06-18 | Codex | Claude | P0 VERIFY report — accept_p0 |
| 2026-06-18 | Claude | System | P0 REVIEW: accept_p0. P0 COMPLETE. Next: M0 DISCUSS |
| 2026-06-18 | Codex | Claude | M0 DISCUSS report — start_plan |
| 2026-06-18 | Codex | Claude | M0 PLAN report — approve_execute |
| 2026-06-18 | Codex | Claude | M0 EXECUTE report — artifacts created, V3 tooling concern |
| 2026-06-18 | Codex | Claude | M0 VERIFY report — request_fixes for Black timeout |
| 2026-06-18 | Codex | Claude | M0 REVIEW report — authorized patch applied, V3 still times out, request_fixes |
| 2026-06-18 | Claude | System | M0 REVIEW: accept_m0 by Claude independent `make genesis-check` (exit 0). M0 COMPLETE. Next: M1 DISCUSS |

## Shared Context

- Blueprint: `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
- Protocol: `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- Usage guide: `.agent-docs/teamwork/claude_supervisor_usage.md`
- Progress: `.agent-docs/teamwork/roadmap_progress.md`
- Wrapper: `scripts/teamwork/dispatch_codex_manager.py`
- Session: `019ed892-624f-7453-ad1a-3131b2000cce`
- Registered code-input references: `code-input/FluxVLA-main.zip`, `code-input/dexbotic-main.zip`

## Registered Code-Input References

- `code-input/FluxVLA-main.zip`: read-only reference for runner lifecycle, deployment/inference, acceleration, registry/config, and checkpoint lifecycle patterns.
- `code-input/dexbotic-main.zip`: read-only reference for typed/dataclass config, transform pipeline, backend enum/config, and maintainability patterns.
- These archives must be inspected for M1 DISCUSS and later planning where relevant.
- Do not mutate or directly copy from `code-input/`; any integration requires Code-Input Integration Workflow, license/source attribution review, and Claude-approved worker plan.

## M1+ Worker Coverage Policy

- `PLAN` creates a worker coverage ledger.
- `EXECUTE` implementation changes require an approved write-capable worker.
- `VERIFY` requires independent read-only worker evidence or Claude external validation evidence.
- `REVIEW` requires independent review evidence and closes the ledger.
- `VERIFY`/`REVIEW` defects return to `PLAN` or scoped `EXECUTE`; Codex Manager must not patch fixes inline in those stages.

## Milestone Publication Policy

- Every completed GenesisVLA milestone must be committed on a `dev/*` branch, pushed, and represented by an opened or updated PR.
- Claude must receive the pushed branch, commit SHA, and PR URL before marking the milestone complete or starting the next milestone.
- If push or PR creation is blocked, status becomes `ready_to_publish_blocked`, not complete.
- Do not merge PRs unless the user explicitly asks for review and merge.

## M1 Current Evidence

- M1 core/config tests pass: `pytest tests/core tests/config -v` -> 14 passed.
- M1 policy + core/config tests pass together: `pytest tests/meta/test_repo_policy.py tests/core tests/config -v` -> 18 passed.
- Bare `pytest` now imports `genesisvla` through `[tool.pytest.ini_options] pythonpath = ["."]`.
- Ruff path-scoped check passes.
- Per-file Black fallback passes; full `make genesis-check` may still hit the known Codex sandbox Black timeout.
- Venv-aware Pyright diagnostic passes with 0 errors.
- Claude external validation confirms `make genesis-check` exits 0 in a dependency-present environment.
- M1 independent `code_reviewer` completed in VERIFY: functional gates are green, but `genesisvla/core/compat/legacy_sample.py` does not preserve `robot_tag` or top-level `episode_id` into metadata as the approved M1 contract requires.
- M1 EXECUTE-FIX-2 updated `legacy_sample.py` to preserve resolved `robot_tag` and top-level `episode_id` into metadata.
- `pytest tests/core/test_raw_sample.py -v` -> 5 passed.
- `pytest tests/core tests/config -v` -> 15 passed.
- `pytest tests/meta tests/core tests/config -v` -> 19 passed.

## Next Proposed Action

Claude decides between VERIFY-2 re-review of the two scoped files or proceeding to REVIEW with external full-gate evidence. Codex Manager recommends VERIFY-2 because EXECUTE-FIX-2 changed source and tests after the independent review.
