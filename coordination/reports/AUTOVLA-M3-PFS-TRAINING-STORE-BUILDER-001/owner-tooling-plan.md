# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Tooling Plan Review

## Role And Mode

- Role: 70-OWNER - Tooling
- Task: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001
- Stage: Wave 1 read-only tooling/gate plan review
- Dispatch reasoning policy recorded: thinking=xhigh
- Prohibited reasoning policy: thinking=max not used
- Allowed write used: this Owner planning report only
- Conclusion: APPROVE_PLAN

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Status: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
- Tracked `genesisvla/**`: none
- Git index mutation: none

## Evidence Reviewed

- Governance:
  - `AGENTS.md`
  - `boundaries.txt`
  - `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- Task/plan evidence:
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-product-spec-plan.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-plan.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-architecture-plan.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-quality-plan.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-training-plan.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-model-plan.md`
- Current tooling/gate surfaces:
  - `scripts/quality/autovla_check_project_local.sh`
  - `scripts/quality/autovla_build_verify_project_local.sh`
  - `.github/workflows/autovla.yml`
  - `.pre-commit-config.yaml`
  - `pyrightconfig.autovla.json`
  - `Makefile`
  - `pyproject.toml`
  - `requirements/quality/quality-requirements.txt`
  - `requirements/quality/quality-constraints.txt`
  - `tests/meta/test_repo_policy.py`
- Current perf harness and tests:
  - `autovla/dataloader/perf/config.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/metrics.py`
  - `autovla/dataloader/perf/cli.py`
  - `autovla/dataloader/perf/MODULE.md`
  - `docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md`
  - `tests/dataloader/test_perf_harness.py`

## Task Card / Spec Traceability

- No exact task card was found in this worktree at `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`.
- No exact dedicated spec file was found in this worktree for `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001`.
- Product/Spec, Data, Quality, Training, and Model Owner reports provide enough bounded plan evidence for Tooling to review gate feasibility.
- Architecture recorded `BLOCKED_SCOPE` because the formal task card/spec are missing. This Tooling `APPROVE_PLAN` is domain-limited and does not override Architecture's scope blocker; Manager should attach or create the formal task contract before write implementation starts.

## Project-Local Tool Environment

- Existing project-local tool environment is present:
  - `runs/tmp/m1-tool-venv/bin/python`: executable
  - `runs/tmp/m1-tool-venv/bin/pyright`: executable
  - `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/stamps/m1-tool-venv.ready.json`: present
- Readiness stamp target root matches this worktree:
  - `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Installed quality tools include pinned `black`, `ruff`, `pyright`, `pytest`, `build`, `numpy`, `pyarrow`, `setuptools`, and `wheel`.
- No tool recovery, dependency install, network package operation, global/user/Conda/system mutation, or toolchain mutation was performed.
- Tooling environment conclusion: no `BLOCKED_TOOL_ENV` condition found.

## Dependency And Toolchain Policy

- No dependency spec change is needed for a v0 `.npz`/JSONL store:
  - `.npz` can use existing pinned `numpy`.
  - JSON/JSONL should use the standard library.
  - Existing quality tooling already pins `numpy` and `pyarrow`; do not add WebDataset, Arrow/Parquet store dependencies, torch, HF, W&B, or model/runtime packages in this task.
- Current diff check over dependency/tooling surfaces is empty for:
  - `pyproject.toml`
  - `requirements/**`
  - lockfiles
  - `Makefile`
  - `pyrightconfig.autovla.json`
  - `.github/workflows/autovla.yml`
  - `.pre-commit-config.yaml`
  - `scripts/quality/**`
- Tooling plan requires dependency diff scan before publication and should fail closed as `REQUEST_CHANGES_PLAN` if implementation attempts dependency or toolchain drift.

## Gate Coverage Assessment

Existing gates are sufficient if implementation stays in the planned roots:

- Source under `autovla/dataloader/perf/**` is covered by:
  - CI path filter `autovla/**`
  - pre-commit Black/Ruff/Pyright regex `autovla/`
  - `scripts/quality/autovla_check_project_local.sh` product file list and Ruff/Pyright inputs
  - `pyrightconfig.autovla.json` include `autovla`
- Tests under `tests/dataloader/**` are covered by:
  - CI path filter `tests/dataloader/**`
  - pre-commit Black/Ruff/Pyright regex `tests/(core|config|dataloader|training|maintenance|slurm)`
  - product pytest `tests/core tests/config tests/dataloader tests/training tests/maintenance tests/slurm`
  - `pyrightconfig.autovla.json` include `tests/dataloader`
- Meta policy tests under `tests/meta/**` are covered by:
  - CI path filter `tests/meta/**`
  - `make governance-check`
  - `autovla-policy-tests` hook
- No wrapper, Pyright, Makefile, workflow, or pre-commit coverage update is required for source/tests in the planned roots.

Documentation caveat:

- `docs/autovla/**` is covered by CI and policy-test hook triggers.
- `docs/architecture/**` is not directly listed in `.github/workflows/autovla.yml` or the policy-test hook regex. If implementation adds or changes active PFS docs under `docs/architecture/**`, Manager should either place active task docs under a covered docs root such as `docs/autovla/**`, or explicitly accept/update path-filter coverage in a separate Tooling-scoped change.
- Nested Markdown is broadly ignored by `.gitignore`; publisher must use exact pathspecs or force-add only intended ignored docs and must not force-add generated artifacts or caches.

## `.npz` / JSONL Store Validation Plan

Login-node-safe validation should use existing project-local tools only:

- `git diff --check`
- `py_compile` for touched Python files with `PYTHONPYCACHEPREFIX` under task evidence
- focused pytest for:
  - new store manifest/index/shard tests
  - existing `tests/dataloader/test_perf_harness.py`
  - any new/updated `tests/meta/**` policy tests
- focused Ruff on touched Python files
- file-by-file Black on touched Python files if broad Black remains unreliable
- strict Pyright through the existing wrapper or focused project-local Pyright when scoped by Quality/Tooling
- CLI help/render/validate smoke only if it uses tiny fixtures and writes to `tmp_path` or ignored task evidence

Recommended test coverage for the store builder:

- Manifest JSON roundtrip and deterministic serialization.
- `sample_index.jsonl` and `episode_index.jsonl` roundtrip using JSON-safe records.
- `.npz` shard write/read with deterministic checksums and bounded sample counts.
- Source dataset remains unchanged.
- Output/store directory cannot be inside source dataset root, `datasets/readonly/**`, or repository root.
- Generated outputs are written only under `tmp_path`, `runs/tmp/**`, or another explicitly governed ignored output path.
- No full dataset conversion, unbounded media decode, model/checkpoint/tokenizer load, W&B/HF network, Slurm, GPU, endpoint, robot, or real training.

Artifact tracking policy:

- `.gitignore` already ignores `**/*.npz`.
- Build wheel scan already rejects `.npz`, `.npy`, `.parquet`, checkpoints, model weights, archives, and top-level `datasets`/`runs` entries.
- JSONL cannot be globally banned because `meta/tasks.jsonl` and `metrics_timeseries.jsonl` are legitimate text fixtures/evidence patterns. Instead, tests/meta should block generated training-store JSONL payloads from tracked output roots and ensure store JSONL artifacts live under ignored evidence or governed derived-data paths only when explicitly authorized.

## Tests/Meta Recommendation

Tooling recommends a narrow meta-policy update if implementation introduces active PFS store docs or public acceptance text:

- Assert no tracked generated store payloads:
  - `*.npz`
  - store shard payloads
  - generated `sample_index.jsonl` / `episode_index.jsonl` outside approved source fixtures
  - dataset/media/checkpoint/model-weight artifacts
- Assert no dependency spec diff for the task.
- Assert no tracked `genesisvla/**`, `import genesisvla`, or compatibility alias.
- Assert active PFS store docs do not describe local NVMe/local-cache as the authoritative store.
- Assert any public docs describe PFS Training Store v0 as a bounded readiness/foundation surface, not real fine-tune readiness.

No broad quality-wrapper rewrite is needed if this meta-policy is added under `tests/meta/**` and implementation stays under the existing source/test roots.

## Required Pre-Publication Scans

- Changed-file scope scan against the approved implementation/test/doc/report roots.
- Dependency/toolchain diff scan.
- Secret/private endpoint scan over changed text.
- Artifact/media/generated-output scan for staged files and diff:
  - block committed `.npz`, `.npy`, `.parquet`, `.mp4`, `.pt`, `.pth`, `.ckpt`, `.safetensors`, archives, model weights, datasets, checkpoints, and run outputs.
- Large-file and large-text-diff scan.
- Compatibility shim scan:
  - `git ls-files 'genesisvla/**'` remains empty.
  - no `import genesisvla`, alias package, fallback import, or compatibility shim.
- External-effect scan for W&B/HF, model/checkpoint/tokenizer load, Slurm/GPU, endpoint/robot, and real training activation.
- Git index scan proving generated store artifacts and `runs/tmp/**` evidence are not staged.

## Tooling Risks

- Missing formal task card/spec is a scope traceability risk owned by Manager/Architecture, not a Tooling environment blocker.
- `.npz` is safe with existing `numpy`, but generated shard files must never be committed.
- JSONL is text and useful for indexes, but store JSONL must be classified by path and purpose; do not add a blanket JSONL ban.
- `docs/architecture/**` changes are not directly path-filter covered; prefer covered docs roots or explicitly update coverage in a scoped Tooling change.
- If final acceptance depends on real PFS throughput, Compute/HPC must own the authorized compute-node evidence; Tooling should not run that from this plan gate.

## DevSpace MCP Compliance

- DevSpace MCP: no.
- `vla-flywheel-devspace`: no.
- MCP connectors, `open_workspace`, MCP read/write/edit/bash: no.
- DevSpace-derived evidence: no.

## Mutation Boundary

- No source, tests, docs, configs, tools, dependencies, datasets, runtime outputs, git index, commit, branch, push, PR state, Slurm, GPU, training, model, checkpoint, W&B/HF, endpoint, robot, or external service was modified or run.
- This report is the only write performed by Tooling.

## Subagent Ledger

- Child subagents used: none.
- Child-agent depth used: 0.
- Active child contexts remaining: none.
- Reviewer-does-not-patch: honored.
- Retired: yes.

## Conclusion

APPROVE_PLAN
