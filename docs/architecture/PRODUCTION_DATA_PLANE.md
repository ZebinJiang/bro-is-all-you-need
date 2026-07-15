# Production Data Plane

## Canonical ownership

`autovla.data.schema` owns feature, episode, temporal-window, source-capability,
manifest, `TrainingSample`, and `TrainingBatch` identities. The sample and batch
classes are exact aliases of `autovla.core.types.training`; there is no second
constructor. `autovla.dataloader` is a compatibility/physical-store layer.

```text
local metadata + physical records
  -> DataSourceSpec / DataSourceCapabilities
  -> canonical TrainingSample in physical units
  -> shared R3 TransformPlan
  -> canonical TrainingBatch [B,H,D] + strict bool action mask
  -> family processor
```

`FeatureSpec` binds a role, explicit `TensorLayout`, dtype, and required flag.
`TemporalQuery` is declarative; resolved `TemporalWindow` keeps sample/frame/time
identity and a temporal-valid mask distinct from action/feature/padding masks.
Every source declares map/streaming/random access, episode and statistics
metadata, temporal queries, local media, deterministic sharding, resume mode,
and batched reads.

## Backends

- `lerobot_local` reads explicit contained local v3 metadata, index, Parquet and
  optional local media. It never invokes Hub download or URL decode. LeRobot
  scalar, `[D]`, and `[T,D]` statistics map directly to the R3 rank-aware schema;
  no flatten, first-step, or hidden epsilon fallback exists.
- `webdataset` remains an optional candidate wrapper around public WebDataset
  APIs. AutoVLA assigns rank then worker units once and disables upstream
  splitters. Only contained local TAR shards and allowlisted record decoding are
  accepted; URL, pipe, remote cache, pickle, and arbitrary `torch.load` are
  rejected. The TAR streaming core is not reimplemented.
- `robodm_container` remains a candidate AutoVLA container format. It is not a
  claim of upstream RoboDM-native compatibility.

Source, schema, manifest, statistics, transform, partition, mixer, and resume
fingerprints are carried separately. Backend runtime and numerical parity are
deferred. No performance comparison or storage decision is made:
`NO_BACKEND_WINNER`.

LeRobot `v0.5.1` is a format/contract reference, WebDataset is public-API
integration, and VLA Foundry is architecture reference only. Exact revisions,
licenses, copy status, and destinations are recorded in
`docs/references/upstream_sources.yaml`; no R5 upstream source was copied.
