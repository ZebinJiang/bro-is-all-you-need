# M1 VERIFY — Independent code_reviewer

## Your Role

You are the **Codex Manager**. Milestone **M1**, stage **VERIFY**.

Claude ran external validation and confirmed:
- bare `pytest tests/core tests/config -v` → 14 passed (after EXECUTE-FIX-1)
- `pytest tests/meta tests/core tests/config` → 18 passed
- `make genesis-check` → **exit 0** in a deps-present env (Black + Ruff + Pyright 0 errors + 18 tests)
- The Codex sandbox 142-pyright-errors / Black-timeout are known environment issues, NOT code defects.

Functional correctness is established. VERIFY now adds the **mandatory M1+ independent review**: dispatch **1× read-only `code_reviewer`** worker over the M1 deliverables.

---

## Required Reading

1. `AGENTS.md`, `CLAUDE.md` (Minimum Worker Coverage)
2. `.agent-docs/teamwork/reports/M1/PLAN.md` (Section 6 contracts, Section 9 V7 review checklist)
3. `.agent-docs/teamwork/reports/M1/EXECUTE.md`
4. `.agent-docs/teamwork/reports/M1/EXECUTE_FIX_1.md`
5. `.codex/agents/code_reviewer.toml`

---

## Approved Worker Plan

```
Worker type: code_reviewer
Count: 1
Mode: serial, READ-ONLY
Scope: review all M1 deliverables for correctness, contract coherence, and governance.
Writable paths: NONE (read-only worker). Findings reported to Manager only.
```

If the `code_reviewer` finds defects, do NOT fix them inline — record them; Claude will decide
return-to-PLAN or scoped EXECUTE-fix. VERIFY is not a fix stage.

## Review Targets

All M1 source + tests + governance:
```
genesisvla/core/types/*.py
genesisvla/core/protocols/*.py
genesisvla/core/registry/*.py
genesisvla/core/compat/*.py
genesisvla/config/schema/*.py
genesisvla/config/loader/*.py
genesisvla/config/presets/local_debug.yaml
tests/core/*.py, tests/config/*.py
Makefile, pyrightconfig.genesisvla.json, .pre-commit-config.yaml,
.github/workflows/genesisvla.yml, pyproject.toml, tests/meta/test_repo_policy.py
```

## Review Checklist (PLAN Section 9 V7)

The code_reviewer must check and report on:
- correctness of validation logic (action shape, mask shape, required modalities, duplicate/missing registry key, invalid backend)
- contract coherence: do RawSample/BatchSample/ModelInput/FrameworkOutput/ActionChunk/ActionSpace/Protocols/Registry/config dataclasses fit together cleanly?
- no torch import anywhere in M1 code or tests
- no code copied from code-input archives WITHOUT a file-header attribution (copy-with-attribution is now ALLOWED per user directive — flag only un-attributed copies; clean original code is fine)
- all new Python modules have Chinese module docstrings; public classes/functions have Chinese docstrings
- frozen+slots on all dataclasses
- registry is generic, eager, per-instance, deterministic (sorted names/items)
- OmegaConf bridge does not import StarVLA or migrate StarVLA configs
- quality gates correctly cover tests/core + tests/config; M0 `make check` and global tool config untouched
- complexity is linear; no hidden large-array copies in hot paths
- no baseline (`starVLA/`) contamination; no dataset/run/Slurm/secret content

## VERIFY Manager Tasks

1. Dispatch the code_reviewer over the targets.
2. Collect findings, classify each as: blocking-defect | non-blocking-risk | clean.
3. Re-state Claude's external gate evidence (18 passed, make genesis-check exit 0) as the validation record.
4. Write `.agent-docs/teamwork/reports/M1/VERIFY.md`.
5. Recommend: `accept_m1_to_review` (if no blocking defects) | `return_to_plan` | `scoped_execute_fix` (if blocking defects found).

## Writable paths (Manager)

- `.agent-docs/teamwork/reports/M1/VERIFY.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude)

NO source edits in VERIFY.

## VERIFY Report Requirements

`.agent-docs/teamwork/reports/M1/VERIFY.md`:
1. code_reviewer dispatch summary + agent id
2. Findings table: each finding with severity + file + recommendation
3. Claude external gate evidence restated (18 passed, make genesis-check exit 0)
4. Contract-coherence assessment
5. Worker coverage ledger status (EXECUTE=coding_integration_engineer done; VERIFY=code_reviewer done)
6. Residual risks
7. Recommendation: accept_m1_to_review | return_to_plan | scoped_execute_fix

## Stop Condition

STOP after VERIFY.md + HANDOFF. Do NOT start REVIEW or publication.

End with `===HANDOFF=== ... Next actor: Claude. ===END HANDOFF===`.
