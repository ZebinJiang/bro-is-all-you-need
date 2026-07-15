# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Training Execute Packet

## Role

You are `20-OWNER · Training`.

This tranche starts only after Data write completion is present in the worktree.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Do not create child write-capable subagents.
No parallel source writes.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`

## Allowed write scope

- `autovla/training/telemetry/**`
- `configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
- `scripts/slurm/autovla_gr00t_gpu200_multiformat.sh`
- `tests/training/**`
- `docs/benchmarks/**`
- `README.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute.md`

Do not write:

- `autovla/dataloader/stores/**`
- `requirements/**`
- `pyproject.toml`
- `Makefile`

## Training tranche intent

Implement the bounded offline/compute-ready telemetry surface only:

- per-step and aggregate GR00T GPU200 telemetry schemas
- nvidia-smi sampler
- CPU/IO sampler
- report/table rendering
- Slurm wrapper/config for later governed compute runs
- README and docs/benchmarks numeric table integration surfaces

This tranche must not:

- claim real model compatibility from local metadata alone
- enable W&B online sync
- enable HF network
- perform long training
- add endpoint/robot/deployment behavior

Use direct root project-local toolenv commands for local validation.
