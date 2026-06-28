# M2 Transform Pipeline + Data Contract

M2 adds a numpy-only transform/data layer around the accepted M1 `RawSample`
contract. It does not change M1 public types, model APIs, training loops,
runtime endpoints, or deployment behavior.

## Package Boundary

- `autovla.core.protocols.TransformProtocol` is the shared structural
  protocol for `RawSample -> RawSample` transforms.
- `autovla.dataloader.transforms` owns concrete transform implementations.
- `autovla.dataloader.statistics` owns schema and cache helpers for
  transform statistics.
- `autovla.dataloader.datasets` owns small in-memory dataset utilities used
  by M2 tests.
- `autovla.testing.fixtures` owns generated tiny fixtures for CPU CI.

Model-specific tokenization, VLM processors, device transfer, runner lifecycle,
checkpoint management, and distributed training remain out of scope.

## Transform Configuration

`TransformSpec` is the versioned public serialization record for a transform.
It stores `schema_version`, `name`, `implementation_version`, and canonical
`params`. Params must be strict JSON values: string keys only, finite floats
only, no numpy arrays, sets, bytes, callables, dataclasses, or other Python
runtime objects. Construction deep-copies and freezes params, sorts keys, and
rejects model-specific tokenization or implicit device-transfer keys so
transform configuration stays independent from model configuration.

`TransformRegistry` maps names to factories. Unknown transform names and
duplicate registrations fail explicitly.

`ComposeTransform` executes `TransformProtocol` instances left-to-right. Public
serialization is explicit: serializable transforms expose `to_spec()`, and
runtime-only transforms fail serialization instead of relying on dynamic
`getattr()` as a public mechanism. `ComposeConfig` records versioned ordered
steps. `stable_transform_fingerprint()` hashes schema version, implementation
version, transform names, and canonical params for statistics cache validation.

`TransformContext` is an immutable JSON-safe execution context for deterministic
transforms. It records seed, epoch, sample key/index, worker id/count,
rank/world size, and strict JSON metadata. It does not change the minimal core
`TransformProtocol`; transform implementations may accept it through
dataloader-owned adapters in later work.

## Typed Batch Contract

`CollatedBatch` is the M2 numpy-only typed batch contract. It owns all arrays
with defensive copies and read-only flags. Sample actions remain `[H,D]` at
`RawSample` boundaries; batched actions and action masks are canonical
`[B,H,D]`. Legacy `[D]` action masks are accepted only at the collate conversion
boundary and are broadcast to `[H,D]` before batching. The legacy
`collate_raw_samples()` dict output remains available for existing tests, while
`collate_raw_samples_typed()` returns the typed contract directly.

## Image Transforms

`ImageResize`, `ImageNormalize`, and deterministic `ImageAugment` are minimal
CPU/numpy transforms. They require explicit channel order and input range, do
not import image backends, and do not invoke model processors.

## State/Action Normalization

`FeatureStatistics` supports `mean_std` and `min_max` with valid-dimension
masks. Invalid/padding dimensions keep their original values. Zero variance
requires an explicit policy: `raise` rejects it, while `identity` leaves the
affected valid dimensions unchanged.

`StateActionNormalize` and `StateActionUnnormalize` round-trip valid dimensions
and preserve padding dimensions.

## Action Modes

`ActionModeTransform` supports:

- `absolute` with `world` reference frame;
- `delta` with `previous_action` reference frame and explicit first-step policy;
- `relative` with `state` reference frame and explicit `state_to_action_indices`.

The relative mode does not assume `state[:action_dim]`. Any state/action mapping
must be declared. M2 relative mode accepts only a one-dimensional state reference
vector; temporal or multi-dimensional state tensors require a later contract
extension.

## Dataset Statistics Cache

`DatasetStatistics` records schema version, dataset fingerprint, transform
fingerprint, count, feature statistics, metadata, and checksum. Cache writes use
same-directory temporary files and `os.replace` for atomic replacement.
Loads can reject stale dataset or transform fingerprints. `FeatureStatistics`
and `DatasetStatistics` own their input arrays/metadata, store arrays as
read-only copies, and serialize metadata through the same strict JSON
canonicalization used by transform specs. Feature names must be non-empty and
unique when present. Standard deviation, min/max range, fingerprints, and masks
are validated at construction time; mask arrays reject numeric/string/object
coercion while accepting bool arrays and Python bool-only sequences.

## Tiny Fixtures And Mixtures

The tiny LeRobot v3-like and standalone Parquet fixtures are generated at test
time under pytest `tmp_path` or an explicit governed output directory. They
contain actual parquet shards/files, metadata/data relationship checks,
padding/mask cases, deterministic reload, malformed-data failure coverage, and
RawSample adapter paths. Generated parquet files and LeRobot-like directories
are not source-tracked artifacts. PyArrow is used only by fixture helpers and
tests as the approved quality/test parquet backend, not as a public dataloader
API dependency. `MixtureDataset` provides deterministic weighted sampling using
seed, epoch, and worker position metadata.

## Legacy Adapter

`LegacyDataloaderAdapter` converts old sample dictionaries to `RawSample` with
explicit `robot_tag` injection, optional shape validation, and warnings for
unsupported fields. Unsupported fields are preserved in metadata for review.
