# M0 PLAN -- GenesisVLA RFC 与质量闸门

> **For agentic workers:** REQUIRED SUB-SKILL: use the project `feature-dev` / `coding_integration_engineer` path approved by Claude for M0 EXECUTE. This plan is not self-approved; EXECUTE starts only after Claude chooses `approve_execute`.

**Goal:** Establish the first GenesisVLA governance and quality gate layer: RFC docs, standards, strict type config, path-scoped pre-commit, GenesisVLA CI, PR template requirements, and a green `make genesis-check`.

**Architecture:** M0 adds a small GenesisVLA-native documentation/tooling slice without touching StarVLA source. It introduces minimal `genesisvla/` package stubs only so strict pyright and CI have real targets. All quality checks are scoped to GenesisVLA-owned paths and `tests/meta/` so historical StarVLA lint/type backlog does not block GenesisVLA development.

**Tech Stack:** Markdown, Make, pytest, pyright, Black, Ruff, pre-commit, GitHub Actions.

---

## 1. Confirmed Claude Decisions

1. **Q1 — Minimal `genesisvla/` stubs**: **YES**. EXECUTE creates `genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py`, and `genesisvla/py.typed`. No real platform behavior; the stubs exist so pyright strict and CI have actual targets.

2. **Q2 — F0.7 branch policy location**: **Section inside `docs/genesisvla/coding_standard.md`**. Do not create a separate `branch_policy.md` in M0.

3. **Q3 — `pyproject.toml` dev deps**: **YES — add `pytest` and `pyright` to `[project.optional-dependencies].dev`**. This makes `make genesis-check` reproducible from project metadata. Do not change existing dev deps (`black`, `ruff`, `pre-commit`).

4. **Q4 — Line length 100 for GenesisVLA**: **YES — enforce 100 only on GenesisVLA paths via explicit command args (`--line-length 100` for black, `--line-length 100` for ruff via `--config`/per-call)**. Do not modify the global `[tool.black]`/`[tool.ruff]` line length (121) in `pyproject.toml`.

   Implementation note: ruff supports per-call config via `--config 'line-length=100'`. Black supports `--line-length 100` directly. If a per-directory pyproject sub-config is cleaner, the PLAN may propose it instead — Claude will review the choice in PLAN, not auto-approve a deviation.

5. **TDD red-green required**: EXECUTE must capture the red output of `tests/meta/test_repo_policy.py` before creating M0 artifacts, then capture the green output after. Both must appear in `EXECUTE.md`.

6. **Wrapper-mediated dispatch**: All Codex Manager dispatch from M0 onwards uses `scripts/teamwork/dispatch_codex_manager.py`.

## 2. In Scope Vs Out Of Scope

EXECUTE may write only these paths:

```text
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/coding_standard.md
docs/genesisvla/testing_standard.md
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
.github/PULL_REQUEST_TEMPLATE.md
Makefile
pyproject.toml
tests/meta/__init__.py
tests/meta/test_repo_policy.py
genesisvla/__init__.py
genesisvla/core/__init__.py
genesisvla/config/__init__.py
genesisvla/py.typed
```

EXECUTE must not touch these paths or path families:

```text
starVLA/
pyrightconfig.json
Makefile existing check target body
pyproject.toml global [tool.black] settings
pyproject.toml global [tool.ruff] settings
datasets/
runs/
configs/slurm/
code-input/
related-assets/
.agents/
.codex/
docs/branching_strategy.md
docs/CONTRIBUTING.md
docs/PR_readme.md
docs/starVLA_guideline.md
docs/model_zoo.md
docs/faq.md
docs/WM4A.md
assets/input/
checkpoints/
playground/
results/
deployment/
examples/
eval/
```

Out-of-scope behavior:

- No StarVLA source edits.
- No real platform implementation beyond empty package stubs.
- No dataset, checkpoint, Slurm, robot, endpoint, credential, or external-service work.
- No full-repo `make check` acceptance.
- No commits, pushes, PR creation, branch publication, or remote operations.
- No `passes: true`, milestone completion, or progress acceptance updates.

## 3. TDD Red-Green Sequence

EXECUTE must follow this order exactly.

### Step T1 -- Create failing meta tests first

Create:

```text
tests/meta/__init__.py
tests/meta/test_repo_policy.py
```

`tests/meta/__init__.py` should contain only a concise Chinese module docstring, for example:

```python
"""GenesisVLA 仓库级策略测试包。"""
```

`tests/meta/test_repo_policy.py` must contain exactly four policy tests with these names:

```python
def test_should_have_genesisvla_docs() -> None: ...
def test_should_have_make_genesis_check() -> None: ...
def test_should_have_pyright_strict_config() -> None: ...
def test_should_have_pr_template_with_test_plan() -> None: ...
```

Each test should use `pathlib.Path` and standard-library `json` only where needed.

Assertions:

- `test_should_have_genesisvla_docs`
  - Requires:
    - `docs/genesisvla/rfc_000_architecture.md`
    - `docs/genesisvla/coding_standard.md`
    - `docs/genesisvla/testing_standard.md`
  - Asserts each file exists.
  - Asserts each file contains `GenesisVLA`.
  - Asserts no file contains placeholder tokens: `TODO`, `TBD`, `placeholder`, `lorem`.
  - Asserts architecture RFC contains `StarVLA`, `seven-layer`, and `make genesis-check`.
  - Asserts coding standard contains `Branch Policy`, `Pyright`, `Ruff`, `Black`, `Chinese docstrings`, and `100`.
  - Asserts testing standard contains `TDD-first`, `make genesis-check`, and `StarVLA backlog`.

- `test_should_have_make_genesis_check`
  - Requires `Makefile`.
  - Asserts it contains a standalone `genesis-check:` target.
  - Asserts it contains these command fragments:
    - `black --check --line-length 100 genesisvla tests/meta`
    - `ruff check --config 'line-length=100' genesisvla tests/meta`
    - `pyright -p pyrightconfig.genesisvla.json`
    - `pytest tests/meta/test_repo_policy.py -v`
  - Asserts the existing `check:` target text still contains `black --check .` and `ruff check --show-source .`.

- `test_should_have_pyright_strict_config`
  - Requires `pyrightconfig.genesisvla.json`.
  - Parses JSON.
  - Asserts `typeCheckingMode == "strict"`.
  - Asserts `pythonVersion == "3.10"`.
  - Asserts `include` contains `genesisvla`, `genesisvla/core`, `genesisvla/config`, and `tests/meta`.
  - Asserts `exclude` contains `starVLA`, `datasets`, `runs`, `playground`, `results`, `checkpoints`, `examples`, and `eval`.

- `test_should_have_pr_template_with_test_plan`
  - Requires `.github/PULL_REQUEST_TEMPLATE.md`.
  - Asserts it contains `GenesisVLA Test Plan`.
  - Asserts it contains ``make genesis-check``.
  - Asserts it contains `tests first`.
  - Asserts it contains `StarVLA backlog`.
  - Asserts it contains `No datasets, checkpoints, secrets, or run artifacts`.

### Step T2 -- Run red test

Run:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected result:

```text
4 failed
```

Expected failure causes:

- GenesisVLA docs do not exist.
- `genesis-check` Make target does not exist.
- `pyrightconfig.genesisvla.json` does not exist.
- PR template lacks GenesisVLA test-plan section.

EXECUTE must capture the full red output in `.agent-docs/teamwork/reports/M0/EXECUTE.md`.

### Step T3 -- Create M0 artifacts

Create or update the in-scope files only:

- docs
- pyright config
- pre-commit config
- CI workflow
- PR template section
- Makefile `genesis-check`
- `pyproject.toml` dev deps
- minimal `genesisvla/` stubs

### Step T4 -- Run green meta test

Run:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected result:

```text
4 passed
```

EXECUTE must capture the full green output in `EXECUTE.md`.

### Step T5 -- Run full M0 gate

Run:

```bash
make genesis-check
```

Expected result:

```text
black --check --line-length 100 genesisvla tests/meta
ruff check --config 'line-length=100' genesisvla tests/meta
pyright -p pyrightconfig.genesisvla.json
pytest tests/meta/test_repo_policy.py -v
4 passed
```

Exact tool phrasing may vary, but exit code must be 0 and the output must show Black, Ruff, Pyright, and pytest all ran.

## 4. Implementation Tasks

### Task 1 -- Add TDD Meta Policy Tests

Target files:

- Create `tests/meta/__init__.py`
- Create `tests/meta/test_repo_policy.py`

Steps:

1. Create `tests/meta/`.
2. Add Chinese module docstrings to both Python files.
3. Add helper functions:
   - `repo_root() -> Path`
   - `read_text(path: Path) -> str`
   - `assert_no_placeholders(text: str, path: Path) -> None`
4. Add the four tests listed in Section 3.

Expected local check:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected result before implementation artifacts:

```text
4 failed
```

The worker must stop and record the red output before creating later artifacts.

### Task 2 -- Create GenesisVLA Documentation Contracts

Target files:

- Create `docs/genesisvla/rfc_000_architecture.md`
- Create `docs/genesisvla/coding_standard.md`
- Create `docs/genesisvla/testing_standard.md`

Steps:

1. Create `docs/genesisvla/`.
2. Write the three docs using the outlines in Section 5.
3. Keep docs in English unless quoting blueprint terms.
4. Include the exact policy phrases required by tests:
   - `GenesisVLA`
   - `StarVLA`
   - `seven-layer`
   - `make genesis-check`
   - `Branch Policy`
   - `Chinese docstrings`
   - `TDD-first`
   - `StarVLA backlog`
5. Avoid placeholders: no `TODO`, `TBD`, `placeholder`, or `lorem`.

Expected local check:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected result after this task only:

- `test_should_have_genesisvla_docs` passes.
- Other tests may still fail until later tasks are complete.

### Task 3 -- Add Minimal GenesisVLA Package Stubs

Target files:

- Create `genesisvla/__init__.py`
- Create `genesisvla/core/__init__.py`
- Create `genesisvla/config/__init__.py`
- Create `genesisvla/py.typed`

Steps:

1. Create `genesisvla/`, `genesisvla/core/`, and `genesisvla/config/`.
2. Add Chinese module docstrings to the three Python files.
3. Do not add platform behavior, imports, classes, or functions.
4. Add empty `genesisvla/py.typed` marker.

Expected local check:

```bash
python -m py_compile genesisvla/__init__.py genesisvla/core/__init__.py genesisvla/config/__init__.py
```

Expected result:

- Exit code 0.

### Task 4 -- Add Strict Pyright Config

Target file:

- Create `pyrightconfig.genesisvla.json`

Steps:

1. Write the JSON shape in Section 6.
2. Do not modify existing `pyrightconfig.json`.

Expected local check:

```bash
python -m json.tool pyrightconfig.genesisvla.json >/dev/null
pytest tests/meta/test_repo_policy.py::test_should_have_pyright_strict_config -v
```

Expected result:

- JSON parse exits 0.
- Pytest target passes.

### Task 5 -- Add `genesis-check` Make Target

Target file:

- Modify `Makefile`

Steps:

1. Append a `.PHONY: genesis-check` declaration.
2. Append a `genesis-check:` target.
3. Do not modify the existing `check:` target body.
4. Use explicit GenesisVLA line-length arguments.

Required added lines:

```make
.PHONY: genesis-check

genesis-check:
	black --check --line-length 100 genesisvla tests/meta
	ruff check --config 'line-length=100' genesisvla tests/meta
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py -v
```

Expected local check:

```bash
pytest tests/meta/test_repo_policy.py::test_should_have_make_genesis_check -v
```

Expected result:

- Test passes.

### Task 6 -- Add M0 Dev Dependencies

Target file:

- Modify `pyproject.toml`

Steps:

1. Add `pytest` and `pyright` to `[project.optional-dependencies].dev`.
2. Preserve existing dev dependencies:
   - `black>=24.2.0`
   - `gpustat`
   - `ipython`
   - `pre-commit`
   - `ruff>=0.2.2`
3. Do not modify global `[tool.black]` line length.
4. Do not modify global `[tool.ruff]` line length.

Required resulting dev dependency list:

```toml
dev = [
    "black>=24.2.0",
    "gpustat",
    "ipython",
    "pre-commit",
    "pytest",
    "pyright",
    "ruff>=0.2.2",
]
```

Expected local check:

```bash
python - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text())
dev = data["project"]["optional-dependencies"]["dev"]
assert "pytest" in dev
assert "pyright" in dev
assert data["tool"]["black"]["line-length"] == 121
assert data["tool"]["ruff"]["line-length"] == 121
PY
```

Expected result:

- Exit code 0.

### Task 7 -- Add Path-Scoped Pre-Commit Config

Target file:

- Create `.pre-commit-config.yaml`

Steps:

1. Use local hooks only.
2. Scope Python hooks to `^(genesisvla/|tests/meta/).*\.py$`.
3. Scope policy/gate hooks to M0-owned paths only.
4. Do not configure hooks over `starVLA/`.

Expected local check:

```bash
python - <<'PY'
from pathlib import Path
text = Path(".pre-commit-config.yaml").read_text()
assert "repo: local" in text
assert "genesis-black" in text
assert "genesis-ruff" in text
assert "genesis-pyright" in text
assert "genesis-policy-tests" in text
assert "starVLA/" not in text
PY
```

Expected result:

- Exit code 0.

### Task 8 -- Add GenesisVLA CI Workflow

Target file:

- Create `.github/workflows/genesisvla.yml`

Steps:

1. Create `.github/workflows/`.
2. Add a single workflow named `GenesisVLA`.
3. Trigger on PR and push path filters listed in Section 6.
4. Use Python 3.10.
5. Install only M0 quality-gate tools.
6. Run `make genesis-check`.

Expected local check:

```bash
python - <<'PY'
from pathlib import Path
text = Path(".github/workflows/genesisvla.yml").read_text()
assert "GenesisVLA" in text
assert "make genesis-check" in text
assert "python-version: '3.10'" in text or 'python-version: \"3.10\"' in text
assert "starVLA/**" not in text
PY
```

Expected result:

- Exit code 0.

### Task 9 -- Update PR Template

Target file:

- Modify `.github/PULL_REQUEST_TEMPLATE.md`

Steps:

1. Add a new section after the existing `## Testing` heading.
2. Do not rename the file.
3. Do not create lowercase `.github/pull_request_template.md`.
4. Keep the existing StarVLA template content intact aside from adding the GenesisVLA section.

Required section:

```markdown
### GenesisVLA Test Plan
- [ ] `make genesis-check` passes
- [ ] Tests were added or updated first for changed behavior
- [ ] Existing StarVLA backlog is not part of this change
- [ ] No datasets, checkpoints, secrets, or run artifacts are included
```

Expected local check:

```bash
pytest tests/meta/test_repo_policy.py::test_should_have_pr_template_with_test_plan -v
```

Expected result:

- Test passes.

### Task 10 -- Run Green Gate And Capture Evidence

Target files:

- No new edits unless required to fix M0 in-scope artifacts.

Steps:

1. Run:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected:

```text
4 passed
```

2. Run:

```bash
make genesis-check
```

Expected:

- Exit code 0.
- Black, Ruff, Pyright, and pytest all run.
- Pytest reports 4 passed.

3. Record both outputs in `EXECUTE.md`.

## 5. Doc Content Outlines

### `docs/genesisvla/rfc_000_architecture.md`

Required sections:

1. `# RFC 000: GenesisVLA Architecture`
2. Metadata table:
   - Status: Accepted for M0 baseline
   - Date: 2026-06-18
   - Scope: governance and architecture contract only
3. `## Summary`
   - State that GenesisVLA is the target platform built on the current StarVLA engineering base.
   - State that M0 does not implement model/data/runner behavior.
4. `## Goals`
   - Establish GenesisVLA identity.
   - Define seven-layer architecture.
   - Create independent quality gate through `make genesis-check`.
5. `## Non-Goals`
   - No model implementation.
   - No dataset execution.
   - No Slurm jobs.
   - No modification of StarVLA baseline paths.
6. `## Relationship To StarVLA`
   - StarVLA remains the current engineering base and legacy baseline.
   - New GenesisVLA code enters `genesisvla/`.
   - `starVLA/` stays untouched during M0.
7. `## Seven-Layer Architecture`
   - Use exact phrase `seven-layer`.
   - List: Core, Config, Data, Model, Runner, Deployment, Acceleration.
   - One sentence per layer.
8. `## Initial Directory Policy`
   - `genesisvla/core` and `genesisvla/config` are initial strict targets.
   - `docs/genesisvla/` owns GenesisVLA RFC and standards.
9. `## Quality Gate`
   - `make genesis-check` is the M0 gate.
   - It is independent from old StarVLA backlog.
10. `## Future RFCs`
   - M1+ will define core contracts and typed config.

### `docs/genesisvla/coding_standard.md`

Required sections:

1. `# GenesisVLA Coding Standard`
2. `## Scope`
   - Applies to `genesisvla/` and GenesisVLA-owned tests/docs.
   - Does not retroactively enforce legacy StarVLA code.
3. `## Python Baseline`
   - Python 3.10.
   - `py.typed` for typed package marker.
4. `## Formatting`
   - Black on GenesisVLA paths.
   - Line length 100 for GenesisVLA only.
   - Existing StarVLA global line length remains 121.
5. `## Linting`
   - Ruff on GenesisVLA paths.
   - No wildcard imports.
   - No library `print`.
6. `## Typing`
   - Pyright strict on `genesisvla/` and `tests/meta`.
   - Avoid `dict[str, Any]` across core boundaries unless explicitly justified.
7. `## Documentation`
   - New or modified Python code uses Chinese docstrings and comments per `AGENTS.md`.
   - Public functions/classes must document purpose, inputs, outputs, and assumptions.
8. `## Runtime Safety`
   - No implicit `.cuda()`.
   - No hidden device transfer inside transform code.
   - No global environment mutation.
9. `## Branch Policy`
   - Use `dev/*` branches for agent-created GenesisVLA work.
   - PRs require `make genesis-check` result.
   - Do not push or create PRs unless the user explicitly asks.
   - Keep StarVLA baseline edits out of GenesisVLA governance PRs unless explicitly scoped.
10. `## Quality Gate`
   - `make genesis-check` must pass before M0 acceptance.

### `docs/genesisvla/testing_standard.md`

Required sections:

1. `# GenesisVLA Testing Standard`
2. `## Scope`
   - Applies to GenesisVLA-native paths and policy tests.
3. `## TDD-First`
   - Include exact phrase `TDD-first`.
   - Tests are written and observed failing before implementation.
4. `## Test Categories`
   - Unit tests.
   - Failure-mode tests.
   - Config validation tests.
   - Smoke tests.
   - Minimal documentation snippets.
5. `## M0 Policy Tests`
   - `tests/meta/test_repo_policy.py`.
   - List the four policy tests.
6. `## Local Gate`
   - `make genesis-check`.
   - It runs Black, Ruff, Pyright, and pytest.
7. `## StarVLA Backlog Isolation`
   - Existing StarVLA backlog does not block GenesisVLA CI.
   - Do not use full-repo `make check` as the M0 acceptance gate.
8. `## Slurm Boundary`
   - CPU/static checks can run locally.
   - Compute-heavy tests require Slurm in later milestones.

## 6. Config Schemas

### `pyrightconfig.genesisvla.json`

Use this full JSON:

```json
{
  "include": [
    "genesisvla",
    "genesisvla/core",
    "genesisvla/config",
    "tests/meta"
  ],
  "exclude": [
    "**/__pycache__",
    ".git",
    "datasets",
    "runs",
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

### `.pre-commit-config.yaml`

Use this exact local-hook shape:

```yaml
repos:
  - repo: local
    hooks:
      - id: genesis-black
        name: GenesisVLA Black
        entry: black --check --line-length 100
        language: system
        files: ^(genesisvla/|tests/meta/).*\.py$
        types_or: [python]
      - id: genesis-ruff
        name: GenesisVLA Ruff
        entry: ruff check --config 'line-length=100'
        language: system
        files: ^(genesisvla/|tests/meta/).*\.py$
        types_or: [python]
      - id: genesis-pyright
        name: GenesisVLA Pyright
        entry: pyright -p pyrightconfig.genesisvla.json
        language: system
        pass_filenames: false
        files: ^(genesisvla/|tests/meta/|pyrightconfig\.genesisvla\.json)
      - id: genesis-policy-tests
        name: GenesisVLA Policy Tests
        entry: pytest tests/meta/test_repo_policy.py -v
        language: system
        pass_filenames: false
        files: ^(docs/genesisvla/|tests/meta/|genesisvla/|pyrightconfig\.genesisvla\.json|Makefile|\.github/PULL_REQUEST_TEMPLATE\.md|\.pre-commit-config\.yaml)
```

### `.github/workflows/genesisvla.yml`

Use this exact workflow shape:

```yaml
name: GenesisVLA

on:
  pull_request:
    paths:
      - "genesisvla/**"
      - "tests/meta/**"
      - "docs/genesisvla/**"
      - "pyrightconfig.genesisvla.json"
      - "Makefile"
      - "pyproject.toml"
      - ".pre-commit-config.yaml"
      - ".github/PULL_REQUEST_TEMPLATE.md"
      - ".github/workflows/genesisvla.yml"
  push:
    paths:
      - "genesisvla/**"
      - "tests/meta/**"
      - "docs/genesisvla/**"
      - "pyrightconfig.genesisvla.json"
      - "Makefile"
      - "pyproject.toml"
      - ".pre-commit-config.yaml"
      - ".github/PULL_REQUEST_TEMPLATE.md"
      - ".github/workflows/genesisvla.yml"

jobs:
  genesis-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - name: Install GenesisVLA gate tools
        run: python -m pip install black ruff pytest pyright
      - name: Run GenesisVLA gate
        run: make genesis-check
```

### `Makefile` additions

Append only this target block; do not change `check:`:

```make
.PHONY: genesis-check

genesis-check:
	black --check --line-length 100 genesisvla tests/meta
	ruff check --config 'line-length=100' genesisvla tests/meta
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py -v
```

### `pyproject.toml` dev dependency addition

Only modify `[project.optional-dependencies].dev` by adding:

```toml
    "pytest",
    "pyright",
```

Do not remove or change:

```toml
    "black>=24.2.0",
    "gpustat",
    "ipython",
    "pre-commit",
    "ruff>=0.2.2",
```

Do not modify:

```toml
[tool.black]
line-length = 121

[tool.ruff]
line-length = 121
```

### PR template addition

Insert this section immediately after the existing `## Testing` heading:

```markdown
### GenesisVLA Test Plan
- [ ] `make genesis-check` passes
- [ ] Tests were added or updated first for changed behavior
- [ ] Existing StarVLA backlog is not part of this change
- [ ] No datasets, checkpoints, secrets, or run artifacts are included
```

## 7. Worker Plan

Claude pre-approves exactly:

```text
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M0 artifacts, run TDD red-green and make genesis-check, capture validation output.
Writable paths: (the whitelist from section 2)
Read-only paths: all others, including starVLA/, datasets/, runs/, secrets, baseline configs.
Stop condition: all in-scope artifacts exist, pytest tests/meta/test_repo_policy.py green, make genesis-check green, worker returns evidence.
Worker must not: launch additional workers, modify out-of-scope files, push, PR, sbatch, set passes=true.
```

Expanded writable-path whitelist:

```text
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/coding_standard.md
docs/genesisvla/testing_standard.md
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
.github/PULL_REQUEST_TEMPLATE.md
Makefile
pyproject.toml
tests/meta/__init__.py
tests/meta/test_repo_policy.py
genesisvla/__init__.py
genesisvla/core/__init__.py
genesisvla/config/__init__.py
genesisvla/py.typed
```

Required worker report content:

- Changed files.
- Red pytest output.
- Green pytest output.
- `make genesis-check` output.
- Any skipped checks and reasons.
- Path-boundary `git status --short`.
- Rollback notes.
- Residual risks.

No parallel workers. No additional workers.

## 8. Validation Plan For VERIFY (V1-V6)

### V1 -- File Existence

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

Expected output:

```text
V1 PASS
```

### V2 -- Meta Policy Tests

Command:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected output:

```text
4 passed
```

Exit code must be 0.

### V3 -- M0 Gate

Command:

```bash
make genesis-check
```

Expected output:

- Black runs on `genesisvla tests/meta`.
- Ruff runs on `genesisvla tests/meta`.
- Pyright runs with `pyrightconfig.genesisvla.json`.
- Pytest reports 4 passed.
- Exit code 0.

### V4 -- Pyright Strict Check

Command:

```bash
pyright -p pyrightconfig.genesisvla.json
```

Expected output:

```text
0 errors
```

Exit code must be 0.

### V5 -- Path-Boundary Git Status

Command:

```bash
git status --short
git diff --name-only HEAD
```

Expected result:

- New/changed M0 paths are limited to the whitelist in Section 2.
- No changes under:
  - `starVLA/`
  - `datasets/`
  - `runs/`
  - `configs/slurm/`
  - `docs/branching_strategy.md`
  - `docs/CONTRIBUTING.md`
  - `docs/PR_readme.md`
  - `docs/starVLA_guideline.md`
- Pre-existing unrelated dirty paths from before M0 must be noted and not reverted.

### V6 -- Manager Inline Review

Review target:

```text
all M0-created/modified files in the whitelist
```

Manager must confirm:

- Python files have Chinese module docstrings.
- No StarVLA baseline source edits.
- No Slurm submission commands.
- No git push, PR creation, merge, or remote publication commands.
- No secrets, tokens, checkpoints, datasets, or run artifacts.
- `pyrightconfig.json` legacy file unchanged.
- Existing `make check` target unchanged.
- Global `[tool.black]` and `[tool.ruff]` settings unchanged.
- `.pre-commit-config.yaml` is path-scoped and does not lint `starVLA/`.
- CI workflow runs `make genesis-check` and not full-repo `make check`.

Expected result:

```text
V6 PASS
```

## 9. Rollback Plan

Rollback commands for M0 EXECUTE:

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

Safety notes:

- These commands should be used only after Claude explicitly approves rollback.
- Do not restore or delete unrelated pre-existing dirty files.
- Do not remove `.github/` itself.
- Do not touch `pyrightconfig.json`.
- Do not touch `starVLA/`.

Recovery:

- Removing M0 artifacts returns the repository to the post-P0 state with no GenesisVLA quality gate.
- Existing StarVLA `make check` and docs remain unchanged except for restored tracked files.

## 10. Risk List

Risks from DISCUSS:

- Scope creep: M0 can accidentally become broad architecture implementation.
- Legacy backlog contamination: full-repo `make check` is known to be unsafe as a GenesisVLA gate.
- Absent GenesisVLA directories can make strict pyright meaningless unless stubs are created.
- Case-sensitive PR template path can create duplicate templates if lowercase path is used.
- Dependency availability: local `make genesis-check` requires `pytest` and `pyright`.
- Pre-commit overreach can lint or format legacy `starVLA/` paths.
- Governance overlay files must remain local and not be published.

New PLAN risks:

- `pyright` may not be installed in the current environment before `pyproject.toml` dev deps are installed.
  - Mitigation: EXECUTE records missing-tool failures if any; CI installs tools directly; local reproducibility comes from `[project.optional-dependencies].dev`.
- Black/Ruff line length 100 must be per-call only.
  - Mitigation: tests and V6 confirm global `pyproject.toml` settings remain 121.
- `pre-commit` local hooks depend on tools installed in the active environment.
  - Mitigation: M0 acceptance uses `make genesis-check`; pre-commit is a convenience gate.
- `python -m py_compile` may create `__pycache__` if run without `PYTHONDONTWRITEBYTECODE=1`.
  - Mitigation: worker should set `PYTHONDONTWRITEBYTECODE=1` or avoid py_compile in final evidence if not needed.
- New package stubs can be mistaken for real GenesisVLA platform support.
  - Mitigation: docs and module docstrings explicitly say M0 stubs contain no platform behavior.
- CI workflow is added locally but not run through GitHub Actions unless a push/PR occurs.
  - Mitigation: VERIFY validates workflow content and local `make genesis-check`; no remote action is required in M0.

## 11. Recommended Next Stage

Recommended gate decision: `approve_execute`.

EXECUTE should use the worker plan in Section 7 exactly:

- worker type: `coding_integration_engineer`;
- count: 1;
- mode: serial;
- writable scope limited to the whitelist in Section 2;
- TDD red-green evidence required;
- stop after `pytest tests/meta/test_repo_policy.py -v` is green and `make genesis-check` is green.

Do not start EXECUTE until Claude explicitly approves this PLAN.

## 12. Self-Review

Spec coverage:

- Confirmed Claude decisions: covered in Section 1.
- In-scope/out-of-scope whitelist/blacklist: covered in Section 2.
- TDD red-green sequence: covered in Section 3.
- Implementation tasks: covered in Section 4.
- Doc content outlines: covered in Section 5.
- Config schemas: covered in Section 6.
- Worker plan: covered in Section 7.
- Validation V1-V6: covered in Section 8.
- Rollback: covered in Section 9.
- Risks: covered in Section 10.
- Recommended next stage: covered in Section 11.

Placeholder scan:

- No `TBD`, `TODO`, `placeholder`, or incomplete task placeholders are intended in this plan.

Files affected by PLAN:

- `.agent-docs/teamwork/reports/M0/PLAN.md` (written)

No source code, docs, tests, configs, workflows, scripts, datasets, Slurm files, or StarVLA baseline paths were modified during PLAN.

===HANDOFF===
Completed:
- Read required governance, blueprint, Teamwork, DISCUSS, Makefile, pyproject, PR template, pyright config, and tests README files.
- Incorporated Claude Supervisor decisions from DISCUSS review.
- Drafted the complete M0 EXECUTE plan with TDD red-green sequence, implementation tasks, config schemas, worker plan, validation plan, rollback, and risks.
- Wrote `.agent-docs/teamwork/reports/M0/PLAN.md`.

Pending:
- Claude gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
- EXECUTE must use exactly one serial `coding_integration_engineer` worker if approved.
- EXECUTE must capture red and green pytest output plus green `make genesis-check`.

Decisions:
- M0 creates minimal `genesisvla/` stubs only for strict typing and CI targets.
- Branch policy goes inside `docs/genesisvla/coding_standard.md`.
- `pytest` and `pyright` are added to the existing dev optional dependency group.
- GenesisVLA line length 100 is enforced per-command only; global StarVLA line length stays 121.
- Existing `make check` and legacy `pyrightconfig.json` remain unchanged.

Files Affected:
- `.agent-docs/teamwork/reports/M0/PLAN.md` (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
