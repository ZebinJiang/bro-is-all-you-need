# Reference-Guided DataBackend, Mixing, And Action Schema Substrate

## Scope

This tranche turns inspected upstream architecture patterns into native AutoVLA
metadata-only infrastructure:

- DataBackend static registry and explicit lookup errors.
- Bounded local probes for synthetic, raw ZJH metadata, LeRobot local layout,
  and WebDataset tar layout.
- Dataset mixing and batch balancing planning without creating a DataLoader.
- GR00T and OpenPI/pi action-family schema rows without runtime imports.
- Bakeoff CLI tables for probe, preview, latency, IO, source mix, batch
  balance, action schema, missing telemetry, reuse/license, and environment.

## Reference Reuse Decision

| Reference | Inspected commit/tag | Reuse mode | Implemented AutoVLA component | Copied code | Dependency added |
| --- | --- | --- | --- | --- | --- |
| StarVLA | `2e5f239bc0b1661d7d556bdba5071f3041544cc6` | architecture-guided native | Boundary naming for data/model/training/action-head separation | false | false |
| Dexbotic | `0f5ae6382bf0bc6196120f0930ce342ae54e7354` | architecture-guided native | Lightweight registry and explicit factory errors | false | false |
| FluxVLA | `9ee9ffd5bb17ab716b276351edd1dd432afbe0d1` | architecture-guided native | Standardized interface metadata | false | false |
| VLA Foundry | `77d2866757b128c77f294d2ad2c5321978943956` | architecture-guided native | DatasetMixSpec and BatchBalancePlan | false | false |
| NVIDIA Isaac-GR00T | `ab88b50c718f6528e1df9dcbaf75865d1b604760` | architecture-guided native | GR00T metadata-only action schema | false | false |
| OpenPI / pi | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | architecture-guided native | pi0/pi0-fast/pi05 roadmap action schema | false | false |
| LeRobot | `192a0b92820dab7571602e4d77909d7f931b30f0` | native probe | LeRobot local metadata probe | false | false |
| WebDataset | `e0953f9bba17b416d5792d5a263b171c266e78be` | native probe | Stdlib tar metadata probe | false | false |
| Qwen / Qwen-VL | existing AutoVLA docs reference | documentation reference only | Sample-format vocabulary alignment | false | false |

No upstream source file was copied, adapted, vendored, or imported as a runtime
dependency. The tracked manifest is `third_party/reuse_manifest.yaml`.

## CLI Contract

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

## Table Outputs

All runtime, schema, and reuse evidence is table-shaped:

- `backend_probe_matrix.{csv,md}`
- `dataset_preview_table.{csv,md}`
- `backend_latency_table.{csv,md}`
- `backend_io_table.{csv,md}`
- `source_mix_plan_table.{csv,md}`
- `batch_balance_plan_table.{csv,md}`
- `action_family_schema_table.{csv,md}`
- `missing_telemetry_table.{csv,md}`
- `reuse_license_table.{csv,md}`
- `backend_environment_table.{csv,md}`
- `backend_bakeoff_raw.json`

## Safety Boundary

The tranche does not download data, copy datasets, write dataset caches, decode
media, load model weights, load tokenizers, start training, use GPU/CUDA, submit
Slurm jobs, call W&B/HF/network services, endpoints, or robots.
