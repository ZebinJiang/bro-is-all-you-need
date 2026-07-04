# Training Benchmark Harness

The training benchmark harness adds:

```bash
python -m autovla.training.cli benchmark \
  --family gr00t-n1d6 \
  --fixture tiny \
  --steps 8 \
  --warmup-steps 2 \
  --repeats 3 \
  --output-dir <path> \
  --table-format json,csv,md
```

## Outputs

- `performance_raw.json`
- `performance_summary.csv`
- `performance_summary.md`
- `performance_gate_table.md`
- `missing_telemetry_table.md`
- `performance_environment_table.md`

## Runtime Boundary

The harness reuses the merged CPU-only runner dry-run and tiny in-memory
fixture. It does not run real training, read a real dataset, load a real model
or checkpoint, use GPU/CUDA, submit Slurm work, contact W&B or Hugging Face, or
call endpoints or robots.

## Interpretation

The emitted numbers are deterministic synthetic scaffold values. They make
future performance evidence table-shaped, but they are not production
performance measurements.
