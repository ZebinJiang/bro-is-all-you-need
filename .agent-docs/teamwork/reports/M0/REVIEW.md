# M0 REVIEW -- GenesisVLA RFC 与质量闸门

Date: 2026-06-18
Stage: REVIEW
Manager: Codex
Milestone: M0

## 1. Stage Summary

M0 progressed through all supervised stages:

- `DISCUSS`: clarified F0.1-F0.7 scope, doc placement, strict type config, pre-commit, CI, PR template, TDD order, and `make genesis-check`.
- `PLAN`: produced a reviewable implementation plan with exactly one serial `coding_integration_engineer` worker.
- `EXECUTE`: created M0 artifacts, captured TDD red/green evidence, and found a Black multi-path timeout in Manager validation.
- `VERIFY`: applied the authorized `.gitignore` exception for `docs/genesisvla/**/*.md`, re-ran checks, and recommended `request_fixes` because V3 still failed on Black directory checks.
- `REVIEW`: applied Claude's authorized `--workers 1` Makefile patch and synchronized the meta policy test expectation.

No worker was dispatched during REVIEW. All edits were Manager inline and scoped to Claude's authorized writable paths.

## 2. Authorized REVIEW Edits

### Edit 1 -- `Makefile`

Before:

```make
genesis-check:
	black --check --line-length 100 genesisvla tests/meta
	ruff check --config 'line-length=100' genesisvla tests/meta
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py -v
```

After:

```make
genesis-check:
	black --check --line-length 100 --workers 1 genesisvla tests/meta
	ruff check --config 'line-length=100' genesisvla tests/meta
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py -v
```

Post-edit line evidence:

```text
    25	.PHONY: genesis-check
    26
    27	genesis-check:
    28		black --check --line-length 100 --workers 1 genesisvla tests/meta
    29		ruff check --config 'line-length=100' genesisvla tests/meta
    30		pyright -p pyrightconfig.genesisvla.json
    31		pytest tests/meta/test_repo_policy.py -v
```

No existing `help`, `clean`, `check`, or `autoformat` target line was modified in REVIEW.

### Edit 2 -- `tests/meta/test_repo_policy.py`

Before:

```python
required_fragments = (
    "black --check --line-length 100 genesisvla tests/meta",
    "ruff check --config 'line-length=100' genesisvla tests/meta",
    "pyright -p pyrightconfig.genesisvla.json",
    "pytest tests/meta/test_repo_policy.py -v",
)
```

After:

```python
required_fragments = (
    "black --check --line-length 100 --workers 1 genesisvla tests/meta",
    "ruff check --config 'line-length=100' genesisvla tests/meta",
    "pyright -p pyrightconfig.genesisvla.json",
    "pytest tests/meta/test_repo_policy.py -v",
)
```

Post-edit line evidence:

```text
    52	def test_should_have_make_genesis_check() -> None:
    53	    makefile = repo_root() / "Makefile"
    54	    text = read_text(makefile)
    55
    56	    assert "\ngenesis-check:\n" in f"\n{text}"
    57	    required_fragments = (
    58	        "black --check --line-length 100 --workers 1 genesisvla tests/meta",
    59	        "ruff check --config 'line-length=100' genesisvla tests/meta",
    60	        "pyright -p pyrightconfig.genesisvla.json",
    61	        "pytest tests/meta/test_repo_policy.py -v",
    62	    )
```

Only the Black expected fragment string was changed.

## 3. V2 Post-Fix -- Meta Policy Tests

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/meta/test_repo_policy.py -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 4 items

tests/meta/test_repo_policy.py::test_should_have_genesisvla_docs PASSED  [ 25%]
tests/meta/test_repo_policy.py::test_should_have_make_genesis_check PASSED [ 50%]
tests/meta/test_repo_policy.py::test_should_have_pyright_strict_config PASSED [ 75%]
tests/meta/test_repo_policy.py::test_should_have_pr_template_with_test_plan PASSED [100%]

============================== 4 passed in 0.02s ===============================
```

Result: `PASS`.

## 4. V3 Post-Fix -- `make genesis-check`

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s make genesis-check
```

Output:

```text
black --check --line-length 100 --workers 1 genesisvla tests/meta
Aborted!
Aborted!
All done! ✨ 🍰 ✨
5 files would be left unchanged.
```

Exit code: `124`.

Result: `FAIL`.

Additional diagnostic:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH black --version
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 --workers 1 tests/meta/test_repo_policy.py
```

Output:

```text
black, 24.2.0 (compiled: no)
Python (CPython) 3.12.13
All done! ✨ 🍰 ✨
1 file would be left unchanged.
single_policy_exit=0
```

Interpretation:

- The authorized `--workers 1` patch was applied exactly.
- The aggregate `make genesis-check` still timed out in this local `/tmp/vla-flywheel-m0-tools` Black environment.
- Single-file Black still passes, and V2 policy tests pass.
- This REVIEW cannot recommend `accept_m0` because the required V3 post-fix command did not exit 0.

## 5. V5 Post-Fix -- Path Boundary

Command:

```bash
git status --short
```

Output:

```text
 M .github/PULL_REQUEST_TEMPLATE.md
 M .gitignore
 M Makefile
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/data_config.py
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/modality.json
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/model2bench_interface.py
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/run_train.sh
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/training_config.yaml
 M pyproject.toml
?? .github/workflows/
?? .pre-commit-config.yaml
?? docs/genesisvla/
?? genesisvla/
?? pyrightconfig.genesisvla.json
?? scripts/
?? tests/
```

Command:

```bash
git status --short --untracked-files=all Makefile tests/meta/test_repo_policy.py .gitignore docs/genesisvla
```

Output:

```text
 M .gitignore
 M Makefile
?? docs/genesisvla/coding_standard.md
?? docs/genesisvla/rfc_000_architecture.md
?? docs/genesisvla/testing_standard.md
?? tests/meta/test_repo_policy.py
```

Command:

```bash
git diff --name-only HEAD
```

Output:

```text
.github/PULL_REQUEST_TEMPLATE.md
.gitignore
Makefile
docs/agent_skills/integrate-starvla-dataset/assets/templates/data_config.py
docs/agent_skills/integrate-starvla-dataset/assets/templates/modality.json
docs/agent_skills/integrate-starvla-dataset/assets/templates/model2bench_interface.py
docs/agent_skills/integrate-starvla-dataset/assets/templates/run_train.sh
docs/agent_skills/integrate-starvla-dataset/assets/templates/training_config.yaml
pyproject.toml
```

Result: `PASS_WITH_NOTES`.

REVIEW-introduced implementation-path changes:

- `Makefile`: one authorized `--workers 1` addition in the `genesis-check` Black command.
- `tests/meta/test_repo_policy.py`: one authorized expected-fragment string update.

Other visible dirty paths:

- M0 EXECUTE artifacts: `.github/PULL_REQUEST_TEMPLATE.md`, `pyproject.toml`, `.github/workflows/`, `.pre-commit-config.yaml`, `docs/genesisvla/`, `genesisvla/`, `pyrightconfig.genesisvla.json`, `tests/`.
- M0 VERIFY artifact: `.gitignore` docs negation line, plus pre-existing unrelated `.gitignore` hunks.
- Pre-existing unrelated dirty paths: `docs/agent_skills/integrate-starvla-dataset/assets/templates/*` deletions.
- P0 artifact remains untracked under `scripts/`.

No StarVLA source, dataset, Slurm, checkpoint, robot, push/PR, or completion-state source changes were introduced in REVIEW.

## 6. Final M0 Deliverables

| Feature | Path(s) |
| --- | --- |
| F0.1 Architecture RFC | `docs/genesisvla/rfc_000_architecture.md` |
| F0.2 Coding standard | `docs/genesisvla/coding_standard.md` |
| F0.3 Testing standard | `docs/genesisvla/testing_standard.md` |
| F0.4 Strict Pyright config | `pyrightconfig.genesisvla.json` |
| F0.5 Path-scoped pre-commit | `.pre-commit-config.yaml` |
| F0.6 GenesisVLA CI | `.github/workflows/genesisvla.yml`, `Makefile` `genesis-check` |
| F0.7 Branch policy and PR template | `docs/genesisvla/coding_standard.md`, `.github/PULL_REQUEST_TEMPLATE.md` |
| TDD meta tests | `tests/meta/test_repo_policy.py`, `tests/meta/__init__.py` |
| Minimal strict package targets | `genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py`, `genesisvla/py.typed` |
| Docs reviewability patch | `.gitignore` negation `!docs/genesisvla/**/*.md` |

## 7. Teamwork State Updates

Updated:

- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/teamwork/workspace/task-board.md`

State recorded:

- M0 `DISCUSS`, `PLAN`, `EXECUTE`, `VERIFY`, and `REVIEW` are complete from Codex's side.
- Acceptance is not recommended yet because V3 still fails locally after the authorized patch.
- Next actor is Claude.

## 8. Residual Risks

1. **V3 still fails in this environment.**
   - `make genesis-check` still exits `124` at Black even with `--workers 1`.
   - The current Black tool is `black, 24.2.0 (compiled: no)` under `/tmp/vla-flywheel-m0-tools` on Python 3.12.13.
   - Single-file Black checks pass; policy tests pass.

2. **The validation tool environment is temporary.**
   - Evidence depends on `/tmp/vla-flywheel-m0-tools`.
   - A durable project-local environment may behave differently, but that was outside REVIEW scope.

3. **Pre-existing workspace dirt remains.**
   - Existing `.gitignore` hunks unrelated to the GenesisVLA docs negation remain dirty.
   - Existing `docs/agent_skills/...` deletions remain dirty.
   - P0 wrapper under `scripts/teamwork/dispatch_codex_manager.py` remains untracked.

4. **M0 docs are now visible but not staged.**
   - `docs/genesisvla/*.md` show as untracked after the authorized `.gitignore` patch.
   - This is the desired reviewable state but still requires future staging/commit if Claude/user chooses to publish M0.

## 9. Rollback Notes

Review-only rollback for this stage:

```bash
git restore -- Makefile
git restore -- tests/meta/test_repo_policy.py  # only after tests/meta is tracked; otherwise edit/remove manually
```

Full M0 rollback remains the PLAN rollback:

```bash
rm -rf docs/genesisvla
rm -rf tests/meta
rm -rf genesisvla
rm -f pyrightconfig.genesisvla.json
rm -f .pre-commit-config.yaml
rm -f .github/workflows/genesisvla.yml
rmdir .github/workflows 2>/dev/null || true
git restore -- Makefile pyproject.toml .github/PULL_REQUEST_TEMPLATE.md
```

Do not roll back pre-existing unrelated dirty paths unless explicitly requested.

## 10. Acceptance Recommendation

Recommendation: `request_fixes`.

Reason:

- M0 deliverables exist and most checks pass.
- The authorized REVIEW patch was applied exactly.
- V2 passes with 4 tests.
- V5 path boundary is acceptable with known pre-existing dirty paths.
- V3 still fails because `make genesis-check` exits `124` after the `--workers 1` patch.

M0 is not ready for Codex to recommend Claude mark complete until V3 either exits 0 in the required environment or Claude explicitly accepts the remaining Black timeout as non-blocking.

===HANDOFF===
Completed:
- Applied Claude's authorized Makefile `--workers 1` patch.
- Updated `tests/meta/test_repo_policy.py` expected Black fragment to match the patched Makefile.
- Re-ran V2 and V3 post-fix.
- Re-ran V5 path-boundary check.
- Updated `.agent-docs/teamwork/roadmap_progress.md` and `.agent-docs/teamwork/workspace/task-board.md`.
- Wrote `.agent-docs/teamwork/reports/M0/REVIEW.md`.

Pending:
- Claude final M0 acceptance and next-milestone selection.
- Claude decision on another scoped fix or non-blocking acceptance for the Black directory-check timeout.

Decisions:
- No worker was dispatched in REVIEW.
- The authorized patch did not make V3 pass in this local `/tmp` tool environment.
- Acceptance recommendation remains `request_fixes`.

Files Affected:
- .agent-docs/teamwork/reports/M0/REVIEW.md (written)
- Makefile (authorized REVIEW edit applied)
- tests/meta/test_repo_policy.py (authorized REVIEW edit applied)
- .agent-docs/teamwork/roadmap_progress.md (updated)
- .agent-docs/teamwork/workspace/task-board.md (updated)
- .agent-docs/teamwork/next-actor.json (set to Claude)

Next-Actor-Notes:
Returning control to Claude Supervisor. M0 awaiting final acceptance.
Next actor: Claude.
===END HANDOFF===
