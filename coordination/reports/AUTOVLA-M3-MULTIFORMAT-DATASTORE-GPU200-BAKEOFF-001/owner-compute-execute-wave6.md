# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Compute Execute Wave 6

Role: `80-OWNER · Compute/HPC`

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## 2. Exact Benchmark Rerun Wrapper Command And Envelope

Wave 6 reused the packet-authorized reduced benchmark config:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`

Exact wrapper route used:

- `scripts/slurm/request_compute_debug.sh --profile h800-gpu --partition a100 --cpus 16 --mem 64G --gres none --time 01:00:00 --run-id autovla-m3-multiformat-store-benchmark-wave6 -- bash -lc 'set -euo pipefail; /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.dataloader.stores run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml; echo STORE_BENCHMARK_OK'`

Resolved benchmark envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `none`
- time: `01:00:00`

Wrapper evidence:

- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark-wave6/logs/srun_command.txt`

## 3. Whether Rerun Benchmark Launched And Completed

Yes.

Wave 6 reran the reduced real benchmark after the Wave 5 camera-ref repair, and
the benchmark completed successfully.

Completion marker:

- wrapper command returned success and emitted `STORE_BENCHMARK_OK`

Benchmark output root:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark`

Primary output files produced:

- `load-benchmark.json`
- `load-benchmark.csv`
- `load-benchmark.md`
- `generated-artifact-ledger.json`

## 4. Benchmark Output Root And Candidate Rows

Shared manifest result:

- checksum: `abf0570cf1572121b4e590473221a1188ee85b284af0e3074994009dc2d16048`
- sample count: `2048`
- episode count: `8`

Candidate rows from `load-benchmark.md` / `load-benchmark.json`:

| candidate | status | prototype | p50 ms | p95 ms | samples/s | artifact bytes | files | note |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `zjh_lerobot_v21_raw` | `PASS` | `False` | `0.617414` | `0.692063` | `407834.958143` | `136983` | `1` | read-only raw baseline |
| `zjh_lerobot_v3_local` | `PASS` | `False` | `7.195522` | `7.978959` | `34767.042144` | `11079622` | `2051` | AutoVLA-native local LeRobot v3-style artifact and reader |
| `zjh_webdataset_tar` | `PASS` | `False` | `18.074306` | `23.766687` | `14822.240436` | `22526219` | `18` | webdataset tar shards built and read through approved package route |
| `zjh_robodm_container_v1` | `PASS` | `True` | `77.962236` | `90.783264` | `3216.960398` | `14215468` | `18` | AutoVLA-owned RoboDM-style prototype container |

## 5. Runnable Candidate Set

Wave 6 derived the minimum telemetry matrix as:

1. `zjh_lerobot_v21_raw`
2. `zjh_lerobot_v3_local`

Why this was the correct minimum matrix:

- `zjh_lerobot_v21_raw` is the overall benchmark leader and required raw baseline.
- `zjh_lerobot_v3_local` is the best non-raw candidate.
- `zjh_webdataset_tar` was the next candidate, but it was not within 10 percent
  of `zjh_lerobot_v3_local` on either required comparison surface:
  - samples/s ratio: `14822.240436 / 34767.042144 = 0.4263`
  - p95 ratio: `23.766687 / 7.978959 = 2.9787`
- `zjh_robodm_container_v1` ranked below the second-best candidate and was
  therefore outside the minimum matrix.

## 6. Exact Telemetry Jobs Attempted

Wave 6 wrote task-local bridge configs under the allowed packet scope:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v21_raw.yaml`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v3_local.yaml`

Both configs passed:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.training.telemetry validate-config --config ...`

Wave 6 then launched the two minimum-matrix telemetry jobs through the approved wrapper.

### Raw baseline attempt

Exact wrapper command:

- `scripts/slurm/request_compute_debug.sh --profile h800-gpu --partition a100 --cpus 16 --mem 64G --gres gpu:1 --time 01:00:00 --run-id autovla-m3-multiformat-gpu200-wave6-raw -- bash -lc 'set -euo pipefail; export PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17; /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.training.telemetry bridge-run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v21_raw.yaml; echo TELEMETRY_OK'`

Output roots:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/raw/outputs`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/raw/logs`

Bridge result:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/raw/outputs/bridge_runtime_result.json`
- `returncode: 1`

Observed failure:

- Isaac launched, loaded the model, started dataset statistics generation, then failed with:
  - `FileNotFoundError: [Errno 2] No such file or directory: '/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz/meta/modality.json'`

### Best non-raw attempt

Exact wrapper command:

- `scripts/slurm/request_compute_debug.sh --profile h800-gpu --partition a100 --cpus 16 --mem 64G --gres gpu:1 --time 01:00:00 --run-id autovla-m3-multiformat-gpu200-wave6-zjh-lerobot-v3-local -- bash -lc 'set -euo pipefail; export PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17; /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.training.telemetry bridge-run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v3_local.yaml; echo TELEMETRY_OK'`

Output roots:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/zjh_lerobot_v3_local/outputs`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/zjh_lerobot_v3_local/logs`

Bridge result:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/zjh_lerobot_v3_local/outputs/bridge_runtime_result.json`
- `returncode: 1`

Observed failure:

- Isaac launched, loaded the model, started dataset initialization for the generated candidate root, then failed with:
  - `FileNotFoundError: [Errno 2] No such file or directory: '/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local/meta/info.json'`

## 7. Telemetry Rows Completed Vs Not Run

Attempted telemetry rows:

- `zjh_lerobot_v21_raw`: `ATTEMPTED_FAIL_MISSING_META_MODALITY_JSON`
- `zjh_lerobot_v3_local`: `ATTEMPTED_FAIL_MISSING_META_INFO_JSON`

Not-run telemetry rows:

- `zjh_webdataset_tar`: `NOT_RUN_MINIMUM_MATRIX_SECOND_BEST_OUTSIDE_10_PERCENT`
- `zjh_robodm_container_v1`: `NOT_RUN_MINIMUM_MATRIX_RANKED_BELOW_REQUIRED_SET`

Completed successful 200-step telemetry rows:

- none

## 8. Exact Remaining Blocker

Wave 6 did not hit a scheduler-policy or wrapper-env blocker.

The compute route worked as intended:

- reduced benchmark launched and completed
- both telemetry wrapper launches reached the compute node
- both telemetry runs created bounded runtime outputs and logs

The remaining blocker is scope-level dataset-contract compatibility between the
current candidate dataset surfaces and the Isaac GR00T runtime:

- raw baseline path lacks required `meta/modality.json`
- generated `zjh_lerobot_v3_local` path lacks required `meta/info.json`

This means the current benchmark-winning datastore surfaces are not yet
drop-in Isaac training dataset roots for the bounded Wave 6 bridge route.
Progressing past this point requires new source/data-artifact work to produce or
adapt the GR00T-required metadata surface, which is outside the allowed write
scope of this compute execute wave.

## 9. Job IDs Or Explicit `unknown_debug_wrapper_no_job_id`

- benchmark run id: `autovla-m3-multiformat-store-benchmark-wave6`
- benchmark job id: `unknown_debug_wrapper_no_job_id`
- raw telemetry run id: `autovla-m3-multiformat-gpu200-wave6-raw`
- raw telemetry job id: `unknown_debug_wrapper_no_job_id`
- best non-raw telemetry run id: `autovla-m3-multiformat-gpu200-wave6-zjh-lerobot-v3-local`
- best non-raw telemetry job id: `unknown_debug_wrapper_no_job_id`

The approved debug wrapper recorded exact `srun` commands and run directories,
but did not emit stable scheduler job ids into the task-owned evidence roots.

## 10. DevSpace MCP Compliance

- DevSpace MCP used: no

## 11. Subagent Retirement Ledger

- child subagents used: none
- write-capable child subagents used: none
- no parallel write: yes
- retired: yes

## Conclusion

`BLOCKED_SCOPE`

Reason:

Wave 6 completed the benchmark rerun and derived the correct minimum telemetry
matrix, and the approved compute wrapper route remained healthy. However, the
two required telemetry attempts both failed on GR00T dataset-surface
requirements (`meta/modality.json` for raw, `meta/info.json` for
`zjh_lerobot_v3_local`). Advancing further now requires new source or
candidate-artifact work to satisfy the Isaac dataset contract, which is outside
this compute-only wave.
