# M0 DISCUSS — GenesisVLA RFC 与质量闸门

## Your Role

You are the **Codex Manager** for the GenesisVLA engineering repository.
Milestone: **M0 — GenesisVLA RFC 与质量闸门**.
Stage: **DISCUSS**.

This is the first real GenesisVLA engineering milestone (P0 was bootstrap only).
You are executing the **DISCUSS** stage.

You are **read-only** for all source code during this stage. You may write to:
- `.agent-docs/teamwork/reports/M0/DISCUSS.md`
- `.agent-docs/teamwork/messages.jsonl` (append only)
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/workspace/task-board.md`

Do NOT write source code, docs, tests, configs, or scripts during DISCUSS.

---

## Required Reading (do this first)

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/GenesisVLA_Blueprint_Roadmap.html` — sections: Blueprint, Target Tree, Milestones overview, M0 Features + TDD, Code Standards
5. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
6. `.agent-docs/teamwork/roadmap_progress.md`
7. `.agent-docs/repository_layout_policy.md`  ← critical for path placement decisions
8. `docs/` directory listing — understand existing StarVLA documentation structure
9. `scripts/init.sh` and `scripts/smoke_test.sh` — understand current quality gate baseline

---

## Stage Objective

Clarify scope, placement, risks, and acceptance criteria for M0 so that Claude can approve a PLAN.

M0 Blueprint scope (read from `.agent-docs/GenesisVLA_Blueprint_Roadmap.html` section 8):
- **F0.1** `docs/genesisvla/rfc_000_architecture.md`
- **F0.2** `docs/genesisvla/coding_standard.md`
- **F0.3** `docs/genesisvla/testing_standard.md`
- **F0.4** `pyrightconfig.genesisvla.json`
- **F0.5** pre-commit config for new `genesisvla/` directories
- **F0.6** CI: lint/type/unit-smoke on `genesisvla/core` and `genesisvla/config`
- **F0.7** GenesisVLA branch policy and PR template

TDD target (from blueprint):
```
tests/meta/test_repo_policy.py
- should_have_genesisvla_docs
- should_have_make_genesis_check
- should_have_pyright_strict_config
- should_have_pr_template_with_test_plan
```

Definition of Done (from blueprint):
- `make genesis-check` 绿色
- 新目录 strict typing 生效
- 旧 StarVLA backlog 不影响 GenesisVLA CI

---

## Discussion Topics

### Topic A: Doc Placement and Scope

Inspect the current `docs/` structure and answer:
- Does `docs/genesisvla/` exist? If not, is `docs/` a natural parent?
- Are there any existing StarVLA docs that conflict with or overlap F0.1-F0.3 content?
- Should the RFC and standards docs be minimal stubs for M0 (to unblock CI), or full documents?
- What is the minimum viable content for each doc to satisfy the TDD checks?

### Topic B: Pyright Config (F0.4)

Inspect any existing pyright/type-check configurations:
- Does `pyrightconfig.json` exist? What does it cover?
- `pyrightconfig.genesisvla.json` should be strict for `genesisvla/` directories only.
- What should the strict config contain minimally? (include, strict mode, pythonVersion)
- Does `genesisvla/` directory exist yet? If not, what should the pyright config point to?

### Topic C: Pre-commit Config (F0.5)

Inspect existing pre-commit or lint configuration:
- Does `.pre-commit-config.yaml` exist? What hooks does it run?
- Should F0.5 add new hooks for the `genesisvla/` directory, or create a separate config?
- Which hooks matter most for M0: ruff, black, pyright, or a custom genesis-check?

### Topic D: CI Setup (F0.6)

Inspect existing CI configuration (`.github/workflows/` or equivalent):
- What CI pipelines already exist for StarVLA?
- Should GenesisVLA CI be a new workflow file, a new job in an existing file, or triggered via `make genesis-check`?
- `genesisvla/core` and `genesisvla/config` don't exist yet — should CI guard against their absence or create stub `__init__.py` files?
- What is the minimal CI that makes `make genesis-check` meaningful for M0?

### Topic E: Branch Policy and PR Template (F0.7)

Inspect existing branch/PR documentation:
- Does `.github/pull_request_template.md` or similar exist?
- Does `docs/branching_strategy.md` exist and cover GenesisVLA?
- What should the GenesisVLA PR template include minimally (test plan, genesis-check result)?

### Topic F: TDD First Principle

The blueprint mandates: "每个 issue 先合测试，再合实现" (tests merged first, then implementation).
For M0 specifically:
- What should `tests/meta/test_repo_policy.py` contain at the point Claude approves EXECUTE?
- Should the tests be in `tests/meta/` (new dir) or elsewhere?
- Does a `tests/` directory already exist?
- Should the TDD tests be written by the EXECUTE worker *before* the docs/configs are created?

### Topic G: make genesis-check Target

F0.6 requires `make genesis-check` to be green. Inspect the current `Makefile` or build system:
- Does a `Makefile` exist? What targets does it have?
- Should `genesis-check` be a new `make` target or a standalone script?
- What does "green" mean for M0: just pyright + lint on empty dirs, or the full TDD suite?

---

## Investigation Commands (read-only)

```bash
# Existing docs
ls -la docs/ 2>/dev/null
find docs/ -name "*.md" 2>/dev/null | head -20

# Pyright / type config
find . -name "pyrightconfig*.json" -not -path "./.git/*" 2>/dev/null
cat pyrightconfig.json 2>/dev/null || echo "not found"

# Pre-commit
ls -la .pre-commit-config.yaml 2>/dev/null || echo "not found"
cat .pre-commit-config.yaml 2>/dev/null | head -40

# CI
ls -la .github/workflows/ 2>/dev/null || echo "not found"
ls -la .github/ 2>/dev/null

# Makefile
ls -la Makefile 2>/dev/null || echo "not found"
head -60 Makefile 2>/dev/null

# Tests
ls -la tests/ 2>/dev/null || echo "not found"
find tests/ -name "*.py" 2>/dev/null | head -20

# PR template
ls -la .github/pull_request_template.md 2>/dev/null || echo "not found"
cat .github/pull_request_template.md 2>/dev/null | head -30

# genesisvla package
ls -la genesisvla/ 2>/dev/null || echo "genesisvla/ does not exist yet"
```

---

## Output Requirements

Write your complete stage report to:
```
.agent-docs/teamwork/reports/M0/DISCUSS.md
```

The report must contain:
1. Investigation findings for each topic (A-G)
2. Decisions made in DISCUSS
3. Open questions requiring Claude input
4. Risks
5. M0 PLAN scope recommendation
6. Recommended next stage action

End your **final response** with:

```
===HANDOFF===
Completed:
- [list]

Pending:
- [list]

Decisions:
- [list]

Files Affected:
- .agent-docs/teamwork/reports/M0/DISCUSS.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

**STOP after DISCUSS.md and HANDOFF.** Do NOT implement any files.
PLAN requires Claude's explicit approval.
