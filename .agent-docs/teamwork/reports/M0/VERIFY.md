# M0 VERIFY -- GenesisVLA RFC 与质量闸门

Date: 2026-06-18
Stage: VERIFY
Manager: Codex
Milestone: M0

## 1. Scope

Claude Supervisor approved VERIFY with no worker dispatch. Work performed:

- re-ran V1, V2, V3, and V4;
- applied the single authorized `.gitignore` governance patch;
- re-ran V5 and V6 against the final state;
- wrote this VERIFY report and returned control to Claude.

Manager-only edit authorized and applied:

```gitignore
!docs/genesisvla/**/*.md
```

No worker was dispatched in VERIFY.

## 2. V1 -- File Existence

Command:

```bash
python - <<'PY'
from pathlib import Path
required = [
    "docs/genesisvla/rfc_000_architecture.md",
    "docs/genesisvla/coding_standard.md",
    "docs/genesisvla/testing_standard.md",
    "pyrightconfig.genesisvla.json",
    ".pre-commit-config.yaml",
    ".github/workflows/genesisvla.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "Makefile",
    "pyproject.toml",
    "tests/meta/__init__.py",
    "tests/meta/test_repo_policy.py",
    "genesisvla/__init__.py",
    "genesisvla/core/__init__.py",
    "genesisvla/config/__init__.py",
    "genesisvla/py.typed",
]
missing = [path for path in required if not Path(path).exists()]
if missing:
    raise SystemExit(f"missing M0 files: {missing}")
print("V1 PASS")
PY
```

Output:

```text
V1 PASS
```

Result: `PASS`.

## 3. V2 -- Meta Policy Tests

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

============================== 4 passed in 0.01s ===============================
```

Result: `PASS`.

## 4. V3 -- `make genesis-check` With Mitigations

### Attempt 1: Aggregate Make Target

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 600s make genesis-check
```

Output:

```text
black --check --line-length 100 genesisvla tests/meta
Aborted!
All done! ✨ 🍰 ✨
5 files would be left unchanged.
```

Exit code: `124`.

Result: aggregate `make genesis-check` timed out at the Black step.

### Attempt 2: Required Individual Fallback Steps

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 120s black --check --line-length 100 genesisvla; echo "black_genesisvla_exit=$?"
```

Output:

```text
Aborted!
All done! ✨ 🍰 ✨
3 files would be left unchanged.
black_genesisvla_exit=124
```

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 120s black --check --line-length 100 tests/meta; echo "black_tests_meta_exit=$?"
```

Output:

```text
Aborted!
Aborted!
All done! ✨ 🍰 ✨
2 files would be left unchanged.
black_tests_meta_exit=124
```

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s ruff check --config 'line-length=100' genesisvla tests/meta; echo "ruff_exit=$?"
```

Output:

```text
All checks passed!
ruff_exit=0
```

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pyright -p pyrightconfig.genesisvla.json; echo "pyright_exit=$?"
```

Output:

```text
0 errors, 0 warnings, 0 informations
pyright_exit=0
```

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pytest tests/meta/test_repo_policy.py -v; echo "pytest_exit=$?"
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

============================== 4 passed in 0.01s ===============================
pytest_exit=0
```

Fallback result:

| Step | Exit Code |
| --- | ---: |
| `black --check --line-length 100 genesisvla` | 124 |
| `black --check --line-length 100 tests/meta` | 124 |
| `ruff check --config 'line-length=100' genesisvla tests/meta` | 0 |
| `pyright -p pyrightconfig.genesisvla.json` | 0 |
| `pytest tests/meta/test_repo_policy.py -v` | 0 |

V3 result by Claude's VERIFY criteria: `FAIL`.

Reason:

- The aggregate target timed out.
- Both required fallback Black directory checks also timed out.
- The timeout output still reported that the files would be left unchanged, but the commands exited `124`.
- Ruff, Pyright, and pytest passed.

Additional supporting Black evidence:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 genesisvla/__init__.py
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 genesisvla/core/__init__.py
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 genesisvla/config/__init__.py
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 tests/meta/__init__.py
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 30s black --check --line-length 100 tests/meta/test_repo_policy.py
```

Output:

```text
All done! ✨ 🍰 ✨
1 file would be left unchanged.
black_file_genesisvla_init_exit=0
All done! ✨ 🍰 ✨
1 file would be left unchanged.
black_file_core_init_exit=0
All done! ✨ 🍰 ✨
1 file would be left unchanged.
black_file_config_init_exit=0
All done! ✨ 🍰 ✨
1 file would be left unchanged.
black_file_tests_init_exit=0
All done! ✨ 🍰 ✨
1 file would be left unchanged.
black_file_policy_exit=0
```

Interpretation:

- The source files are individually Black-clean.
- The current environment still cannot complete Black directory checks within the requested timeout windows.
- Because the specified fallback directory checks returned non-zero, this VERIFY report cannot mark V3 as `PASS_WITH_TOOLING_NOTE`.

## 5. V4 -- Pyright Strict

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pyright -p pyrightconfig.genesisvla.json
```

Output:

```text
0 errors, 0 warnings, 0 informations
```

Result: `PASS`.

## 6. `.gitignore` Governance Patch

Before patch:

```text
   232	**/*.pt
   233	**/*.mp4
   234	**/*.npy
   235	**/*.parquet
   236
   237	*/**/*.md
   238	*/*.md
   239	!examples/**/README.md
```

Applied patch:

```diff
 */**/*.md
+!docs/genesisvla/**/*.md
 */*.md
```

After patch:

```text
   232	**/*.pt
   233	**/*.mp4
   234	**/*.npy
   235	**/*.parquet
   236
   237	*/**/*.md
   238	!docs/genesisvla/**/*.md
   239	*/*.md
   240	!examples/**/README.md
```

Full `git diff -- .gitignore` includes pre-existing dirty changes outside this VERIFY edit. The VERIFY edit itself is the single added line above.

## 7. V5 -- Path Boundary After `.gitignore` Patch

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

Command:

```bash
git status --short --untracked-files=all docs/genesisvla .gitignore
```

Output:

```text
 M .gitignore
?? docs/genesisvla/coding_standard.md
?? docs/genesisvla/rfc_000_architecture.md
?? docs/genesisvla/testing_standard.md
```

`git check-ignore -v` output:

```text
.gitignore:238:!docs/genesisvla/**/*.md	docs/genesisvla/rfc_000_architecture.md
check_ignore_rfc_exit=0
.gitignore:238:!docs/genesisvla/**/*.md	docs/genesisvla/coding_standard.md
check_ignore_coding_exit=0
.gitignore:238:!docs/genesisvla/**/*.md	docs/genesisvla/testing_standard.md
check_ignore_testing_exit=0
```

Note: with `-v`, Git reports the matching negation rule. To confirm the files are not ignored, plain and quiet forms were also run.

Command:

```bash
git check-ignore docs/genesisvla/rfc_000_architecture.md; echo "check_ignore_plain_rfc_exit=$?"
git check-ignore docs/genesisvla/coding_standard.md; echo "check_ignore_plain_coding_exit=$?"
git check-ignore docs/genesisvla/testing_standard.md; echo "check_ignore_plain_testing_exit=$?"
```

Output:

```text
check_ignore_plain_rfc_exit=1
check_ignore_plain_coding_exit=1
check_ignore_plain_testing_exit=1
```

Command:

```bash
git check-ignore -q docs/genesisvla/rfc_000_architecture.md; echo "check_ignore_q_rfc_exit=$?"
git check-ignore -q docs/genesisvla/coding_standard.md; echo "check_ignore_q_coding_exit=$?"
git check-ignore -q docs/genesisvla/testing_standard.md; echo "check_ignore_q_testing_exit=$?"
```

Output:

```text
check_ignore_q_rfc_exit=1
check_ignore_q_coding_exit=1
check_ignore_q_testing_exit=1
```

Command:

```bash
git ls-files --others --exclude-standard docs/genesisvla
```

Output:

```text
docs/genesisvla/coding_standard.md
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/testing_standard.md
```

V5 result: `PASS_WITH_NOTES`.

Notes:

- `docs/genesisvla/` files now appear as untracked and reviewable.
- Plain and quiet `git check-ignore` confirm the docs are not ignored.
- `git check-ignore -v` reports the negation rule itself; this differs from Claude's expected "nothing" output but confirms the active unignore pattern.
- Pre-existing unrelated dirty paths remain and were not reverted.

## 8. V6 -- Manager Inline Review

Commands and outputs:

```text
V6 docstring/stub PASS
V6 pyproject PASS
pyrightconfig_json_exit=0
starvla_diff_exit=0
V6 make/precommit/ci PASS
```

Secret / Slurm / push scan command:

```bash
rg -n "\b(sbatch|srun|git push|gh pr create|create_pull_request|merge_pull_request|BEGIN RSA|BEGIN OPENSSH|api[_-]?key|secret|token)\b" docs/genesisvla genesisvla tests/meta .github/workflows/genesisvla.yml .pre-commit-config.yaml pyrightconfig.genesisvla.json Makefile pyproject.toml .github/PULL_REQUEST_TEMPLATE.md .gitignore || true
```

Output:

```text
.gitignore:142:.*api_key
tests/meta/test_repo_policy.py:20:    for token in banned_tokens:
tests/meta/test_repo_policy.py:21:        assert token not in text, f"{path} contains forbidden token {token!r}"
```

Review result:

- Python files have Chinese module docstrings.
- GenesisVLA stubs contain only module docstrings.
- `genesisvla/py.typed` remains empty.
- No StarVLA source changes exist.
- `pyrightconfig.json` is unchanged.
- Existing `make check` and `autoformat` target bodies are unchanged.
- Global `[tool.black]` and `[tool.ruff]` line lengths remain 121.
- `.pre-commit-config.yaml` remains path-scoped and does not target `starVLA/`.
- CI workflow runs `make genesis-check`, not `make check`.
- No Slurm submission commands, push/PR commands, secrets, datasets, checkpoints, or run artifacts were introduced.
- The `.gitignore` VERIFY edit is the single intended negation line near the Markdown ignore rules. Other `.gitignore` diff hunks were pre-existing before VERIFY and were not modified in this stage.
- No source code was modified during VERIFY; only `.gitignore` and Teamwork report/state were written.

V6 result: `PASS`.

## 9. Final Residual Risks

1. **V3 remains failing under the specified fallback.**
   - `make genesis-check` timed out at Black after 600 seconds.
   - `black --check --line-length 100 genesisvla` and `black --check --line-length 100 tests/meta` each timed out.
   - Single-file Black checks passed, and Ruff/Pyright/pytest passed.
   - This is still most consistent with the Black multi-path/directory validation behavior in this environment, but the VERIFY acceptance rule says any individual fallback failure makes V3 fail.

2. **Validation tools are installed under `/tmp/vla-flywheel-m0-tools`.**
   - The project metadata now includes `pytest` and `pyright`, but the local command evidence depends on the temporary worker venv.
   - A durable project environment setup is still a future operational task.

3. **Pre-existing dirty workspace remains.**
   - `.gitignore` had unrelated dirty edits before VERIFY.
   - `docs/agent_skills/integrate-starvla-dataset/assets/templates/*` deletions remain.
   - `scripts/teamwork/dispatch_codex_manager.py` remains untracked from P0.

4. **`git check-ignore -v` behavior differs from expected text.**
   - It reports the negation rule rather than returning no output.
   - Plain and quiet checks exit 1, and `git status` / `git ls-files --others --exclude-standard` show the docs are no longer ignored.

## 10. Acceptance Recommendation

Recommendation: `request_fixes`.

Rationale:

- M0 artifacts are present.
- TDD policy tests pass.
- Pyright strict passes.
- GenesisVLA docs are now reviewable after the authorized `.gitignore` patch.
- V6 review passes.
- However, V3 cannot be marked `PASS` or `PASS_WITH_TOOLING_NOTE` under the exact VERIFY criteria because the required Black fallback directory checks exit `124`.

Recommended fix scope for Claude:

- Approve a scoped M0 EXECUTE revision to make `make genesis-check` robust in this environment, likely by changing the Black invocation to a form that validates the same files without triggering the multi-path/directory hang, or by approving a known-good project-local tool environment.
- Keep the `.gitignore` negation patch.

===HANDOFF===
Completed:
- Re-ran V1, V2, V3, and V4 independently.
- Applied the authorized `.gitignore` governance patch: `!docs/genesisvla/**/*.md`.
- Confirmed GenesisVLA docs are now visible as untracked files.
- Re-ran V5 and V6 against the final state.
- Wrote `.agent-docs/teamwork/reports/M0/VERIFY.md`.

Pending:
- Claude REVIEW gate decision.
- Claude decision on scoped fixes for V3 Black directory-check timeout.

Decisions:
- No worker was dispatched in VERIFY.
- `.gitignore` was changed only for the authorized GenesisVLA docs negation line during VERIFY.
- V3 is recorded as `FAIL` by the exact VERIFY criteria because required Black fallback checks exited 124.
- Acceptance recommendation is `request_fixes`.

Files Affected:
- .agent-docs/teamwork/reports/M0/VERIFY.md (written)
- .gitignore (authorized governance patch applied)
- .agent-docs/teamwork/next-actor.json (set to Claude)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting REVIEW gate.
Next actor: Claude.
===END HANDOFF===
