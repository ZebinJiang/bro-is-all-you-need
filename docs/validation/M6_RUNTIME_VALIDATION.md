# M6 Runtime Validation

## Status

The W9 consolidated governance repair records the current prepublication
posture. Every non-President Owner, worker, and Manager-facing return uses
`gpt-5.6-sol / medium`; only the President Manager uses
`gpt-5.6-sol / xhigh`. W8 passed the full suite with 737 tests, runtime
isolation 40/40 twice, Black, Ruff, strict Pyright, package gates, and scans.
Post-repair independent validation must create the next authoritative freeze.

| Boundary | Current evidence | Disposition |
| --- | --- | --- |
| CPU | bounded reduced run | PASS; not general runtime readiness |
| one GPU | bounded reduced run | PASS; no broader GPU claim |
| fresh resume/isolation | independent bounded runs | PASS |
| runtime command isolation | 40/40 in two distinct roots | PASS twice |
| standard DDP 3076 | finite work/checkpoints and clean teardown | PASS |
| standard DDP 3082 | finite work/checkpoints and clean teardown | PASS |
| standard FSDP2 3077 | completed work/checkpoints, then leaked semaphores | FAIL teardown |
| standard FSDP2 3083 | worker `SemLock._rebuild` failure | FAIL startup and teardown |
| traced FSDP2 3088 | completed under ptrace timing perturbation | diagnosis only; not acceptance |
| quality/package | 737 passed; Black/Ruff/Pyright/package/scans passed | PASS for bounded candidate gates |
| official checkpoint | local authorized assets absent | `deferred_local_asset_absent` |
| upstream numerical parity | oracle runtime/assets absent | deferred |
| backend choice | no winner selected | `NO_BACKEND_WINNER` |

PyAV-dependent LeRobot media remains an optional-runtime limitation when PyAV
is absent. The physical LeRobot evidence remains the bounded
`[8] -> [1,8] -> [16,8]` action-shape path. Backend close counters cannot be
reported from already-exited worker processes through the current immutable
batch contract; local tests prove parent-observed worker exit and expose only
the backend open/cache state delivered before close. No invented close telemetry
or throughput winner is reported.

## Reproduction Surface

The tracked matrix is `configs/runtime/m6-runtime-matrix.yaml`. The request
generator and renderer remain local-only, offline, and bounded to two steps:

```bash
python scripts/runtime/generate_m6_reduced_runtime.py --help
python scripts/runtime/render_m6_runtime_command.py --help
python scripts/runtime/run_m6_runtime_request.py --help
```

GPU, DDP, and FSDP2 requests must continue through the governed project Slurm
wrapper after separate authorization. This page does not authorize submission,
official assets, endpoints, robots, long training, or deployment.

## Publication Boundary

M6 remains a stacked open draft. It is not merge-ready or production-ready and
must not imply standard FSDP2 completion, exact full-training resume, official
checkpoint compatibility, model quality, deployment readiness, long-training
stability, or a backend winner. W7R8 recovered no first-unlink actor and
authorizes no source repair. Only `PARTIAL` draft publication is allowed; no
production PASS, ready transition, merge, or retarget is authorized.
