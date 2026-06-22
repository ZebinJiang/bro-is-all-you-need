# Slurm Environment Discovery

## Purpose

When `configs/slurm/default_sandbox.json` contains `TO_FILL`, the Manager must discover the cluster name, available partitions, resource shapes, and candidate default partition before formal Slurm submission.

## Trigger

Run discovery when any active Slurm config has:

```json
"approved_cluster": "TO_FILL"
"partition": "TO_FILL"
```

Once those fields are filled, do not refresh them unless the user explicitly asks for a Slurm config update.

## Command

```bash
python3 -S scripts/slurm/discover_slurm_environment.py \
  --config configs/slurm/default_sandbox.json \
  --run-id slurm-discovery-<yyyymmddhhmmss> \
  --write-config
```

The script writes an inventory under:

```text
runs/slurm_inventory/<run_id>/outputs/slurm_inventory.json
runs/slurm_inventory/<run_id>/logs/commands.log
```

## Allowed discovery operations

Allowed:

- `sinfo` for partition/node inventory;
- `scontrol show config` for cluster identity;
- `scontrol show partition` for partition details;
- `sbatch --version` and `srun --version`;
- reading the current project Slurm config.

Disallowed:

- modifying cluster config;
- changing partitions/QoS/accounting;
- inspecting private job details;
- cancelling or requeueing jobs;
- bypassing resource limits.

## Config update rule

The script may write the config only when the current config still contains `TO_FILL`, or when the user explicitly requested a refresh and the Manager passes the script's force flag. The Manager must record the discovery run id and the resulting config values in `.agent-docs/progress.txt`.
