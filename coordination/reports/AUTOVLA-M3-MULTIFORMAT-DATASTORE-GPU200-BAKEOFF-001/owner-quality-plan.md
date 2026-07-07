# Owner Quality Plan

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- owner_role: `Quality`
- mode: `read-only planning review`
- conclusion: `PASS`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- workspace_check: `PASS`

## Packet Follow-Through

I reviewed the Quality owner packet and the cited task sources:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `tests/dataloader/test_backend_bakeoff_dashboard.py`
- `tests/dataloader/test_format_native_loader_bakeoff.py`
- `tests/training/test_baseline_metrics.py`
- `.agent-docs/git_workflow.md`

The packet objective is aligned with the task card: plan a read-only Quality gate for deterministic bounded sample/window manifests, multiformat candidate tables, GPU200 telemetry evidence, generated-artifact exclusion, and safe draft-PR publication.

## Exact Validation Matrix

Planned login-node-safe validation before any commit/push/draft PR:

1. Workspace and diff hygiene
   - `git status --short --branch`
   - `git diff --check`
   - `git diff --name-only`
   - `git ls-files --others --exclude-standard`

2. Focused dataloader/store tests
   - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_backend_bakeoff_dashboard.py -v`
   - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_format_native_loader_bakeoff.py -v`
   - Add focused new store tests in `tests/dataloader/**` for:
     - deterministic shared sample/window manifest generation
     - raw/WebDataset/RoboDM-style/Zarr candidate row coverage
     - blocked candidate reason preservation
     - no source-dataset writes
     - no generated artifact path leakage into tracked docs/report outputs

3. Focused training/telemetry tests
   - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/training/test_baseline_metrics.py -v`
   - Add focused new telemetry tests in `tests/training/**` for:
     - GPU200 telemetry manifest/report schema
     - redaction of sensitive fields
     - no subprocess/network side effects
     - explicit `missing`/`not_observed` classification for absent telemetry

4. Static quality gates on changed Python
   - `runs/tmp/m1-tool-venv/bin/python -m py_compile <changed_python_files>`
   - `runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/stores autovla/training/telemetry tests/dataloader tests/training`
   - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 <changed_python_files>`
   - `runs/tmp/m1-tool-venv/bin/pyright -p pyrightconfig.autovla.json`

5. Project-local wrapper gate
   - `bash scripts/quality/autovla_check_project_local.sh`

6. Compute-owned evidence that Quality must later review, not run in this plan turn
   - real compute-node store benchmark over runnable candidates
   - real one-GPU 200-step telemetry over runnable candidates
   - governed logs and structured JSON/CSV/Markdown outputs under task-local `runs/tmp/**`

## Publication And Scan Gates

Required pre-publication scans:

1. Secret scan
   - use the repo `git_workflow.md` secret pattern gate over staged and tracked candidate content

2. Blocked artifact-extension scan
   - reject staged `.pt`, `.pth`, `.ckpt`, `.safetensors`, `.onnx`, `.bin`, `.parquet`, `.arrow`, `.npy`, `.npz`, `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.zst`

3. Large staged file scan
   - reject staged files above the repo threshold in `.agent-docs/git_workflow.md`

4. Large text diff scan
   - reject oversized staged text diffs per `.agent-docs/git_workflow.md`

5. Protected-path scan
   - no mutation under:
     - `datasets/readonly/**`
     - `requirements/**`
     - `pyproject.toml`
     - `Makefile`
     - `AGENTS.md`
     - `checkpoints/**`
     - `code-input/**`

6. Generated artifact scan
   - `git ls-files datasets/working runs/tmp checkpoints`
   - `git status --short -- datasets/working runs/tmp checkpoints`
   - any generated shard/store/media/checkpoint artifact must remain ignored/untracked

7. Dependency drift scan
   - confirm no changes in `requirements/**`, `pyproject.toml`, or other dependency surfaces

## What May Remain Ignored

The following may remain ignored while source/docs publish safely:

- generated candidate stores, converted shards, cache/index files, and telemetry outputs under `datasets/working/**`
- task-local compute and comparison evidence under `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
- raw logs, structured benchmark intermediates, and temporary manifests that are not intended as tracked docs/source

Safe publication requires that tracked content stay limited to source, tests, configs, README/docs benchmark summaries, coordination reports, and other task-card-approved text/code surfaces. Generated datasets, stores, media, raw telemetry outputs, and checkpoints must remain untracked even if they are used as local evidence.

## Tooling Sufficiency Decision

Current project-local tooling is **not yet sufficient** for the proposed gate in this worktree.

Observed blocker:

- `runs/tmp/m1-tool-venv/bin/python` is missing in this worktree.
- `bash scripts/quality/autovla_check_project_local.sh` exits `127`.
- Exact wrapper error:
  - `missing project-local python: /home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/m1-tool-venv/bin/python`

This is a tool-environment blocker, not a source-quality failure. Under the packet rules, Quality must fail closed as `BLOCKED_TOOL_ENV` until the required worktree-local project-local tooling path exists.

## Quality Decision

Quality approves the planned validation matrix and scan boundaries in substance, but the plan cannot be accepted as runnable yet because the decisive project-local wrapper path is unavailable in the assigned worktree.

To clear this blocker, the worktree-local project-local tool environment must exist first. After that, the exact validation commands above are sufficient for the local Quality gate, with compute-node benchmark/telemetry evidence reviewed in a later non-planning stage.

## DevSpace MCP Compliance

- DevSpace MCP used: `no`

## Subagent Retirement Ledger

- subagents used: `none`
- retired: `yes`

## Addendum - Manager Toolenv Clarification

Manager clarified that this planning gate requires project-local tooling, not necessarily a worktree-local duplicate environment. I independently verified that the root project-local Python exists and is executable at:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python`

Revised planning conclusion: `PASS`.

Reason:

- The earlier blocker was specific to the worktree-local wrapper lookup path.
- For this planning gate, direct validation commands from this worktree may use the existing root project-local toolenv without changing dependencies or touching any global/user/system environment.
- Therefore the proposed gate is runnable if command paths are written against the root project-local toolenv explicitly.

Quality planning adjustment:

- Replace worktree-relative `runs/tmp/m1-tool-venv/bin/python ...` command examples in execution with `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python ...`.
- Treat `bash scripts/quality/autovla_check_project_local.sh` as usable only if the branch-local wrapper is updated to honor the existing root project-local toolenv or if Manager invokes equivalent direct commands instead.

This changes the planning outcome from tool-env blocked to plan approved. It does not authorize dependency mutation, global install, or generated-artifact publication.
