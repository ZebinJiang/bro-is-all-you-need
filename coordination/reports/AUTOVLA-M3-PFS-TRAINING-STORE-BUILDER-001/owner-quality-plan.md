# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Owner Quality Plan

Role: 60-OWNER - Quality
Mode: Wave 1 read-only validation/publication plan
Dispatch reasoning policy recorded: thinking=xhigh; thinking=max not used
DevSpace MCP: not used

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git branch --show-current`: `dev/feat-autovla-m3-dataloader-perf-harness`
- `git rev-parse HEAD`: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch --untracked-files=all`:

```text
## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness
```

The worktree is at the expected branch/head and has no visible source/test/docs/config dirty state at plan-gate time.

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/reports/AUTOVLA-M3-PR13-MERGE-AND-DATALOADER-PERF-HARNESS-001/manager-summary.md`
- `autovla/dataloader/perf/MODULE.md`
- `autovla/dataloader/perf/config.py`
- `tests/dataloader/test_perf_harness.py`
- GitHub PR #14 read-only metadata via GitHub app:
  - URL: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/14`
  - State: open
  - Draft: true
  - Base: `main`
  - Head branch: `dev/feat-autovla-m3-dataloader-perf-harness`
  - Head SHA: `69c371e5861dccb6d374f8c1e155b55304a1f927`
  - Mergeable: true
  - Changed files: `16`

Task-card/spec lookup:

- Exact searches for `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001`, `TRAINING-STORE-BUILDER`, and `Training Store v0` under `coordination`, `.agent-docs`, `runs`, and `docs` returned no local task card/spec file.
- This plan therefore treats the Manager dispatch as the controlling Wave 1 planning input.
- Before any writer starts implementation, Manager should create or attach the task contract/spec evidence, or the writer must fail closed as `BLOCKED_SCOPE` rather than inventing missing Training Store v0 schema details.

## Current PR #14 Context

PR #14 is a request-changes draft for the DataLoader performance harness. It includes:

- `autovla/dataloader/perf/**`
- `tests/dataloader/test_perf_harness.py`
- dataloader/perf documentation
- architecture roadmap/docs
- manager summary evidence

Current blocker recorded in the PR body and manager summary:

- Compute job `1824` on `instance-yp83uwa1-1`, A100-SXM4-80GB.
- `metadata-only`: `INSUFFICIENT_TELEMETRY`.
- `bounded-decode`: `FAIL`.
- Failure reason: `media_decode_time_ms dominates per-batch time`.

The Training Store v0 plan should be evaluated as a bounded follow-up to PR #14, not as a new unrelated PR. Its publication target is the existing draft PR #14 unless Manager explicitly changes the publication route.

## Quality Assessment

The proposed Training Store v0 validation plan is approvable if it remains narrowly scoped to a deterministic, local-first training-store builder that:

- materializes derived store artifacts only into caller-provided output directories or governed temporary paths;
- never writes to source datasets, `datasets/readonly`, or the repository root;
- does not commit generated store/media/cache artifacts;
- does not add dependency declarations;
- does not reintroduce `genesisvla/**` or compatibility shims;
- does not activate real model, checkpoint, tokenizer, W&B/HF, endpoint, robot, or real training behavior;
- directly addresses PR #14's decode/store bottleneck evidence or records an Owner-approved `WARN` if the measurable blocker is not fully closed.

Quality should not accept a merge-ready state unless the final evidence is `PASS` or an explicit Owner-approved `WARN` with bounded risk. `FAIL`, unapproved `WARN`, missing compute evidence, missing scans, or missing exact-head CI keeps PR #14 draft/request-changes.

## TDD Plan For Training Store v0

Required tests before implementation is accepted:

1. Training Store config/schema tests
   - accept only explicit source dataset/artifact path, output directory, mode, max samples/episodes, shard/chunk size, and deterministic seed if needed;
   - reject unknown fields, empty strings, path traversal, output under source dataset root, output under `datasets/readonly`, output under repository root, and unbounded sample counts;
   - reject model/checkpoint/tokenizer/W&B/HF/endpoint/robot/training fields.

2. Deterministic manifest tests
   - write a stable `training_store_manifest.json` or equivalent v0 manifest;
   - include schema version, source artifact fingerprint/checksum, source dataset reference, row/sample count, generated store file list, per-file checksums, builder config, and external-effects flags;
   - repeated runs from the same tiny fixture must produce byte-identical manifest content except for explicitly documented run-local output paths, if any.

3. Source immutability tests
   - prove no source dataset file is modified;
   - prove no artifact is written inside the source dataset root;
   - prove no media/parquet/checkpoint/model-weight file is committed or staged.

4. Tiny fixture builder tests
   - use `tmp_path` and tiny metadata/sample fixtures only;
   - validate generated store layout and manifest references;
   - validate missing optional telemetry is explicit and not fabricated.

5. Perf harness integration tests
   - ensure PR #14 perf harness can consume or compare the Training Store v0 manifest/output contract;
   - show the training-store path either removes bounded-decode from the hot path or clearly records remaining decode/cache gaps.

6. CLI/render/validate tests
   - `--help` succeeds;
   - render-only or validate-only modes do not create store artifacts outside the output dir;
   - invalid configs fail with nonzero exit and actionable error text;
   - dry-run does not read media payloads unless compute-authorized.

7. Security and external-effect tests
   - no W&B/HF/network calls;
   - no Slurm/GPU on login node;
   - no endpoint/robot/action-producing strings beyond explicit negative-policy text;
   - secret/private endpoint redaction or absence is covered.

8. Publication-policy tests
   - no dependency diff;
   - no compatibility shim;
   - no `genesisvla/**`;
   - no tracked generated store/media/cache artifacts.

## Login-Node-Safe Validation Plan

Allowed login-node checks for implementation review:

- workspace verification and clean/staged-index checks;
- `git diff --check`;
- `py_compile` on changed Python files with `PYTHONPYCACHEPREFIX` under task evidence;
- focused pytest only for Training Store v0 unit tests and any directly impacted perf harness tests;
- focused Ruff on changed Python files;
- file-by-file Black check on changed Python files if broad Black remains unreliable;
- JSON/YAML parse for changed config/example files;
- CLI help and render-only/validate-only smoke using tiny `tmp_path` or task evidence output paths;
- `bash -n` only if shell wrappers are changed;
- changed-file scope scan;
- secret/private endpoint scan over changed diff and PR body/report content;
- artifact/media/large-file/generated-output scan over changed/staged files;
- dependency diff scan;
- compatibility shim / old package scan;
- source dataset write scan by test assertions and changed-code inspection.

Forbidden on login node:

- full pytest over unrelated suites;
- full Pyright/full pre-commit if it exceeds login-node policy;
- wheel build or clean install unless Tooling explicitly classifies it safe;
- real dataset conversion;
- media decode over real data;
- Slurm/srun/sbatch;
- GPU/runtime training/model/checkpoint/tokenizer load;
- W&B/HF/network/endpoint/robot actions.

## Compute-Node Validation Plan

Compute/HPC validation is required before merge readiness if Training Store v0 claims to resolve PR #14's bounded-decode/performance blocker.

Required compute evidence:

- Compute/HPC Owner authorization and budget for the exact command.
- Project wrapper or governed compute command that records node/job id, environment, command, outputs, and logs.
- Bounded dataset/media scope; no full dataset conversion unless explicitly authorized.
- Before/after or store-vs-non-store evidence tied to PR #14 metrics:
  - `media_decode_time_ms`;
  - `data_wait_time_ms`;
  - batch latency p50/p95;
  - throughput/samples per second;
  - missing GPU/CPU/RSS telemetry classification.
- Store output written only under governed output/evidence paths and never committed.
- Result classification:
  - `PASS`: Training Store v0 removes the known hot-path decode blocker or reduces it below the accepted threshold with required telemetry present or explicitly waived.
  - Owner-approved `WARN`: bounded store builder is safe and useful, but some telemetry remains missing or performance improvement is partial; all Owners accept the residual risk and PR body preserves draft/request-changes if not merge-ready.
  - `FAIL`: media decode/data wait still dominates or store builder introduces unsafe writes/artifacts.

No compute-node evidence means publication may remain draft/review-only, but merge readiness must be blocked unless the task scope is explicitly narrowed to plan/scaffold-only.

## Scan Plan

Required pre-publication scans:

- Changed-file scope: allow only approved Training Store implementation/tests/docs and existing PR #14 update paths.
- No `AGENTS.md`, unrelated governance, root checkout, protected baseline, or source dataset path changes unless explicitly authorized.
- No dependency specs: `pyproject.toml`, requirements, lockfiles, Makefile dependency behavior, and workflow dependency changes must be absent unless separately approved.
- No generated store/media artifacts:
  - block `*.mp4`, `*.parquet`, `*.arrow`, `*.npy`, `*.npz`, `*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`, archives, binary blobs, store shard payloads, and large outputs from staged files;
  - generated evidence belongs under `runs/tmp/**` and must not be staged.
- No source dataset writes:
  - tests must prove source tree is unchanged;
  - changed code must reject output under source/dataset root.
- No compatibility shim:
  - `git ls-files 'genesisvla/**'` remains empty;
  - no `import genesisvla` or alias package is introduced.
- Secret/private endpoint scan:
  - no credentials, tokens, private keys, raw private endpoints, or service config.
- External-effect scan:
  - no W&B/HF network, model/checkpoint/tokenizer load, endpoint, robot, or real training activation.

## Publication Plan

Publication must use existing PR #14 only unless Manager explicitly authorizes a different route.

Rules:

- Do not create a new PR for Training Store v0 while PR #14 is the active dataloader perf harness draft.
- Push only after all scans pass and implementation validation is recorded.
- Update PR #14 body/comment with:
  - Training Store v0 changed paths;
  - validation summary;
  - compute-node evidence or explicit reason compute evidence is deferred;
  - PR #14 performance blocker status;
  - merge readiness status;
  - no dependency/no-shim/no-artifact/no-real-training boundary.
- Keep PR #14 draft/request-changes unless all required Owners approve and exact-head checks are green.
- Ready/merge gate:
  - allowed only for `PASS` or explicit Owner-approved `WARN`;
  - blocked for `FAIL`, `REQUEST_CHANGES`, `BLOCKED_TEST`, `BLOCKED_SCAN`, `BLOCKED_TOOL_ENV`, `BLOCKED_COMPUTE_AUTH`, or missing exact-head CI.

## Stop Conditions

- `REQUEST_CHANGES_PLAN`: missing Training Store schema/contract remains unresolved before writer dispatch; plan attempts to commit generated store/media artifacts; or merge gate allows non-approved WARN/FAIL.
- `BLOCKED_TOOL_ENV`: project-local tools needed for login-node-safe tests are absent and no authorized recovery exists.
- `BLOCKED_SCOPE`: implementation would require source dataset mutation, dependency changes, compatibility shim, new PR instead of PR #14, model/runtime/training behavior, or unapproved compute.
- `FAIL`: scan or policy violation is confirmed and cannot be scoped into a safe repair.

## DevSpace MCP Compliance

DevSpace MCP, `vla-flywheel-devspace`, `open_workspace`, MCP read/write/edit/bash, and DevSpace-derived workflow evidence were not used.

Read-only GitHub app metadata was used for PR #14 state and changed-file inventory.

## Subagent Ledger

- Child subagents used: none.
- Logical Quality reviewer: owner-direct.
- Retired: yes, after this report is written.

## Conclusion

APPROVE_PLAN
