# M1 PLAN — GenesisVLA Core Contract + Typed Config

## Your Role

You are the **Codex Manager**.
Milestone: **M1 — Core Contract + Typed Config**.
Stage: **PLAN**.

Claude Supervisor reviewed the (re-run) M1 DISCUSS report — which now includes code-input FluxVLA/dexbotic findings, a worker coverage ledger, and a publication-gate reminder — and chose `start_plan`.

You are **read-only** for source code during PLAN. You may write to:
- `.agent-docs/teamwork/reports/M1/PLAN.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/workspace/task-board.md`

Do NOT write source code during PLAN.

---

## Required Reading

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md` — especially **Minimum Worker Coverage** and **Milestone Publication Gate** sections
4. `.agent-docs/teamwork/reports/M1/DISCUSS.md` — your own DISCUSS findings
5. `.agent-docs/teamwork/roadmap_progress.md`
6. `.agent-docs/git_workflow.md` — for the publication gate plan
7. `docs/genesisvla/coding_standard.md`, `docs/genesisvla/testing_standard.md`
8. `pyrightconfig.genesisvla.json`, `Makefile`, `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/genesisvla.yml`
9. `tests/meta/test_repo_policy.py`

---

## Claude Supervisor Decisions (confirmed — include verbatim in PLAN)

1. **Extra tests approved**: M1 ships `tests/core/test_action.py` and `tests/core/test_registry.py` in addition to the blueprint's `tests/core/test_raw_sample.py` and `tests/config/test_loader.py`. F1.2 (ActionChunk) and F1.4 (Registry) need direct TDD coverage.

2. **Runtime deps approved**: add `numpy` and `omegaconf` to `[project].dependencies` in `pyproject.toml`. Do NOT add torch, pyyaml, hydra, accelerate, deepspeed, transformers, or any runtime/training/Slurm dependency. Do NOT change existing `[dev]` deps.

3. **OmegaConf bridge filename approved**: `genesisvla/config/loader/legacy_omegaconf.py`. Defer `migrate_starvla.py` until a real StarVLA migration milestone.

4. **No code-input copying**: FluxVLA and dexbotic archives are reference-only. M1 copies ZERO source from them. No file-header attribution issues arise because nothing is copied. The mmengine-derived registry and OpenVLA-derived runner from FluxVLA, and dexbotic's BaseExp/transforms, are explicitly NOT imported.

5. **Worker coverage ledger approved**:
   - DISCUSS: no worker (Manager read-only inspection done).
   - PLAN: Manager drafts; no implementation.
   - EXECUTE: **1× `coding_integration_engineer`, serial, write-capable, whitelist only.**
   - VERIFY: **1× `code_reviewer`, read-only, independent review** (plus Claude-run `make genesis-check` external evidence).
   - REVIEW: Manager synthesis + independent code_reviewer findings + final `make genesis-check` + path-boundary evidence + publication readiness.

6. **Serial-only contracts** (no parallelism): all of `genesisvla/core/types/*`, `genesisvla/core/protocols/*`, `genesisvla/core/registry/*`, `genesisvla/config/schema/*`, `genesisvla/config/loader/*`, `pyrightconfig.genesisvla.json`, `.pre-commit-config.yaml`, `Makefile`, `pyproject.toml`, `.github/workflows/genesisvla.yml`, `tests/meta/test_repo_policy.py`.

7. **Design decisions confirmed**: numpy-backed arrays (no torch in M1 code or tests); frozen+slots dataclasses; `RunnerBackend` enum = {local, accelerate, ddp, fsdp, deepspeed}; generic eager per-domain `Registry[T]` with Duplicate/Unknown errors; Chinese docstrings per DISCUSS Topic I.

8. **Publication gate awareness**: M1 is NOT complete after local REVIEW. After REVIEW acceptance, a separate publication step (scans + dev/* commit + push + PR URL) is required. The PLAN must include a "Publication Plan" section describing this, but EXECUTE itself does NOT push/PR (that happens in the publication gate after Claude accepts REVIEW).

---

## Plan Scope (from approved DISCUSS recommendation)

In-scope create list:
```text
genesisvla/core/types/__init__.py
genesisvla/core/types/sample.py
genesisvla/core/types/action.py
genesisvla/core/types/modality.py
genesisvla/core/types/framework.py
genesisvla/core/protocols/__init__.py
genesisvla/core/protocols/framework.py
genesisvla/core/protocols/runner.py
genesisvla/core/protocols/policy.py
genesisvla/core/registry/__init__.py
genesisvla/core/registry/registry.py
genesisvla/core/registry/errors.py
genesisvla/core/compat/__init__.py
genesisvla/core/compat/legacy_sample.py
genesisvla/config/schema/__init__.py
genesisvla/config/schema/base.py
genesisvla/config/schema/model.py
genesisvla/config/schema/data.py
genesisvla/config/schema/runner.py
genesisvla/config/schema/experiment.py
genesisvla/config/loader/__init__.py
genesisvla/config/loader/load_yaml.py
genesisvla/config/loader/merge_cli.py
genesisvla/config/loader/validate.py
genesisvla/config/loader/export.py
genesisvla/config/loader/legacy_omegaconf.py
genesisvla/config/presets/local_debug.yaml
tests/core/__init__.py
tests/core/test_raw_sample.py
tests/core/test_action.py
tests/core/test_registry.py
tests/config/__init__.py
tests/config/test_loader.py
```

In-scope governance updates:
```text
Makefile                              (extend genesis-check to cover tests/core tests/config)
pyrightconfig.genesisvla.json         (add tests/core, tests/config to include)
.pre-commit-config.yaml               (add tests/core, tests/config to path filters)
.github/workflows/genesisvla.yml      (add paths + install -e ".[dev]" + numpy/omegaconf)
pyproject.toml                        ([project].dependencies += numpy, omegaconf)
tests/meta/test_repo_policy.py        (update genesis-check fragment assertions)
```

Out of scope (blacklist): `starVLA/`, `code-input/`, `datasets/`, `runs/`, `configs/slurm/`, secrets, torch, deployment/acceleration/checkpoint/device modules, real model families, existing `pyrightconfig.json`, global `[tool.black]`/`[tool.ruff]` settings, existing `make check`/`autoformat` targets.

---

## Plan Requirements

PLAN.md must contain:

### 1. Confirmed Claude Decisions
Repeat the 8 decisions above.

### 2. In Scope vs Out of Scope
Whitelist + blacklist file lists.

### 3. Worker Coverage Ledger
A table covering DISCUSS / PLAN / EXECUTE / VERIFY / REVIEW with: worker type, count, mode, read/write, scope, and skip reasons where applicable. This is now a mandatory M1+ artifact per CLAUDE.md.

### 4. TDD Red-Green Sequence
Exact ordered steps. Tests first (red), then implementation (green). For each of the 4 test files, list the test function names and what each asserts. Map the blueprint-required test names plus the approved extra tests.

### 5. Implementation Tasks
Numbered tasks the EXECUTE worker follows. Group logically (types → protocols → registry → compat → config schema → config loader → preset → tests → governance). Each task: target files, steps, expected local check, expected result.

### 6. Type/Contract Specifications
Precise signatures for:
- `RawSample`, `BatchSample`, `ModelInput`, `FrameworkOutput` (F1.1)
- `ActionChunk`, `ActionMask`, `ActionSpace` (F1.2)
- `FrameworkProtocol`, `RunnerProtocol`, `PolicyProtocol` (F1.3) — method names + signatures
- `Registry[T]` + `RegistryError`/`DuplicateRegistrationError`/`UnknownRegistrationError` (F1.4)
- `RunnerBackend` enum
- `BaseConfig`, `ModelConfig`, `DataConfig`, `RunnerConfig`, `ExperimentConfig` field lists (F1.5)
- `legacy_sample.from_legacy_dict(...)` shape
- loader functions: `load_yaml`, `merge_cli`(dotlist), `validate`, `export`, `legacy_omegaconf` bridge (F1.6, F1.7)

Be precise enough that the worker has no architecture latitude.

### 7. Config Schema Field Lists + Preset
Exact fields for each config dataclass and the exact `local_debug.yaml` content shape.

### 8. Governance Update Specs
Exact changes for Makefile, pyrightconfig, pre-commit, CI workflow, pyproject, and the meta test fragment update. Note the M0 Black `--workers 1` mitigation must be preserved and applied to the expanded path set.

### 9. Validation Plan (V1-Vn for VERIFY)
Define checks the VERIFY stage (code_reviewer + Claude) runs. At minimum:
- V1: all in-scope files exist
- V2: `pytest tests/core tests/config -v` → all pass
- V3: `pytest tests/meta/test_repo_policy.py -v` → 4 pass
- V4: `make genesis-check` → exit 0 (note: Claude runs this externally per M0 sandbox finding)
- V5: `pyright -p pyrightconfig.genesisvla.json` → 0 errors over expanded scope
- V6: path-boundary git status — only whitelist changed; no starVLA/code-input/datasets/runs touched
- V7: code_reviewer independent review (correctness, contract coherence, no torch, no code-input copying, license cleanliness, Chinese docstrings, frozen/slots, complexity)

### 10. Publication Plan
Per CLAUDE.md Milestone Publication Gate. Describe the steps that will run AFTER Claude accepts REVIEW: read git_workflow.md scans, commit on dev/*, push to origin, open/update PR, record PR URL. Note EXECUTE does NOT push/PR.

### 11. Rollback Plan
Exact rm/git restore commands.

### 12. Risk List
Include DISCUSS risks + license/attribution + publication risk.

### 13. Recommended Next Stage
`approve_execute` with the worker plan in section 3.

---

## Output

Write to:
```
.agent-docs/teamwork/reports/M1/PLAN.md
```

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
Decisions:
- ...
Files Affected:
- .agent-docs/teamwork/reports/M1/PLAN.md (written)
Next-Actor-Notes:
Returning control to Claude Supervisor.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

STOP after PLAN.md and HANDOFF. Do NOT write code, run TDD, or launch the EXECUTE worker.
EXECUTE requires Claude's explicit `approve_execute`.
