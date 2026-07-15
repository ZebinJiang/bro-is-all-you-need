# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Data-W3 Docs

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- Worktree-local `runs/tmp/m1-tool-venv` is absent; validation used the root project-local toolenv at `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv`.

## Files Changed

- `README.md`
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
- `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w3-docs.md`

No source, tests, configs, dependencies, Makefile, pyproject, requirements, compute evidence, datasets/readonly, or datasets/working generated artifacts were modified in this docs wave.

## Final Ranking And Decision Status

Compute-W2 evidence is reflected as the bounded PR #30 final runnable-candidate ordering:

| Rank | Label | Candidate | samples_per_sec | total_batch_ms | actual_workers | status |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | D4 | `zjh_webdataset_tar` | 501.775424 | 8163.014375 | 8 | `RUN` / `PASS` |
| 2 | D5 | `zjh_robodm_container_v1` | 295.03279 | 13883.202613 | 8 | `RUN` / `PASS` |
| 3 | D3 | `zjh_lerobot_v3_local` | 203.022981 | 20175.055925 | 8 | `RUN` / `PASS` |
| 4 | D1b/D2 | `zjh_lerobot_v21_autovla_adapter` | 24.7923 | 165212.583614 | 8 | `RUN` / `PASS` |

Non-runnable/non-ranked rows remain explicit:

- D1a `zjh_lerobot_v21_gr00t_or_lerobot_native`: `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.
- D6 `zjh_zarr_cache`: `NOT_IMPLEMENTED_IN_CURRENT_PR`.

Decision status used in README/docs:

- `NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS`
- `REQUEST_CHANGES_REMAIN`
- `NO_BACKEND_WINNER`

The docs do not claim final backend winner, training format selection, fine-tune readiness, model quality, deployment readiness, production readiness, or full prompt-contract closure.

## Evidence Paths Reflected

- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-w2.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-compute-benchmark-w2.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_raw.json`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_summary.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/backend_decision_table.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/missing_telemetry_table.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/worker_evidence_table.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/payload_completeness_table.md`

The source mutation hash is preserved in docs:

`36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`

## Publication Note

`docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md` was created as requested, but the repository currently ignores new Markdown files through `.gitignore:235` (`*/**/*.md`). It is therefore shown as ignored (`!!`) until Quality publication explicitly handles it, for example by force-adding the intended new doc or choosing another PR-visible tracked surface. To avoid a tracked broken link, README links the already tracked `ACTUAL_DATALOADER_WORKER_BAKEOFF.md` and mentions the final evidence draft path in code formatting.

## Validation Commands And Results

- `test -x runs/tmp/m1-tool-venv/bin/python`: no worktree-local venv.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader tests/meta -v`: PASS, `255 passed`.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: sticky/no output after 60s, interrupted with exit `130`; file-by-file fallback used.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright -p pyrightconfig.genesisvla.json`: FAIL because `pyrightconfig.genesisvla.json` does not exist in this worktree; pyright then fell back to broad environment-unaware analysis and reported missing environment imports.
- Substitute project-local check: `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS, `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: PASS.
- Documentation overclaim scan: PASS. Grep hits for `training readiness`, `model quality`, and `selected as winner` are negated/caveated wording; no active winner/training/GPU200/model/deployment/production readiness claim was found.

## Compliance

- DevSpace MCP: no.
- Subagents: none used; retired yes.
- Stage/commit/push/PR mutation: no.
- Compute/Slurm run by Data-W3: no.
- Source/tests/config/dependency/Makefile/pyproject/requirements/.github/AGENTS.md edits: no.
- `datasets/readonly/**` mutation: no.
- `runs/tmp/**` evidence mutation: no.
- `datasets/working/**` generated artifact mutation: no.

## Conclusion

PASS_DOCS_READY_FOR_FINAL_REVIEWS
