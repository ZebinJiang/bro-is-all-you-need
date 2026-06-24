# M0 DISCUSS -- GenesisVLA RFC 与质量闸门

Date: 2026-06-18
Stage: DISCUSS
Manager: Codex
Milestone: M0 -- GenesisVLA RFC 与质量闸门

## 1. Investigation Summary

Required governance and context files were read:

- `AGENTS.md`
- `boundaries.txt`
- `CLAUDE.md`
- `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
- `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/repository_layout_policy.md`
- `scripts/init.sh`
- `scripts/smoke_test.sh`

Blueprint facts for M0:

- M0 is the first real GenesisVLA engineering milestone after P0.
- Scope is governance and quality gates only: RFC docs, coding/testing standards, pyright strict config, pre-commit, CI, branch/PR policy.
- Definition of Done:
  - `make genesis-check` is green.
  - Strict typing applies to new GenesisVLA directories.
  - Existing StarVLA backlog does not affect GenesisVLA CI.
- TDD target:

```text
tests/meta/test_repo_policy.py
- should_have_genesisvla_docs
- should_have_make_genesis_check
- should_have_pyright_strict_config
- should_have_pr_template_with_test_plan
```

Current repository facts:

- Branch: `dev/starvla-engineering-base`.
- `docs/` exists; `docs/genesisvla/` does not exist.
- `genesisvla/` does not exist.
- `tests/` exists with only `.gitkeep` and `README.md`; no Python tests currently exist.
- `pyrightconfig.json` exists and has `"typeCheckingMode": "off"`.
- No `pyrightconfig.genesisvla.json` exists.
- `.pre-commit-config.yaml` does not exist.
- `.github/workflows/` does not exist.
- `.github/PULL_REQUEST_TEMPLATE.md` exists; lowercase `.github/pull_request_template.md` does not exist.
- `Makefile` exists with `help`, `clean`, `check`, and `autoformat`; no `genesis-check`.
- `pyproject.toml` has Black/Ruff settings at line length 121 and dev deps for `black`, `ruff`, and `pre-commit`, but not `pytest` or `pyright`.
- Existing StarVLA docs include `branching_strategy.md`, `CONTRIBUTING.md`, `PR_readme.md`, `starVLA_guideline.md`, `model_zoo.md`, `faq.md`, and `WM4A.md`.
- `scripts/init.sh` and `scripts/smoke_test.sh` are local governance/smoke baselines; `smoke_test.sh` validates existing governance files, mock execution, and Slurm dry-run generation, not M0 GenesisVLA quality gates.

## 2. Topic A -- Doc Placement And Scope

Findings:

- `docs/genesisvla/` does not exist.
- `docs/` is the natural parent:
  - The blueprint target tree explicitly lists `docs/genesisvla/`.
  - Existing StarVLA docs already live under `docs/`.
  - Adding a subdirectory avoids rewriting upstream StarVLA docs in M0.
- Existing StarVLA docs overlap procedurally with F0.7, but not directly with F0.1-F0.3:
  - `docs/branching_strategy.md` covers StarVLA `starVLA` / `starVLA_dev` branch flow.
  - `docs/PR_readme.md` and `docs/CONTRIBUTING.md` cover StarVLA contribution process and acknowledge full-repo `make check` backlog.
  - `docs/starVLA_guideline.md` is an end-to-end StarVLA training/eval guide, not GenesisVLA architecture standards.

Recommendation:

- M0 docs should be minimal but substantive contract documents, not empty stubs.
- They should be short enough to unblock CI and future planning, but contain real policy decisions that tests can assert.
- Avoid full exhaustive design docs in M0; detailed design belongs in later RFCs or milestone docs.

Minimum viable content:

- `docs/genesisvla/rfc_000_architecture.md`
  - Title, status, date, scope, non-goals.
  - GenesisVLA identity and relationship to StarVLA.
  - Seven-layer architecture summary: core, config, data, model, runner, deployment, acceleration.
  - Initial path policy: `genesisvla/` for new code, `starVLA/` remains legacy baseline.
  - M0 quality-gate decision: `make genesis-check` independent from old StarVLA backlog.

- `docs/genesisvla/coding_standard.md`
  - Python 3.10 baseline.
  - Black, Ruff, Pyright strict for new GenesisVLA directories.
  - GenesisVLA line length target from blueprint: 100, with note that existing StarVLA `pyproject.toml` still uses 121 for legacy code.
  - Chinese docstrings/comments for new or modified code per `AGENTS.md`.
  - No wildcard imports, no library `print`, no implicit `.cuda()`, no naked `dict[str, Any]` across core boundaries.

- `docs/genesisvla/testing_standard.md`
  - TDD-first: tests are written before implementation.
  - Test categories: unit, failure-mode, config validation, smoke.
  - `make genesis-check` is the local M0 gate.
  - Local vs Slurm boundary: CPU/static checks local; compute-heavy behavior requires Slurm later.
  - Existing StarVLA lint/type backlog must not block GenesisVLA gates.

## 3. Topic B -- Pyright Config (F0.4)

Findings:

- Existing `pyrightconfig.json`:

```json
{
  "exclude": [
    "checkpoints",
    "results",
    ".vscode",
    ".git",
    "playground",
    "scripts/debug",
    "eval/debug_logs",
    "playground",
    "cogact.egg-info",
    "eval"
  ],
  "typeCheckingMode": "off"
}
```

- This is explicitly not suitable for GenesisVLA strict typing.
- `genesisvla/` does not exist yet.

Recommendation:

- Add a separate `pyrightconfig.genesisvla.json`.
- Do not change the legacy `pyrightconfig.json` in M0.
- Scope the strict config to new GenesisVLA paths and meta tests only.

Minimal config shape:

```json
{
  "include": [
    "genesisvla",
    "tests/meta"
  ],
  "exclude": [
    "**/__pycache__",
    ".git",
    "runs",
    "datasets",
    "playground",
    "results",
    "checkpoints",
    "starVLA",
    "examples",
    "eval"
  ],
  "typeCheckingMode": "strict",
  "pythonVersion": "3.10"
}
```

Directory question:

- Because the Definition of Done says strict typing is active for new directories, M0 should create minimal package stubs:

```text
genesisvla/__init__.py
genesisvla/core/__init__.py
genesisvla/config/__init__.py
genesisvla/py.typed
```

- These stubs should not implement real platform behavior. Their purpose is to make strict typing and CI meaningful.

## 4. Topic C -- Pre-Commit Config (F0.5)

Findings:

- `.pre-commit-config.yaml` does not exist.
- `pyproject.toml` includes dev dependencies for `pre-commit`, `black`, and `ruff`.
- Existing Black/Ruff global settings use line length 121.

Recommendation:

- Add a repo-root `.pre-commit-config.yaml` rather than a separate hidden GenesisVLA config.
- Restrict M0 hooks to GenesisVLA-owned paths to avoid legacy StarVLA backlog:

```text
files: ^(genesisvla/|tests/meta/)
```

- Hooks that matter most for M0:
  - Ruff for lint/import checks on new Python files.
  - Black for formatting on new Python files.
  - A local `make genesis-check` hook or equivalent custom hook for policy tests.

Pyright placement:

- Pyright should be run by `make genesis-check` and CI.
- It can also be added as a local pre-commit hook, but only if PLAN accounts for local dependency availability.

## 5. Topic D -- CI Setup (F0.6)

Findings:

- `.github/workflows/` does not exist.
- `.github/` contains only `CODEOWNERS` and `PULL_REQUEST_TEMPLATE.md`.
- No existing StarVLA CI workflow needs to be modified.

Recommendation:

- Add a new workflow file, e.g. `.github/workflows/genesisvla.yml`.
- The workflow should run `make genesis-check`.
- Trigger on PR/push path filters for M0-owned files:
  - `genesisvla/**`
  - `tests/meta/**`
  - `docs/genesisvla/**`
  - `pyrightconfig.genesisvla.json`
  - `Makefile`
  - `.pre-commit-config.yaml`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.github/workflows/genesisvla.yml`

Handling absent `genesisvla/core` and `genesisvla/config`:

- Prefer creating minimal stubs in M0 instead of making CI silently pass on absent directories.
- If Claude rejects source stubs in M0, CI must guard absence explicitly, but that weakens the DoD for strict typing.

Minimal M0 CI:

```text
checkout
setup-python 3.10
install black ruff pytest pyright
make genesis-check
```

This keeps GenesisVLA CI independent of StarVLA runtime dependencies and avoids the legacy full-repo lint backlog.

## 6. Topic E -- Branch Policy And PR Template (F0.7)

Findings:

- `.github/PULL_REQUEST_TEMPLATE.md` exists and is StarVLA-oriented.
- `.github/pull_request_template.md` does not exist.
- Existing PR template has a Testing section but no `make genesis-check` requirement.
- `docs/branching_strategy.md` exists and is StarVLA-specific:
  - branch from `starVLA_dev`;
  - target PRs to `starVLA_dev`;
  - full-repo `make check` expected to fail due historical backlog.
- Repository governance for agent work requires `dev/*` branches and no remote push/PR without user authorization.

Recommendation:

- Update the existing uppercase `.github/PULL_REQUEST_TEMPLATE.md`; do not add a duplicate lowercase file.
- Add a GenesisVLA-specific section requiring:
  - test plan;
  - `make genesis-check` result;
  - changed-path scope;
  - confirmation that legacy StarVLA backlog is not used as a reason to skip GenesisVLA checks.
- For branch policy, avoid rewriting StarVLA `docs/branching_strategy.md` in M0 unless Claude explicitly wants to modify upstream-facing docs.
- Prefer a GenesisVLA branch policy section in `docs/genesisvla/coding_standard.md` or a dedicated `docs/genesisvla/branch_policy.md`.

Minimum GenesisVLA PR template content:

```text
## GenesisVLA Test Plan
- [ ] `make genesis-check` passes
- [ ] Added or updated tests first for changed behavior
- [ ] Existing StarVLA backlog is not part of this change
- [ ] No datasets, checkpoints, secrets, or run artifacts included
```

## 7. Topic F -- TDD First Principle

Findings:

- `tests/` exists.
- `tests/meta/` does not exist.
- No Python tests currently exist.
- `tests/README.md` says project-specific tests may live under `tests/` when the actual layout has no better location.

Recommendation:

- Use `tests/meta/test_repo_policy.py`.
- Write these tests first in EXECUTE, run them to show red, then implement M0 artifacts and run green.
- One serial write-capable worker can do this while preserving TDD evidence, as long as the EXECUTE report records red-green output.

Recommended test content:

- `should_have_genesisvla_docs`
  - Assert `docs/genesisvla/rfc_000_architecture.md`, `coding_standard.md`, and `testing_standard.md` exist.
  - Assert each contains non-placeholder GenesisVLA-specific text.

- `should_have_make_genesis_check`
  - Assert `Makefile` contains a `genesis-check` target.
  - Optionally run `make -n genesis-check` or parse the target to avoid executing tools during this meta test.

- `should_have_pyright_strict_config`
  - Assert `pyrightconfig.genesisvla.json` exists.
  - Assert `typeCheckingMode` is `strict`, `pythonVersion` is `3.10`, and includes `genesisvla`.

- `should_have_pr_template_with_test_plan`
  - Accept `.github/PULL_REQUEST_TEMPLATE.md` as the existing canonical template.
  - Assert it contains `make genesis-check` and a test-plan checklist.

## 8. Topic G -- `make genesis-check` Target

Findings:

- `Makefile` exists.
- Existing targets:
  - `help`
  - `clean`
  - `check`
  - `autoformat`
- Existing `check` runs full-repo Black and Ruff:

```make
check:
	black --check .
	ruff check --show-source .
```

- Existing StarVLA docs say full-repo `make check` is expected to fail because of historical lint backlog.

Recommendation:

- Add `genesis-check` as a new Makefile target, not a standalone script.
- Do not modify the existing `check` target in M0.
- `genesis-check` should be scoped to GenesisVLA-owned paths:

```text
black --check genesisvla tests/meta
ruff check genesisvla tests/meta
pyright -p pyrightconfig.genesisvla.json
pytest tests/meta/test_repo_policy.py
```

- If PLAN includes doc-only artifacts and no package stubs, `genesis-check` must either guard missing `genesisvla/` or run only meta tests. This is weaker than the blueprint DoD, so stubs are recommended.

Meaning of "green" for M0:

- M0 green means `make genesis-check` passes on:
  - the meta policy tests;
  - strict pyright config against new GenesisVLA stubs;
  - Black/Ruff on new GenesisVLA and meta-test Python files.
- It does not mean full StarVLA repo lint/type/test passes.
- It does not require Slurm or GPU evidence.

## 9. Decisions Made During DISCUSS

- `docs/genesisvla/` is the correct documentation location for F0.1-F0.3.
- M0 docs should be minimal but real contract documents, not empty placeholders.
- `pyrightconfig.genesisvla.json` should be separate from existing `pyrightconfig.json`.
- Existing legacy `pyrightconfig.json` should remain unchanged during M0.
- Pre-commit should be root-level and path-scoped to GenesisVLA/meta-test files.
- GenesisVLA CI should be a new workflow file, because no workflows exist yet.
- `tests/meta/test_repo_policy.py` is the correct TDD location.
- TDD red-green evidence should be required in EXECUTE.
- `genesis-check` should be a new Make target and should not replace existing `make check`.
- Existing uppercase `.github/PULL_REQUEST_TEMPLATE.md` should be updated rather than adding a duplicate lowercase template.
- M0 should avoid changing StarVLA baseline docs unless needed; GenesisVLA-specific branch/policy material should live under `docs/genesisvla/`.

## 10. Open Questions For Claude

1. Should M0 EXECUTE create minimal `genesisvla/` stubs (`__init__.py`, `core/__init__.py`, `config/__init__.py`, `py.typed`) so pyright strict mode and CI have real new directories?

   Recommendation: yes.

2. Should F0.7 branch policy be a dedicated file `docs/genesisvla/branch_policy.md`, or a section inside `docs/genesisvla/coding_standard.md`?

   Recommendation: section inside `coding_standard.md` for M0, unless Claude wants a distinct branch-policy artifact.

3. Should M0 update `pyproject.toml` dev dependencies to add `pytest` and `pyright`, or should CI install them directly without changing project metadata?

   Recommendation: add them to the `dev` optional dependency group if Claude wants local `make genesis-check` to be reproducible from project metadata; otherwise install directly in CI for minimal scope.

4. Should `genesis-check` run Black/Ruff with blueprint line length 100 even though existing StarVLA `pyproject.toml` uses 121?

   Recommendation: yes for GenesisVLA paths, with explicit command args or GenesisVLA-specific configuration.

## 11. Risks

- Scope creep: M0 can become a broad architecture implementation. Keep it to docs, meta tests, strict config, package stubs, Make target, pre-commit, CI, and PR template.
- Legacy backlog contamination: full-repo `make check` is known to be unsafe as a GenesisVLA gate. `genesis-check` must remain scoped.
- Absent `genesisvla/` dirs: strict pyright config may be meaningless or fail ambiguously unless minimal stubs are created.
- Case-sensitive PR template path: existing template is uppercase. Tests should accept/update `.github/PULL_REQUEST_TEMPLATE.md` rather than create a duplicate lowercase file.
- Dependency availability: local `make genesis-check` will require `pytest` and `pyright`; PLAN must specify whether to add metadata deps or rely on CI install steps.
- Pre-commit overreach: unscoped hooks could reformat or lint legacy StarVLA paths. Hooks must use path filters.
- Governance overlay boundary: M0 should not publish local `.agent-docs/` or Teamwork state.

## 12. M0 PLAN Scope Recommendation

Recommended in-scope implementation artifacts for M0 PLAN:

```text
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/coding_standard.md
docs/genesisvla/testing_standard.md
tests/meta/test_repo_policy.py
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
.github/PULL_REQUEST_TEMPLATE.md
Makefile
```

Recommended optional/stub artifacts, pending Claude confirmation:

```text
genesisvla/__init__.py
genesisvla/core/__init__.py
genesisvla/config/__init__.py
genesisvla/py.typed
```

Potential metadata dependency artifact, pending Claude confirmation:

```text
pyproject.toml
```

Recommended EXECUTE approach:

- One serial `coding_integration_engineer` worker.
- Write `tests/meta/test_repo_policy.py` first and capture failing output.
- Implement minimal docs/configs/gates.
- Run `make genesis-check` and capture green output.
- Run a focused review for scope, baseline protection, and StarVLA backlog isolation.

Out of scope for M0:

- Real model/data/runner/deployment implementation.
- Modifying StarVLA source paths.
- Running Slurm jobs.
- Full-repo `make check` acceptance.
- Dataset, checkpoint, robot, endpoint, or remote-service work.
- Commit, push, PR creation, or remote publication.

## 13. Recommended Next Stage Action

Recommend `start_plan`.

The PLAN should resolve the four Claude questions above, then produce a concrete implementation plan with:

- exact file list and write scopes;
- TDD red-green sequence;
- worker plan;
- validation commands;
- rollback notes;
- acceptance criteria for `make genesis-check` green and strict pyright scope.

Do not advance to EXECUTE until Claude reviews and approves the PLAN.

## 14. Files Affected

- `.agent-docs/teamwork/reports/M0/DISCUSS.md` (written)

No source code, docs, tests, configs, CI files, scripts, datasets, Slurm files, or StarVLA baseline paths were modified during DISCUSS.

===HANDOFF===
Completed:
- Read required governance, blueprint, Teamwork, repository layout, and quality-gate baseline files.
- Ran read-only investigation over docs, pyright config, pre-commit, CI, Makefile, tests, PR template, and GenesisVLA package presence.
- Answered M0 discussion topics A-G.
- Identified decisions, Claude open questions, risks, and PLAN scope recommendation.
- Wrote `.agent-docs/teamwork/reports/M0/DISCUSS.md`.

Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- PLAN must decide whether to create minimal `genesisvla/` stubs and whether to add `pytest`/`pyright` to project dev dependencies.
- PLAN must define the approved worker plan and TDD red-green validation sequence.

Decisions:
- Use `docs/genesisvla/` for GenesisVLA RFC and standards docs.
- Keep M0 quality gates scoped to GenesisVLA/new meta-test paths, not legacy StarVLA backlog.
- Add a new `genesis-check` Make target rather than changing existing `make check`.
- Add a new GenesisVLA CI workflow rather than modifying nonexistent legacy workflows.
- Update existing `.github/PULL_REQUEST_TEMPLATE.md` rather than creating a duplicate lowercase template.

Files Affected:
- `.agent-docs/teamwork/reports/M0/DISCUSS.md` (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
