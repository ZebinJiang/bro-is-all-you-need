# M1 EXECUTE — GenesisVLA Core Contract + Typed Config

## Your Role

You are the **Codex Manager**.
Milestone: **M1 — Core Contract + Typed Config**.
Stage: **EXECUTE**.

Claude Supervisor reviewed `.agent-docs/teamwork/reports/M1/PLAN.md` and approved `approve_execute`.

Your job:
1. Dispatch the **approved `coding_integration_engineer` worker** to implement the M1 plan with TDD red-green.
2. Review worker output.
3. Run V1-V6 validation; V7 (independent code_reviewer) happens in the VERIFY stage, not here.
4. Write `.agent-docs/teamwork/reports/M1/EXECUTE.md`.
5. Return `===HANDOFF===` to Claude.

---

## Standing User Directives (NEW — apply from now on)

The user gave two standing directives on 2026-06-18:

1. **Efficiency first, quality first. Do not ration Codex usage.** Use workers freely and thoroughly.

2. **Copy-with-attribution is ALLOWED.** Code under `code-input/` (FluxVLA, dexbotic) MAY be copied/adapted into GenesisVLA. This is a private non-commercial repo, so the only requirement is a **file-header attribution block** (upstream source + original license) on any file containing copied/adapted code. This overrides the earlier "no copying" stance in M1 DISCUSS/PLAN.

**Application to M1 specifically:** M1 is the minimal contract layer. The upstream registry (FluxVLA mmengine-derived) and config (dexbotic BaseExp) are HEAVIER than M1 needs, so for M1 you should still write minimal original contracts per the PLAN specs — that is both higher quality and faster here. Do NOT pull in mmengine/BaseExp. The copy policy is recorded for M2+ where it pays off. If during EXECUTE you find a specific small helper from code-input that genuinely improves an M1 file, you MAY adapt it WITH a Chinese file-header attribution block; otherwise build original per PLAN.

---

## Required Reading

1. `AGENTS.md` (esp. rule 32 third-party attribution)
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/teamwork/reports/M1/PLAN.md` — **full implementation spec; this is the source of truth**
5. `.agent-docs/teamwork/reports/M1/DISCUSS.md`
6. `.codex/agents/coding-integration-engineer.toml`
7. `docs/genesisvla/coding_standard.md`, `docs/genesisvla/testing_standard.md`

---

## Approved Worker Plan (verbatim from PLAN Section 13)

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M1 artifacts, run TDD red-green and validation, capture evidence.
Writable paths: PLAN Section 2.1 whitelist only.
Read-only paths: all others.
Stop condition: tests and gates in PLAN Sections 4 and 9 are run or documented with exact blocker; worker returns changed files, commands, outputs, complexity notes, residual risks, rollback notes.
Worker must not: modify out-of-scope paths, add forbidden dependencies (torch/pyyaml/hydra/accelerate/deepspeed/transformers), launch workers, run Slurm, push, create PRs, or mark M1 complete.
```

Writable whitelist (33 create + 6 governance files) — exactly PLAN Section 2.1:
```
genesisvla/core/types/{__init__,sample,action,modality,framework}.py
genesisvla/core/protocols/{__init__,framework,runner,policy}.py
genesisvla/core/registry/{__init__,registry,errors}.py
genesisvla/core/compat/{__init__,legacy_sample}.py
genesisvla/config/schema/{__init__,base,model,data,runner,experiment}.py
genesisvla/config/loader/{__init__,load_yaml,merge_cli,validate,export,legacy_omegaconf}.py
genesisvla/config/presets/local_debug.yaml
tests/core/{__init__,test_raw_sample,test_action,test_registry}.py
tests/config/{__init__,test_loader}.py
Makefile
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
pyproject.toml
tests/meta/test_repo_policy.py
```

Out of scope (must NOT touch): `starVLA/`, `code-input/` (read-only reference; do not mutate the archives), `datasets/`, `runs/`, `configs/slurm/`, `pyrightconfig.json` (legacy), global `[tool.black]`/`[tool.ruff]`, existing `make check`/`autoformat` targets, existing `[dev]` deps.

---

## Critical Worker Instructions

Pass to the worker:

1. **TDD order (PLAN Section 4)**: write the 4 test files FIRST (`tests/core/test_raw_sample.py`, `test_action.py`, `test_registry.py`, `tests/config/test_loader.py`), run `pytest tests/core tests/config -v` to capture RED, then implement, then capture GREEN.

2. **Type/contract specs are exact (PLAN Section 6)**: follow the dataclass signatures, validation rules, protocol method names, registry API, RunnerBackend enum, config field lists, legacy_sample adapter rules, and loader function signatures precisely.

3. **Config schema + preset (PLAN Section 7)**: exact field lists and exact `local_debug.yaml` content.

4. **Governance updates (PLAN Section 8)**:
   - Makefile genesis-check extended to `genesisvla tests/meta tests/core tests/config`, preserving `--workers 1`.
   - pyrightconfig include += tests/core, tests/config.
   - pre-commit path filters += tests/(core|config).
   - CI workflow: add paths + replace install with `pip install -e ".[dev]"`.
   - pyproject `[project].dependencies` += numpy, omegaconf (ADDITIVE; do not touch [dev] or [tool.*]).
   - tests/meta/test_repo_policy.py: update genesis-check fragment + pyright include assertions.

5. **numpy-only, no torch** in M1 code and tests.

6. **frozen+slots** for all dataclasses; Chinese docstrings on all modules/public classes/functions per PLAN Section 6 and coding_standard.md.

7. **Tool env**: `numpy` and `omegaconf` must be importable. If missing, install into the worker env (`pip install -e ".[dev]" numpy omegaconf`, or reuse `/tmp/vla-flywheel-m0-tools` venv + add numpy/omegaconf). Record install commands.

8. **No code-input copying needed for M1** (upstream too heavy). If a small adaptation is genuinely used, add a Chinese file-header attribution block.

---

## Validation Checks (Manager runs after worker; PLAN Section 9)

- **V1**: file-existence script (PLAN Section 9 V1) → `V1 PASS`
- **V2**: `pytest tests/core tests/config -v` → 14 passed
- **V3**: `pytest tests/meta/test_repo_policy.py -v` → 4 passed
- **V4**: `make genesis-check` → exit 0. NOTE: if the Codex sandbox Black directory-check timeout (known M0 issue) recurs, run each step individually AND record that Claude will run `make genesis-check` externally. Do not block on the sandbox timeout — capture per-step exit codes.
- **V5**: `pyright -p pyrightconfig.genesisvla.json` → 0 errors
- **V6**: `git status --short` + `git diff --name-only HEAD` → only whitelist changed; pre-existing dirty paths noted not reverted; no starVLA/code-input/datasets/runs touched

(V7 independent code_reviewer is the VERIFY stage — not here.)

---

## Writable Paths For Manager (EXECUTE)

- `.agent-docs/teamwork/reports/M1/EXECUTE.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude after handoff)
- plus the worker's writable whitelist (worker writes via Manager)

---

## EXECUTE Report Requirements

Write `.agent-docs/teamwork/reports/M1/EXECUTE.md`:
1. Worker dispatch summary
2. Changed files (with sizes or sha256)
3. Full RED pytest output
4. Full GREEN pytest output (tests/core tests/config = 14 passed)
5. `make genesis-check` output (or per-step exit codes if sandbox timeout)
6. V1-V6 results
7. Complexity/performance notes
8. Any code-input adaptation + attribution (or "none")
9. Residual risks
10. Rollback notes
11. Recommended next stage: VERIFY (1× code_reviewer)

---

## Stop Condition

STOP after EXECUTE.md + HANDOFF. Do NOT start VERIFY. Do NOT push/PR (publication gate is post-REVIEW).

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude gate decision for VERIFY (1× code_reviewer).
Decisions:
- ...
Files Affected:
- [whitelist files]
- .agent-docs/teamwork/reports/M1/EXECUTE.md (written)
Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting VERIFY gate.
Next actor: Claude.
===END HANDOFF===
```
