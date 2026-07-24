# Model Runtime Evidence Architecture

## Status

M12 introduces a versioned, multi-receipt readiness ledger. The ledger records
observed evidence; it does not infer runtime support from source presence,
configuration, package declarations, asset names, or historical milestone
status.

`NO_BACKEND_WINNER` remains unchanged.

## Canonical Objects

`RuntimeValidationKey` is the exact identity of one claimed operation. A
runtime key binds the model-family definition, runtime profile, resolved lock,
realized environment, asset and checkpoint identities, data binding, source
SHA, command, operation, strategy, topology, precision, checkpoint mode,
explicit data backend, exact positive gradient accumulation, and DeepSpeed
stage where applicable.

`RuntimeEvidenceReceipt` is one immutable observation for one validation key.
It records source, static, or runtime evidence, the evidence artifact
fingerprint, terminal pass/fail state, and whether the receipt came from the
M11 migration boundary.

`RuntimeEvidenceSet` retains multiple operations, strategies, and topologies at
the same time. Receipts are deterministically ordered. Duplicate receipt
identities and two payloads for the same validation key are rejected rather
than overwritten.

`ModelFamilyReadinessSnapshot` binds one current family-definition fingerprint
to one evidence set. `ReadinessProjection` is derived on demand for CLI and UI
display. The projection is never persisted as another mutable source of truth.

## Evidence Rules

Source evidence may describe source availability. Static evidence may describe
metadata or a manifest decision. Neither can authorize construction,
checkpoint loading, forward, backward, optimization, prediction, resume,
distributed execution, or profiling.

New runtime receipts require a complete M12 validation identity. Operations
that consume a checkpoint require a checkpoint fingerprint. Checkpoint load,
save, and resume additionally require an explicit checkpoint mode. Processor,
forward, backward, optimizer, prediction, decode, data-binding, and profiling
operations require both a data-binding fingerprint and an explicit data
backend. Backward, optimizer, checkpoint-save, resume, and profiling operations
also require an exact positive gradient-accumulation value. A contract fixture
therefore cannot silently become real-data evidence, and accumulation windows
or backend identities cannot overwrite one another.

Topology is explicit:

- `single_gpu` requires one node, world size one, and one GPU per node.
- `ddp` requires world size of at least two and no ZeRO stage.
- `deepspeed` requires an explicit ZeRO 1, 2, or 3 stage.
- World size must equal node count multiplied by GPUs per node.

These rules preserve simultaneous DDP, ZeRO, and cross-node receipts without a
scalar distributed field overwriting earlier evidence.

## Persistence And Migration

The only writable schema is
`autovla.runtime_readiness.m12.v1`. Documents contain sorted family snapshots
and their receipt sets. Writers serialize deterministically, flush and fsync a
same-directory temporary file, atomically replace the destination, and fsync
the directory. Symlink targets, unknown fields, missing fields, malformed
JSON, bool-as-int values, stale family definitions, partial SHA values, and
impossible strategy/topology combinations fail closed.

The reader accepts the historical M11 snapshot shape and the explicit
`autovla.model_readiness.m11.v1` wrapper. It verifies every serialized scalar
axis and validation list against the old receipts before migrating in memory.
Migrated receipts are marked `historical=true`; they remain available for
source-only inspection but cannot authorize runtime activation. Reading M11
never rewrites the source file.

## Activation

`evaluate_activation()` requires a caller-supplied complete
`RuntimeValidationKey`. Authorization succeeds only when the snapshot contains
an equal, successful, non-historical runtime receipt. A receipt for another
operation, topology, strategy, precision, lock, environment, asset,
checkpoint, data binding, source SHA, or command cannot satisfy the request.

Blocked decisions expose one stable first blocker, including family or
definition mismatch, incomplete key, missing operation evidence, historical or
non-runtime evidence, exact-identity mismatch, and failed runtime evidence.

## CLI Boundary

`autovla-models status --readiness-file <path>` reads the canonical ledger,
verifies it against current family definitions, and derives the public status
projection. Without a readiness file, catalog inspection exposes only source
inventory and historical accepted-evidence identifiers. Checkpoint, forward,
training, and distributed categories are derived only from the M12 snapshot;
the catalog never acts as a parallel runtime-status source.

Importing readiness, persistence, activation, or model status modules does not
import Torch, family implementations, training engines, datasets, runtime
profile managers, or network clients. Explicit readiness-file inspection may
resolve current lightweight family definitions solely to verify their
fingerprints.
