# M0 PLAN — GenesisVLA RFC 与质量闸门

## Your Role

You are the **Codex Manager**.
Milestone: **M0 — GenesisVLA RFC 与质量闸门**.
Stage: **PLAN**.

Claude Supervisor has reviewed the DISCUSS report and chose `start_plan`.

You are **read-only** for source code during this stage. You may write to:
- `.agent-docs/teamwork/reports/M0/PLAN.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/workspace/task-board.md`

Do NOT write source code, docs, tests, configs, or scripts during PLAN.

---

## Required Reading (do this first)

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/GenesisVLA_Blueprint_Roadmap.html` — sections: M0 Features + TDD, Code Standards, CI/CD 规范
5. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
6. `.agent-docs/teamwork/roadmap_progress.md`
7. `.agent-docs/teamwork/reports/M0/DISCUSS.md`  ← full DISCUSS findings
8. `pyproject.toml`
9. `Makefile`
10. `.github/PULL_REQUEST_TEMPLATE.md`
11. `pyrightconfig.json`
12. `tests/README.md`

---

## Claude Supervisor Decisions (from DISCUSS review)

These are confirmed and must appear verbatim in your PLAN:

1. **Q1 — Minimal `genesisvla/` stubs**: **YES**. EXECUTE creates `genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py`, and `genesisvla/py.typed`. No real platform behavior; the stubs exist so pyright strict and CI have actual targets.

2. **Q2 — F0.7 branch policy location**: **Section inside `docs/genesisvla/coding_standard.md`**. Do not create a separate `branch_policy.md` in M0.

3. **Q3 — `pyproject.toml` dev deps**: **YES — add `pytest` and `pyright` to `[project.optional-dependencies].dev`**. This makes `make genesis-check` reproducible from project metadata. Do not change existing dev deps (`black`, `ruff`, `pre-commit`).

4. **Q4 — Line length 100 for GenesisVLA**: **YES — enforce 100 only on GenesisVLA paths via explicit command args (`--line-length 100` for black, `--line-length 100` for ruff via `--config`/per-call)**. Do not modify the global `[tool.black]`/`[tool.ruff]` line length (121) in `pyproject.toml`.

   Implementation note: ruff supports per-call config via `--config 'line-length=100'`. Black supports `--line-length 100` directly. If a per-directory pyproject sub-config is cleaner, the PLAN may propose it instead — Claude will review the choice in PLAN, not auto-approve a deviation.

5. **TDD red-green required**: EXECUTE must capture the red output of `tests/meta/test_repo_policy.py` before creating M0 artifacts, then capture the green output after. Both must appear in `EXECUTE.md`.

6. **Wrapper-mediated dispatch**: All Codex Manager dispatch from M0 onwards uses `scripts/teamwork/dispatch_codex_manager.py`.

---

## Plan Scope

In-scope EXECUTE artifacts (mandatory):

```text
docs/genesisvla/rfc_000_architecture.md            (F0.1)
docs/genesisvla/coding_standard.md                  (F0.2 + branch policy section per Q2)
docs/genesisvla/testing_standard.md                 (F0.3)
pyrightconfig.genesisvla.json                       (F0.4)
.pre-commit-config.yaml                             (F0.5, path-scoped)
.github/workflows/genesisvla.yml                    (F0.6)
.github/PULL_REQUEST_TEMPLATE.md                    (F0.7 — update, not duplicate)
Makefile                                            (add `genesis-check` target only)
pyproject.toml                                      (add pytest+pyright to [dev] only)
tests/meta/__init__.py
tests/meta/test_repo_policy.py
genesisvla/__init__.py                              (stub per Q1)
genesisvla/core/__init__.py                         (stub per Q1)
genesisvla/config/__init__.py                       (stub per Q1)
genesisvla/py.typed                                 (marker per Q1)
```

Out-of-scope (must not be modified by EXECUTE):
- `starVLA/` (any path)
- `pyrightconfig.json` (legacy, leave as-is)
- existing `make check` target (only ADD `genesis-check`, do not modify `check`)
- global `[tool.black]` / `[tool.ruff]` settings in `pyproject.toml` (only ADD `[dev]` deps)
- any dataset, checkpoint, Slurm config, robot endpoint, secrets
- `docs/branching_strategy.md`, `docs/CONTRIBUTING.md`, `docs/PR_readme.md`, `docs/starVLA_guideline.md`, other existing StarVLA docs
- `code-input/`, `related-assets/`, `datasets/`, `runs/`, `.agents/`, `.codex/`

---

## Plan Requirements

Your PLAN.md must contain all of:

### 1. Confirmed Claude Decisions

Repeat the 6 decisions above verbatim.

### 2. In Scope vs Out of Scope

Explicit file lists, both whitelist (EXECUTE may write) and blacklist (EXECUTE must not touch).

### 3. TDD Red-Green Sequence

Spell out the exact ordered steps EXECUTE must follow. Concretely:

```
Step T1: Create tests/meta/__init__.py and tests/meta/test_repo_policy.py with 4 tests:
  - should_have_genesisvla_docs
  - should_have_make_genesis_check
  - should_have_pyright_strict_config
  - should_have_pr_template_with_test_plan
Step T2: Run pytest tests/meta/test_repo_policy.py -v, capture RED output (all 4 fail).
Step T3: Create docs/genesisvla/ stubs, pyrightconfig, Makefile target, PR template update, etc.
Step T4: Run pytest tests/meta/test_repo_policy.py -v, capture GREEN output (all 4 pass).
Step T5: Run make genesis-check, capture green output.
```

For each test, specify what it asserts (paths exist, file contains "make genesis-check" string, etc.).

### 4. Implementation Tasks

Number each task with:
- target file(s)
- exact steps
- expected local check command
- expected check result

Tasks should cover all in-scope artifacts. Group them so a single `coding_integration_engineer` worker can complete them serially.

### 5. Doc Content Outlines

For each of the 3 docs (`rfc_000_architecture.md`, `coding_standard.md`, `testing_standard.md`), provide a section-by-section outline of what the doc must contain. This must be detailed enough that the EXECUTE worker has no creative latitude on policy decisions — only writing latitude.

`coding_standard.md` must include the branch policy section (per Q2).

### 6. Config Schemas

Provide the exact content shape (not necessarily literal text) for:
- `pyrightconfig.genesisvla.json` — full JSON with include/exclude/strict
- `.pre-commit-config.yaml` — exact hooks and `files:` filter
- `.github/workflows/genesisvla.yml` — trigger paths, jobs, steps
- `Makefile` `genesis-check` target body (lines added)
- `pyproject.toml` dev deps addition (which keys, no global changes)
- PR template addition (the GenesisVLA Test Plan section content)

### 7. Worker Plan

Claude pre-approves exactly:

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M0 artifacts, run TDD red-green and make genesis-check, capture validation output.
Writable paths: (the whitelist from section 2)
Read-only paths: all others, including starVLA/, datasets/, runs/, secrets, baseline configs.
Stop condition: all in-scope artifacts exist, pytest tests/meta/test_repo_policy.py green, make genesis-check green, worker returns evidence.
Worker must not: launch additional workers, modify out-of-scope files, push, PR, sbatch, set passes=true.
```

Include this verbatim in PLAN.md.

### 8. Validation Plan (V1-V6 for VERIFY stage)

Define each VERIFY check with the exact command and expected output. At minimum:

- V1: All in-scope files exist (list and check).
- V2: `pytest tests/meta/test_repo_policy.py -v` exits 0 with 4 passed.
- V3: `make genesis-check` exits 0.
- V4: Pyright strict check on `genesisvla/` directory exits 0.
- V5: Path-boundary git status — no out-of-scope files changed.
- V6: Manager inline review of all new docs/configs/scripts for: Chinese docstrings on Python files, no StarVLA baseline edit, no Slurm/push/PR/secret content, no global pyproject changes beyond [dev].

### 9. Rollback Plan

How to undo M0 EXECUTE cleanly. List exact commands.

### 10. Risk List

Include all DISCUSS risks plus any new ones.

### 11. Recommended Next Stage

`approve_execute`, with worker plan exactly as in section 7.

---

## Output

Write your complete PLAN to:
```
.agent-docs/teamwork/reports/M0/PLAN.md
```

End your final response with:

```
===HANDOFF===
Completed:
- ...
Pending:
- ...
Decisions:
- ...
Files Affected:
- .agent-docs/teamwork/reports/M0/PLAN.md (written)
Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

STOP after writing PLAN.md and HANDOFF.
Do NOT implement, write source/docs/configs/tests, run TDD, or run `make genesis-check`.
EXECUTE requires Claude's explicit `approve_execute` gate decision.
