# DataBackend Bakeoff Foundation

This tranche adds a metadata-only DataBackend bakeoff foundation for local review.

## Scope

- Typed backend contracts for synthetic, raw_zjh, lerobot_local, and webdataset_tar.
- Bounded local probes for JSON/JSONL metadata, LeRobot `meta/info.json`, and tar member metadata.
- Stable bakeoff tables for probe matrix, preview, latency, IO, source mix,
  batch balance, action family schema, missing telemetry, environment, and
  reuse/license review.

## Non-goals

- No real training.
- No model, checkpoint, tokenizer, GPU, Slurm, W&B, Hugging Face, endpoint, or robot action.
- No dataset download, copy, conversion, cache mutation, media read, media decode, or tar extraction.
- No dependency change.

## CLI

```bash
python -m autovla.dataloader.perf bakeoff \
  --backend synthetic,raw_zjh,lerobot_local,webdataset_tar \
  --input-root <local-path> \
  --max-samples 64 \
  --max-files 256 \
  --max-bytes-read 1048576 \
  --output-dir <output-dir> \
  --table-format json,csv,md \
  --allow-missing-input-root
```

## Output Files

- `backend_bakeoff_raw.json`
- `backend_bakeoff_summary.csv`
- `backend_bakeoff_summary.md`
- `backend_probe_matrix.md`
- `dataset_preview_table.md`
- `backend_latency_table.md`
- `backend_io_table.md`
- `source_mix_plan_table.md`
- `batch_balance_plan_table.md`
- `action_family_schema_table.md`
- `missing_telemetry_table.md`
- `backend_environment_table.md`
- `reuse_license_table.md`

Each table also has a CSV companion. The raw JSON payload is
`backend_bakeoff_raw.json`.
