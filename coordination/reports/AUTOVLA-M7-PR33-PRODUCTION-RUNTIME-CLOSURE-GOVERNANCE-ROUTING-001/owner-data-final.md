# Data Owner Final Review

`BLOCK`

## Finding

### [CRITICAL] Frozen candidate content identity drifted

- **Path/symbol:** `coordination/tasks/active/AUTOVLA-M7-PR33-PRODUCTION-RUNTIME-CLOSURE-GOVERNANCE-ROUTING-001.yaml` / frozen manifest entry.
- **Evidence:** Independent recomputation from the manifest-defined framing over all 105 ordered paths produced content-stream SHA256 `47bdfbe14e3806c3a1cd92a32897deb41f3d0037875e7d6051a71eb420b78a76`, not frozen `490da6571b170f95c0beec23af8e477e426bd68722c0bc211c017796f8d4a789`. This is the sole per-path mismatch: frozen SHA/size `1c987d06a726a324d750f6936b49a32dfa91dd5c66164df46c8ac7ba7c2fa903` / 4,572 bytes; current SHA/size `93eb2fec6db8e164183c8d74757f137d12b59644a95f1ae38f7a070d3fae0958` / 4,538 bytes. Manifest-file SHA `fd5d58768cdeccf2a0fd8b674830839160363a97e3b13004a2771929aae850c3`, 105-path-list SHA `6773e2f54c2f317d56030740d8aab75b35a31992efdaf431cdabe488d919d947`, tracked binary-diff SHA `b588b29ffbfe5584f54d239b6c5a828bfea1cc5b453dda40d7ec602e6b9ea0aa`, and empty index SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` otherwise match.
- **Acceptance condition:** A newly frozen, internally consistent packet must bind the exact reviewed 105-path content (including the task card), and the final Owner fan-out must consume that stable identity.
- **Impact:** Blocks partial publication from this packet and blocks all later readiness/ready/merge claims. This is an identity gate, independent of the otherwise supportable honest `PARTIAL_COMPUTE_RUNTIME` posture.

## Data Boundary Assessment

Subject to stable refreeze, no additional Data Owner defect was found in the reviewed data surface. `WorkerEpochState` uses an anonymous `RawArray` version protocol with bounded fail-closed snapshots; tests cover coherent parent/worker publication, uint64 boundaries, spawn/forkserver pickling, and absence of named shared-memory/resource-tracker bypasses. `TrainingDataLoader` validates source/schema fingerprints, assignment digests, committed cursors, stream RNG state, worker count, and temporal/normalization identity before applying resume state; workers=0 and workers=2, persistent PID reuse, exception/partial-start cleanup, two concurrent rank-like parents, and fresh-process exact-next-sample resume are exercised. WebDataset finite cursor/state/fingerprint, local LeRobot deterministic identity and optional live PyAV ownership/close behavior, and RoboDM ordering/provenance/content fingerprinting preserve finite identity without source mutation. `NO_BACKEND_WINNER` remains explicit.

The FSDP2 disclosure must remain exact: standard DDP 3076 and 3082 passed with two workers per rank and clean teardown; standard FSDP2 3077 completed two steps/checkpoints but failed teardown with 28 missing-name finalizers and two groups of 14 leaked semaphores; standard FSDP2 3083 failed four worker `SemLock._rebuild` operations before data delivery and then teardown; traced 3088 completed only under ptrace and is diagnosis-only. W7R8 recovered no first successful unlink actor, so neither an AutoVLA source cause nor an environment cause is established and no source repair is authorized. There is no standard untraced FSDP2 lifecycle pass; production PASS/readiness/merge remain unavailable.

## Identity And Scope

- Workspace/root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-production-data-plane-gr00t-runtime`
- Branch: `dev/feat-autovla-production-data-plane-gr00t-runtime`
- HEAD: `b63be4470c4fddb2d44ca36ae926710e7bd2b4ff`
- Index: empty
- Descendants: none
- DevSpace MCP: not used
- Writes: this report and its assigned JSON companion only

Retirement-ready: yes.
