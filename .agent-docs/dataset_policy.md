# Dataset Policy

## Directory layout

```text
datasets/
  readonly/   # immutable original dataset source files
  working/    # reusable derived datasets, conversions, patches, filtered subsets, manifests
  cache/      # reusable indexes, feature caches, tokenization caches, small precomputed artifacts
```

## Supported source vocabulary

The governance harness can track source datasets such as:

- LeRobot datasets;
- Parquet collections;
- RLDS datasets;
- HDF5 datasets;
- real-robot logs;
- simulation rollouts;
- evaluation benchmark data.

This vocabulary does not imply any dataset is present until it is registered in `.agent-docs/asset_manifest.md`.

## Rules

1. Original dataset source files belong in `datasets/readonly/` and are immutable.
2. Do not write generated data into `datasets/readonly/`.
3. Do not copy full datasets into every run directory.
4. Run directories may store small manifests, metrics, references, checksums, sampled examples, or symlinks where safe.
5. Derived artifacts that should be reused across runs belong under `datasets/working/` or `datasets/cache/`.
6. Any dataset used as validation evidence must be registered in `.agent-docs/asset_manifest.md`.
7. Dataset transformations must record source path, source format, transformation command/config, output path, and checksum when feasible.
8. If the user explicitly gives an external dataset path, use the one-time external path transfer policy and record a transfer manifest. Do not touch the external path again after task completion without a new explicit instruction.
9. Robot logs and benchmark data must preserve provenance, embodiment assumptions, timestamps, and filtering criteria when feasible.

## Capacity guidance

For large datasets, prefer:

- manifests instead of copies;
- symlinks instead of copies when site policy permits;
- shared derived caches under `datasets/cache/`;
- reusable converted datasets under `datasets/working/`;
- run-specific metadata under `runs/<kind>/<run_id>/outputs/`.

Do not create per-run full dataset replicas without explicit user authorization.
