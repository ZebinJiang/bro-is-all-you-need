# M6 Runtime Validation

## Status

The final-review candidate was frozen at baseline HEAD
`be841be388018166637ff6f952772141299237c1` with 110 changed paths and status
`BLOCKED_VALIDATION`. The pre-freeze repair/rerun budget had been exceeded. The
single integrated repair cycle did not rerun the consumed broad suite, submit
Slurm jobs, use a GPU, install dependencies, access the network, or mutate a PR.

| Boundary | Frozen evidence | Integrated-repair disposition |
| --- | --- | --- |
| CPU | bounded reduced two-step run completed | preserved; not general runtime readiness |
| one GPU float32 | bounded reduced run completed | preserved; no broader GPU claim |
| DDP | one finite step, then rank RNG gather failed | primitive NumPy RNG encoding repaired and locally round-tripped; two-rank rerun deferred |
| FSDP2 | one finite step, then the same rank RNG gather failed | same source repair; two-rank rerun deferred |
| workers=2 | original RoboDM run failed on `mappingproxy` and leaked IPC resources | focused local spawn test completes two epochs with two observed workers, PID reuse, non-default prefetch, deterministic samples, and clean child exit; three-backend Slurm matrix rerun deferred |
| fresh resume | rejected before apply because operational paths changed identity | canonical semantic projection and a two-process exact-next-sample test added; full CLI next-loss/parameter equivalence rerun deferred |
| focused tests/static | frozen result was 122 passed/4 failed, Ruff I001, strict Pyright 858 | see the integrated-repair report for exact targeted post-repair commands and residual type classification |
| official checkpoint | local authorized assets absent | deferred; no download authorized |
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
must not imply distributed completion, exact full-training resume, official
checkpoint compatibility, model quality, deployment readiness, long-training
stability, or a backend winner.
