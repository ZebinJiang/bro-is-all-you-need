# GVLA-M1-PUBLISH-001A Owner Architecture Review

Owner: 10-OWNER - Architecture
Task: GVLA-M1-PUBLISH-001A - M1 publication scope audit
Mode: read-only publication scope review
Date: 2026-06-22

## Decision

BLOCKED_SCOPE.

The current index must not proceed to publication as-is. It stages broad governance/archive/local-skill material while several accepted M1 implementation, test, report, and publication-audit files remain untracked. Architecture approves a narrower M1/M1-T candidate scope for restaging, but publication cannot proceed to 001B until ambiguous groups are decided and the index is rebuilt to the approved scope.

## Evidence reviewed

- `AGENTS.md`
- `boundaries.txt`
- `coordination/THREAD_REGISTRY.yaml`
- `coordination/reports/GVLA-M1-PUBLISH-001A/owner-quality.md`
- `.agent-docs/feature_list.json`
- `.agent-docs/progress.txt`
- `.agent-docs/review.txt`
- `coordination/reports/GVLA-M1-ACCEPT-001/manager-summary.md`
- `coordination/reports/GVLA-M1-COV-001/manager-summary.md`
- `coordination/reports/GVLA-M1-TOOL-001/manager-summary.md`
- `coordination/reports/GVLA-M1T-003/manager-summary.md`
- Read-only git scope checks: `git status --short`, staged/untracked root counts, staged rename scan, staged/untracked artifact-pattern scan, and DevSpace MCP governance search.

## Scope assessment

Quality reports `BLOCKED_SCOPE`, wrapper PASS, pytest `43/43`, Black/Ruff/Pyright PASS. Architecture agrees with the Quality block: validation health is acceptable, but publication scope is not.

Read-only index evidence:

- Staged root counts: `.agent-docs` 78, `.agents` 36, `docs` 18, `scripts` 10, `coordination` 9, `configs` 4, plus root files.
- Untracked root counts: `genesisvla` 31, `coordination` 21, `tests` 10, `docs` 3, `scripts` 2, plus `.github`, `.pre-commit-config.yaml`, `pyrightconfig.genesisvla.json`, and `skills-lock.json`.
- Five staged renames move `docs/agent_skills/integrate-starvla-dataset/assets/templates/*` into `.agent-docs/agent_skills/...`.
- Artifact-pattern scan found no staged or untracked `runs/`, `datasets/`, `__pycache__`, `.pyc`, checkpoints, weights, logs, or cache files in git candidate lists.

This means the current index simultaneously includes broad unrelated/ambiguous archive material and omits core accepted M1 candidate files. That is a publication-scope blocker, not a code-quality blocker.

## Approved include groups

These groups are Architecture-approved for a narrow M1/M1-T publication candidate after restaging:

1. M1 core/config implementation:
   - `genesisvla/__init__.py`
   - `genesisvla/py.typed`
   - `genesisvla/core/**`
   - `genesisvla/config/**`
   - `pyrightconfig.genesisvla.json`

2. M1 tests and direct contract coverage:
   - `tests/core/**`
   - `tests/config/**`
   - `tests/meta/test_repo_policy.py`

3. M1 docs:
   - `docs/genesisvla/rfc_000_architecture.md`
   - `docs/genesisvla/coding_standard.md`
   - `docs/genesisvla/testing_standard.md`

4. M1 coordination evidence and task cards:
   - `coordination/reports/GVLA-M1-RECON-001/**`
   - `coordination/reports/GVLA-M1-QG-001/**`
   - `coordination/reports/GVLA-M1-TOOL-001/**`
   - `coordination/reports/GVLA-M1-COV-001/**`
   - `coordination/reports/GVLA-M1-ACCEPT-001/**`
   - `coordination/reports/GVLA-M1-PUBLISH-001A/owner-quality.md`
   - `coordination/reports/GVLA-M1-PUBLISH-001A/owner-architecture-review.md`
   - `coordination/tasks/active/GVLA-M1-QG-001.yaml`
   - `coordination/tasks/active/GVLA-M1-TOOL-001.yaml`
   - `coordination/tasks/active/GVLA-M1-COV-001.yaml`
   - `coordination/tasks/active/GVLA-M1-ACCEPT-001.yaml`
   - `coordination/tasks/active/GVLA-M1-PUBLISH-001A.yaml`
   - `coordination/PROGRAM_STATE.yaml`
   - `coordination/TASK_INDEX.yaml`

5. M1-T registry/governance evidence:
   - `AGENTS.md`
   - `boundaries.txt`
   - `coordination/THREAD_REGISTRY.yaml`
   - `coordination/tasks/active/GVLA-M1T-001.yaml`
   - `coordination/tasks/active/GVLA-M1T-002.yaml`
   - `coordination/tasks/active/GVLA-M1T-003.yaml`
   - `coordination/reports/GVLA-M1T-002/manager-summary.md`
   - `coordination/reports/GVLA-M1T-003/manager-summary.md`
   - `coordination/templates/**`
   - `docs/coordination/**`

6. Project-local quality wrapper and repo gates:
   - `scripts/quality/genesis_check_project_local.sh`
   - `Makefile`
   - `pyproject.toml`
   - `.github/PULL_REQUEST_TEMPLATE.md`
   - `.github/workflows/genesisvla.yml`
   - `.pre-commit-config.yaml`

7. Narrow M1 acceptance governance records:
   - `.agent-docs/feature_list.json`
   - `.agent-docs/progress.txt`
   - `.agent-docs/review.txt`
   - `.agent-docs/git_workflow.md`

## Required exclude groups

These groups must be excluded from the M1 publication candidate unless a later explicit Manager/user decision reclassifies them with evidence:

1. Broad local skill overlays:
   - `.agents/**`
   - `.agent-docs/agent_skills/**`
   - staged `docs/agent_skills/... -> .agent-docs/agent_skills/...` renames

2. Broad legacy Teamwork archive:
   - `.agent-docs/teamwork/**` by default, including prompts, session JSON, message logs, roadmap progress, workspace files, and broad P0/M0/M1 report snapshots.

3. Generated or broad blueprint/archive artifacts:
   - `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
   - broad `.agent-docs/*_policy.md`, `.agent-docs/*_workflow.md`, `.agent-docs/asset_manifest.md`, `.agent-docs/config_contracts.md`, `.agent-docs/execution_contract.md`, `.agent-docs/implementation_blueprint.md`, `.agent-docs/repository_layout_policy.md`, `.agent-docs/slurm_*`, `.agent-docs/sandbox_validation.md`, unless Manager explicitly ties each file to accepted M0/M1 publication scope.

4. Broader Slurm/data/maintenance/sandbox support not required by M1 local feature acceptance:
   - `configs/slurm/**`
   - `configs/experiments/example_experiment.json`
   - `configs/project.json`
   - `scripts/slurm/**`
   - `scripts/data/**`
   - `scripts/maintenance/**`
   - `scripts/sandbox/**`
   - `scripts/init.sh`
   - `scripts/smoke_test.sh`

5. Other ambiguous/unrelated paths:
   - `examples/mock_genesisvla_task.py` unless Manager explicitly declares it the M1 milestone example.
   - `scripts/teamwork/dispatch_codex_manager.py`
   - `skills-lock.json`
   - any cache/generated artifact, `runs/**`, `datasets/**`, checkpoints, weights, logs, or local tool environments.

## Ambiguous groups needing user or Manager decision

1. `.agent-docs/teamwork/**`:
   - Architecture decision: broad Teamwork archive is not required for M1 publication because accepted evidence is now recorded in `coordination/reports/**`, `.agent-docs/feature_list.json`, `.agent-docs/progress.txt`, and `.agent-docs/review.txt`.
   - Publication should not delete or erase this historical audit evidence; it should remain available locally unless a separate cleanup/archive policy is approved.
   - If the Manager/user wants original historical blueprint provenance in publication, approve only a narrow selected subset, such as the specific M1 plan/report file(s), rather than the full archive.

2. `.agents/**` and skill overlays:
   - Useful for local agent operation, but not established as required M1 feature evidence. Requires explicit publication decision.

3. Staged skill-template renames:
   - The five `docs/agent_skills/...` to `.agent-docs/agent_skills/...` renames are unrelated to M1 core/config acceptance unless Manager supplies separate accepted evidence. Requires explicit decision before publication.

4. Broad Slurm/data/maintenance/sandbox scripts and configs:
   - Useful governance/runtime scaffolding, but M1 acceptance is local core/config only and has no Slurm-dependent acceptance claim. Requires explicit decision or later milestone routing.

5. `examples/mock_genesisvla_task.py`:
   - Include only if Manager declares it the M1 milestone example and records that decision.

6. `scripts/teamwork/dispatch_codex_manager.py` and `skills-lock.json`:
   - Not needed for accepted M1 feature evidence. Requires explicit provenance and publication decision.

## Can publication proceed to 001B?

No. Publication must not proceed to 001B with the current index.

Required before 001B:

1. Restage only the approved include groups.
2. Exclude required exclude groups.
3. Resolve ambiguous groups by explicit Manager/user decision.
4. Re-run required local scan evidence after restaging and before any commit/push/PR.
5. Keep M1 milestone `passes: false` until a PR URL exists and the publication gate is complete.

## M1 passes and historical evidence note

`.agent-docs/feature_list.json` currently has M1-F1, M1-F2, and M1-F3 `passes: true` with evidence, while M1 milestone `passes` remains `false`. This is correct for local feature-level acceptance and must remain unchanged until publication/PR evidence exists.

Publication scope should preserve historical audit evidence by retaining accepted coordination reports and local acceptance governance records. Excluding broad `.agent-docs/teamwork/**` from publication is not deletion; it is a narrower publication boundary. Any deletion or archive cleanup would require a separate cleanup proposal and explicit confirmation.

## DevSpace MCP compliance result

PASS.

Architecture used local shell/git inspection and this direct report write only; no DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP `read`, MCP `write`, MCP `edit`, or MCP `bash` was used for this review.

Search results show DevSpace MCP is mentioned in:

- `AGENTS.md` as a boundary forbidding it as repository-internal workflow evidence.
- `coordination/tasks/active/GVLA-M1-PUBLISH-001A.yaml` as a compliance criterion.
- `coordination/reports/GVLA-M1-PUBLISH-001A/owner-quality.md` as Quality compliance evidence.
- `tests/meta/test_repo_policy.py` as policy coverage.

No reviewed prompt, skill, report, or config was found recommending DevSpace MCP as internal Manager/Owner/subagent workflow evidence. No governance violation is recorded.

## Subagent retirement ledger

None used. No short-lived direct subagents were created for this Architecture review, so none required retirement.

## Parallelism

No parallel writes. Read-only shell/git inspection was parallelized where useful. The only write is this Architecture Owner report at `coordination/reports/GVLA-M1-PUBLISH-001A/owner-architecture-review.md`.

## Final recommendation

Block the current publication index as-is. Approve the narrower selected M1/M1-T candidate groups above for restaging. Proceed to 001B only after the index has been rebuilt around those groups, ambiguous groups are resolved, and required scans pass on the final staged set.
