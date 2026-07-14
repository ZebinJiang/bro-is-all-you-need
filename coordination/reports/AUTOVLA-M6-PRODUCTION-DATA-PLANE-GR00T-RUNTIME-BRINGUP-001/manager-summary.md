# AUTOVLA M6 Manager Summary

## Conclusion

`PARTIAL_M6_PRODUCTION_DATA_RUNTIME_DRAFT_PUBLISHED`

The exact 115-path M6 candidate was published as stacked draft PR
`https://github.com/ZebinJiang/bro-is-all-you-need/pull/33` at feature commit
`b63be4470c4fddb2d44ca36ae926710e7bd2b4ff`. It remains open, draft,
unmerged, and targets `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`.
Parent PR #30 remains open/draft/unmerged at
`be841be388018166637ff6f952772141299237c1`.

This is a partial publication, not acceptance. The package/build path and all
three actual workers=2 backend jobs pass. DDP/FSDP2 write valid step-1
checkpoints but fail at step 2 on missing shared-memory descriptors; fresh
resume fails on JSON-list versus dataclass-tuple `data_manifest`; eight focused
tests fail on retained fixed fixture directories; Black fails two paths; strict
Pyright remains non-green; the broad suite was not rerun; tracked runtime docs
remain a pre-Compute snapshot. PR #33's body enumerates each failure and is
marked `DRAFT / DO NOT MERGE`.

## Stack

- PR #32 initial head: `3a93100777e69e30e6d2f9a0ec5d549bfdb47849`
- PR #32 stacked merge commit: `be841be388018166637ff6f952772141299237c1`
- PR #30: `OPEN`, draft, base `main`, head `be841be...`, unmerged
- M6 branch: `dev/feat-autovla-production-data-plane-gr00t-runtime`
- M6 PR #33: `OPEN`, draft, `UNSTABLE`, unmerged
- M6 PR base/head: PR #30 branch -> M6 branch at `b63be447...`
- no force/direct-main push, retarget, ready transition, merge, or deletion

## Candidate And Publication

- candidate paths: `115`
- path-list SHA256: `d929f9a3705ee83d666b49a563c34952e0be6315096302d5db7493bc0a419e1b`
- path/content SHA256: `4c53a4147d29df7673b8ce0385eef6ee87af5d47ddabf592cbb0a7cefc56b1ed`
- candidate diff SHA256: `db7ab56c88caca37fba3dc1042631b949855c8fdd75ebcb1edce1869fa290381`
- exact manifest staging: PASS, 115/115 paths
- commit/push: PASS, no force
- secret/private endpoint/artifact/binary/cache/large-file/protected-path/dependency/license scans: PASS
- optional gitleaks: not installed, skipped

## Package

- distribution/version: `autovla==0.1.0.dev0`
- base dependencies: `numpy`, `omegaconf`
- package identity, wheel/sdist, clean install, `pip check`, entrypoints,
  `py.typed`, packaged configs, Torch-lazy import, license/notice/archive scans:
  PASS
- wheel SHA256: `b9c769c9264681723e6b19716b5c586b797669967269f6b5e0124b04e98928b2`
- sdist SHA256: `6b30e130f919c407b9d6d6128b6e7516b3c86a6cc8f5a93c6b3f334f1880ac7f`
- no lockfile, global, Conda, or system dependency mutation

## Data Plane And Backends

- canonical real PyTorch DataLoader map/stream route implemented
- worker/rank partition, seed, prefetch, persistence, pin/timeout, grouped
  reads, lifecycle, provenance, and checkpointable state implemented
- WebDataset workers=2 job `2814`: PASS, two epochs/stable PIDs/exact IDs/clean close
- LeRobot workers=2 job `2815`: PASS, persistent parquet/cache reuse/clean close
- RoboDM workers=2 job `2816`: PASS, persistent handles/cache reuse/clean close
- PyAV media remains optional/unproved
- no upstream-native RoboDM or performance claim
- `NO_BACKEND_WINNER`

## Model Training And Checkpoint Runtime

- production GR00T processor/Eagle/backbone/action-head/model/factory/engine path used
- bounded CPU and float32 GPU source path executed
- official local checkpoint absent; no download; full parity deferred
- primitive 624-int MT19937 checkpoint transport repair proved through live
  distributed step-1 checkpoints
- baseline job `2817`: PASS
- resume job `2818`: FAIL `data_manifest` list/tuple compatibility
- DDP `2810`: step-1 checkpoint PASS; step-2 shared-memory descriptor FAIL
- FSDP2 `2811`: step-1 checkpoint PASS; step-2 shared-memory descriptor FAIL
- clean two-step distributed teardown not proved

## Quality

- compatibility: `31 passed`
- configured collection: `635`
- focused: `129 passed, 8 failed, 1 warning`
- eight failures: retained fixed-fixture `FileExistsError`
- Ruff/compile/Bash/structured parse/Git diff/package/security: PASS
- Black: FAIL two paths
- repaired-path Pyright: FAIL 69
- repository Pyright: FAIL 822, including 291 unchanged legacy diagnostics
- broad suite: consumed once pre-repair, not rerun
- source dataset unchanged: 3,076 files, 1,130,738,062 bytes,
  SHA256 `96a695a2c0cab0545323a1ea4dc405c9797ddd5d376ead1e3f04ba75a0ca3f17`

## Reuse And License

- WebDataset: public API integration, BSD-3-Clause, no source copy
- LeRobot/RoboDM/VLA Foundry: architecture or format references only
- FluxVLA/Dexbotic: absent-archive metadata references only
- StarVLA: MIT base lineage, not AutoVLA package/runtime identity
- NVIDIA Isaac-GR00T pin `5dc80c4a...`: isolated adapted/reimplemented
  boundary with complete NVIDIA license and immediate MIT/Apache notices
- no weights, tokenizer assets, datasets, upstream clone, remote code, or
  upstream `gr00t` runtime published
- NVIDIA non-commercial-research and prohibited-use terms remain residual risk

## Governance And Threads

- no Owner review before freeze
- exactly one six-scope final Owner fanout; all six `REQUEST_CHANGES`
- one consolidated repair ledger
- exactly one Integrated-Repair-W1
- one targeted Compute-W1
- no post-repair Owner rereview
- one Publication-W1
- repair `019f5233-cdc7-78a2-8d2c-5ffd749d5d8e`, compute
  `019f5261-0d14-74b1-a228-66cf197fd16e`, and publication
  `019f530b-e238-7232-b273-fa18226728c3`: completed/collected/closed/retired,
  no descendants
- all research and implementation thread IDs/returns are indexed in
  `runs/tmp/.../thread-routing.json`
- historical medium/max routing is recorded; after the installed governance
  override, final Owner/repair/compute/publication used `xhigh` and no new
  active `max` dispatch occurred
- no parallel tracked writes; no parallel compute or publication writers
- DevSpace MCP: not used by any stage; evidence dependency: none; PASS

## Rollback And Next Action

No rollback was performed. An authorized rollback can revert feature commit
`b63be4470c4fddb2d44ca36ae926710e7bd2b4ff` on the M6 branch and close PR #33;
force push, deletion, closure, retargeting, merge, and cleanup need separate
authorization.

Do not merge PR #33. The next user/ChatGPT review should decide whether to
authorize a bounded follow-up repair for shared-memory lifecycle, resume
canonicalization, eight fixture collisions, two Black paths, candidate-owned
Pyright diagnostics, and final tracked runtime-status docs. Do not rerun the
six Owners, start long training, or select a backend winner.

Full task-local detail is in:

`runs/tmp/AUTOVLA-M6-PRODUCTION-DATA-PLANE-GR00T-RUNTIME-BRINGUP-001/manager-summary.md`
