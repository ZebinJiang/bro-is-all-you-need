# autovla.dataloader.ingestion Module Guide

## Purpose

`autovla.dataloader.ingestion` is reserved for future governed dataset conversion and ingestion plans. In the current readiness tranche, ingestion is documentation-only: no conversion code, dataset writes, media decode, parquet row reads, or statistics fitting are implemented here.

## Public contracts

- Future ingestion contracts must consume `DatasetArtifactV1` metadata and produce governed project-local outputs.
- Ingestion plans must state source format, target artifact, statistics scope, checksums, and output policy before execution.
- Real conversion must remain separate from metadata-only adapters.

## Directory structure

- `MODULE.md`: this agent-readable boundary guide.
- Future files should separate plans, validators, and executors instead of mixing them into one runtime entrypoint.

## Naming conventions

- Use `*_plan.py` for dry-run plan builders.
- Use `*_executor.py` only for authorized conversion execution.
- Use `*_manifest.py` for generated manifest helpers.
- Keep external adapter names in `autovla.dataloader.adapters`, not in ingestion filenames.

## Extension points

- Add a conversion planner when Data has an approved task to map an external format into AutoVLA artifacts.
- Add an executor only when the task explicitly authorizes dataset reads/writes and target governed paths.
- Add integrity checks for generated artifacts after conversion, not during metadata-only preview.

## Modify vs extend rule

Extend ingestion with new format-specific planners rather than changing shared dataloader contracts. Modify existing ingestion executors only when the authorized output contract changes and validation evidence covers the migration.

## Invariants

- Original data under `datasets/readonly/**` stays immutable.
- Derived data belongs under `datasets/working/` or `datasets/cache/`.
- Run evidence belongs under `runs/`.
- Import formats are not the hot training path.
- Conversion must be explicit, bounded, and recorded.

## Performance requirements

- Do not copy full datasets into run directories.
- Plan builders should inspect metadata and bounded manifests only.
- Executors must avoid redundant data movement and must record size and checksum evidence when authorized.

## Tests and gates

- Plan-only tests should use tiny synthetic metadata.
- Conversion tests must stay synthetic unless a future task authorizes real data access.
- Heavy validation, Slurm, GPU, model, network, media decode, and stats fitting require separate scope.

## Agent workflow

1. Verify an explicit conversion task exists before adding executable ingestion code.
2. Keep source data immutable and target paths governed.
3. Record source, destination, command, checksums, and rollback notes for any conversion.
4. Stop on missing authorization, ambiguous output path, or dependency requirement.

## Anti-patterns

- Running conversion from an adapter preview.
- Reading or writing real datasets during a plan gate.
- Treating external format readers as training dataloaders.
- Hiding conversion side effects behind validation or tests.
