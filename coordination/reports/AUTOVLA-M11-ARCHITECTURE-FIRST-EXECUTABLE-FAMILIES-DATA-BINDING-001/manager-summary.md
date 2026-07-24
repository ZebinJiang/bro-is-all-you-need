# AUTOVLA-M11 Manager Summary

## Conclusion

`PARTIAL_EXECUTABLE_MODEL_FAMILIES_GPU_RUNTIME_DRAFT_PUBLISHED`

M11 has published one stacked Draft PR for source and contract review. It is
not merge-ready and M11 remains incomplete because the accepted runtime,
license, asset, physical-data, and compute gates are unresolved.

## Publication Identity

- PR: <https://github.com/ZebinJiang/bro-is-all-you-need/pull/37>
- State: OPEN / Draft / DO NOT MERGE
- Base branch: `dev/feat-autovla-production-model-zoo-gr00t-n1d7-pi05`
- Base SHA and PR #36 head: `1411ef66f94da7598d71c71bf940f06c220c2edc`
- Head branch: `dev/feat-autovla-executable-families-data-binding`
- Implementation commit: `82047382739ee93c6e43eebbcabaf314b3cbe573`
- Final PR head: the control-plane closure commit containing this report; its
  exact SHA is recorded in the ignored task summary and verified PR body after
  push because a commit cannot contain its own SHA.
- Merge, ready transition, force push, branch deletion, and cleanup: not run.

At publication-time live inspection, PR #30 remained OPEN/Draft on `main` at
`3ae30f414dd931d9b8aba22080b08c4e530e63de`. PR #36 remained OPEN/Draft at
`1411ef66f94da7598d71c71bf940f06c220c2edc` and was not merged or retargeted.
Its disposition remains `PR36_MERGE_DEFERRED_BY_REPOSITORY_POLICY`.

## Delivered Architecture

The active zoo remains exactly:

- `gr00t_n1d6`
- `gr00t_n1d7`
- `pi0_5`

The candidate adds or hardens:

- immutable backend, dataset, config, manifest, schema, source, store, and
  ordered-record provenance receipts;
- fail-closed dataset-to-family binding with per-record identity validation;
- packaged read-only runtime-profile descriptors and checkout-independent
  `autovla-env list/inspect`;
- explicit checkout ownership for create, verify, and exec operations;
- transactional environment creation with atomic publication and bounded
  failure receipts;
- N1D7 CPU metadata audit, exact index/physical-source equality, and bounded
  streaming mutation with a 64 MiB simultaneous checkpoint-payload ceiling;
- typed stable model CLI errors;
- strategy-owned ZeRO-3 initialization and checkpoint boundaries;
- device-side token telemetry accumulation until flush/checkpoint boundaries;
- canonical documentation aligned with the implemented limits and non-claims.

No additional model family was promoted. LeRobot, WebDataset, and RoboDM remain
first-class data backends, and the literal result remains `NO_BACKEND_WINNER`.

## Family And Runtime Status

### GR00T N1.6

- Source architecture: executable source contract retained.
- Asset status: `PASS_ASSET_READY` based on historical strict-load evidence.
- Runtime profile: requests Torch 2.7.1 and DeepSpeed 0.19.2.
- Blocker: the preserved lock resolves Torch 2.6.0 and omits DeepSpeed; no
  accepted replacement lock/fingerprint exists.
- Runtime: no M11 CUDA, forward, backward, update, resume, DDP, ZeRO, or
  cross-node execution; compatible C3 data remains unavailable.

### GR00T N1.7

- Source architecture: family-owned PyTorch source and bounded strict
  checkpoint adapter.
- Blocker: checkpoint/Cosmos terms receipts, exact runtime versions, accepted
  lock, and executable checkpoint assets remain unresolved.
- Runtime: no checkpoint load, CUDA, training, distributed, or conformance
  claim.

### Pi0.5

- Source architecture: clean AutoVLA PyTorch path with isolated conversion
  boundary.
- Blocker: Gemma/checkpoint/tokenizer/normalization/conversion receipts and
  accepted runtime/conversion locks remain unresolved.
- Runtime: JAX, Flax, and Orbax are prohibited from the production runtime;
  no conversion, checkpoint load, CUDA, training, distributed, or conformance
  claim.

## Data Truth

The bounded dataset surface remains metadata-only: 72 state values, 98 action
values, three cameras, and 30 Hz. Units, frames, ordering, history, horizon,
normalization, and embodiment are unresolved. Compatibility therefore fails
closed and `real_sample_read=false`. No real dataset sample was opened.

## Reference Reuse Decision

- NVIDIA GR00T N1.6.1 source pin:
  `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`; restrictive non-commercial
  research terms, with source and weights treated separately.
- NVIDIA GR00T N1.7 source pin:
  `9c7e746b2cd37a810070a98ef41d290a07e806c2`; checkpoint revision
  `2fc962b973bccdd5d8ce4f67cc63b264d6886495`; Apache-2.0 code while
  checkpoint/Cosmos terms remain unresolved.
- OpenPI pin: `15a9616a00943ada6c20a0f158e3adb39df2ccac`;
  Apache-2.0 source while Gemma and weight terms remain separate/unresolved.
- DeepSpeed pin: `b919284ab1ad6dbc1cb0e06b10386ff74160b586`;
  v0.19.2 Apache-2.0 public API dependency.
- StarVLA pins: `3422b9f2387b6f682cf02802904a77b23ab13afd` and
  `236f584ef603817e019b002924b2506a71311f2b`.
- Dexbotic, FluxVLA, VLA Foundry, LeRobot, and WebDataset were retained in the
  governed source map as design/contract references.

Reuse is selective and adapter-oriented. No whole upstream tree, model weight,
tokenizer, dataset, or checkpoint was copied. License/weight uncertainty is a
hard runtime and publication-readiness gate, not an implied approval.

## Review And Repair

Exactly one fresh final review swarm ran with four read-only agents:
Architecture, complexity, parallel efficiency, and readability. The swarm
returned four P1 and three material P2 findings. Manager integration added five
bounded findings covering test-helper identity/formatting, exact checkpoint
source accounting, documentation truth, independent strict typing, and a type
suppression.

All accepted findings were repaired by 12 fresh bounded writers. Every writer
and reviewer was collected and retired. No second final review swarm ran;
Manager post-repair acceptance replaced it as required by the task contract.

Final routing evidence:

- ledger records: 127
- child events: 110
- non-child events: 17
- final review agents: 4
- active children: 0
- routing validator: PASS
- model/reasoning: `gpt-5.6-sol` / `medium` for task children
- persistent Owner fanout: disabled
- DevSpace MCP: not used

## Validation

- Dependency-safe changed-path matrix: 137 passed.
- Black API over the exact 22 changed Python files: PASS.
- Ruff: PASS.
- Redirected `py_compile`: PASS.
- Strict Pyright: 493 diagnostics, all confined to seven Torch/Transformers
  dependent files in a project-local environment without those optional
  packages; independent candidate diagnostics: 0.
- JSON/TOML parsing: PASS.
- Added ignore/noqa/Any suppression scan: zero findings.
- `git diff --check`: PASS.
- Secret, model-asset, large-file, large-text, artifact-extension, generated
  output, and forbidden-path scans: PASS.
- Full stacked branch range: 120 changed paths, no governed artifact or
  `runs/`, `base_model/`, dataset, checkpoint, or model-weight publication.
- Optional gitleaks: not installed, skipped explicitly.

Canonical package build is `BLOCKED_TOOL_ENV`: the project-local wheelhouse
does not contain the pyproject-pinned `setuptools==77.0.3`, and installation or
network access was not authorized. A clearly marked non-canonical
package-content build using the already available setuptools 80.9.0 with no
isolation and skipped dependency checking passed. Its wheel had 389 entries,
its sdist had 469 entries, archive scans passed, and a clean task-local no-deps
wheel install successfully ran `autovla-env list/inspect` outside the checkout.
This evidence is not represented as the canonical build gate.

## External Effects And Non-Claims

- Slurm submissions: 0.
- A100 GPU-hours: 0.
- No environment, dependency, global/system Python, or lock was modified.
- No checkpoint, tokenizer, model weight, base-model shard, or dataset was
  opened, downloaded, hashed intentionally, staged, or committed by this task.
- No network runtime, `trust_remote_code`, arbitrary pickle, GPU, Slurm, W&B,
  Hugging Face upload, endpoint, robot, or real training action occurred.
- The observed transient root `git hash-object` PID was not launched by an
  explicit Manager command; it had exited before its parent chain could be
  inspected. M11 publication work stayed in the canonical worktree and avoided
  root `base_model/` scans.
- This Draft does not claim production support, numerical parity, model
  quality, real-data compatibility, distributed readiness, or measured
  performance.

## Rollback

Keep PR #37 Draft and unmerged. To abandon the publication, close the Draft PR
without deleting branches or worktrees, then retain the implementation and
control-plane commits for audit. Do not delete task evidence without a separate
authorized cleanup proposal.

## Recommended Next Action

Review PR #37 as a stacked Draft only. A later authorized task must resolve the
exact runtime locks, license/asset receipts, compatible physical data, canonical
build tool environment, and compute-node validation before any executable GPU
runtime or merge-ready claim. M11 remains active and incomplete.
