# M2 Transform Pipeline + Data Contract

M2 adds a numpy-only transform/data layer around the accepted M1 `RawSample`
contract. It does not change M1 public types, model APIs, training loops,
runtime endpoints, or deployment behavior.

## Package Boundary

- `genesisvla.core.protocols.TransformProtocol` is the shared structural
  protocol for `RawSample -> RawSample` transforms.
- `genesisvla.dataloader.transforms` owns concrete transform implementations.
- `genesisvla.dataloader.statistics` owns schema and cache helpers for
  transform statistics.
- `genesisvla.dataloader.datasets` owns small in-memory dataset utilities used
  by M2 tests.
- `genesisvla.testing.fixtures` owns generated tiny fixtures for CPU CI.

Model-specific tokenization, VLM processors, device transfer, runner lifecycle,
checkpoint management, and distributed training remain out of scope.

## Transform Configuration

`TransformSpec` stores a transform name and JSON-like params. It rejects
model-specific tokenization and implicit device transfer keys so transform
configuration stays independent from model configuration.

`TransformRegistry` maps names to factories. Unknown transform names and
duplicate registrations fail explicitly.

`ComposeTransform` executes `TransformProtocol` instances left-to-right and can
serialize/deserialize through `TransformSpec` and `ComposeConfig`.
`stable_transform_fingerprint()` hashes canonical config representation for
statistics cache validation.

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
must be declared.

## Dataset Statistics Cache

`DatasetStatistics` records schema version, dataset fingerprint, transform
fingerprint, count, feature statistics, metadata, and checksum. Cache writes use
same-directory temporary files and `os.replace` for atomic replacement.
Loads can reject stale dataset or transform fingerprints.

## Tiny Fixtures And Mixtures

The tiny LeRobot-like and Parquet-like fixtures are generated in memory, contain
padding/mask cases, and require no external downloads. `MixtureDataset` provides
deterministic weighted sampling using seed, epoch, and worker position metadata.

## Legacy Adapter

`LegacyDataloaderAdapter` converts old sample dictionaries to `RawSample` with
explicit `robot_tag` injection, optional shape validation, and warnings for
unsupported fields. Unsupported fields are preserved in metadata for review.
