# Dataset-Model Binding Architecture

## M12 Semantic Manifest Boundary

M12 adds one canonical schema, `autovla.semantic_manifest.v1`. The parser accepts an
in-memory mapping and rejects unknown fields at every level. It binds:

- immutable dataset, backend, source revision, and store revision identities;
- source fields to physical feature keys, dimensions, units, coordinate/reference frames,
  representations, component order, source indices, modality, validity range, and masks;
- embodiment identity/version, joint and EEF order, camera mounts, and coordinate
  conventions;
- ordered cameras, language semantics, sample rate, state/action offsets, history, horizon,
  action mode, episode-boundary policy, padding, and mask closure;
- normalization method, statistics fingerprint, axes, feature coverage, owner, scope,
  constant-feature policy, and padding identity;
- an identity or named explicit projector with a version and implementation fingerprint.

The manifest always builds `DatasetSchema.row_validation_status="declared_only"`. A schema
declaration cannot state that rows were observed. `SemanticManifestReceipt` binds the
manifest, `DatasetSchema`, `EmbodimentSchema`, dataset content, projector, normalization,
backend, source, and store fingerprints, but it remains declaration-only.

Unknown units, frames, representation, order, action mode, temporal anchor/boundary policy,
language semantics, normalization policy, or required masks fail closed. There is no
implicit zero padding, index selection, coordinate conversion, temporal resampling, or
normalization fallback.

## Boundary

The M12 receipt-gated path is:

`semantic manifest -> manifest receipt -> backend reader receipt -> canonical records or TrainingBatch -> DatasetModelRuntime -> BoundBatchProvenance -> existing family processor`

`TrainingBatch` remains the only physical batch. Canonical records still reuse
`TrainingSample` and `PaddedBatchCollator`; direct batches and records converge on the same
validation path. `DatasetModelRuntime` owns no loader, backend implementation, dataset file,
model, tokenizer, optimizer, or device runtime. Its semantic/receipt modules import none of
those implementations.

The three backends remain separate first-class identities. Every manifest, row receipt,
reader receipt, context, and bound-batch provenance preserves literal `NO_BACKEND_WINNER`.
This layer neither ranks nor selects a backend.

## Compatibility Levels

- `exact`: the physical batch must match the declared dataset and model-side physical
  camera order, dimensions, history, horizon, normalization receipt, and embodiment. No
  projector or projection receipt may exist. The manifest projector mode must be
  `identity`.
- `explicit_projection`: a caller-supplied physical projector is mandatory. Its output is
  revalidated and must stamp the `DatasetModelBinding` fingerprint. The M12 bridge also
  requires `PhysicalProjectionReceipt`, which binds the named projector ID, version,
  implementation fingerprint, binding fingerprint, semantic-manifest receipt, and backend
  reader receipt.
- `contract_fixture_only`: only `ContractBatchFactory` may consume this level. Its output
  remains synthetic and records the model input source revision plus provenance schema.
  `ReaderEvidenceClass.CONTRACT_FIXTURE_ONLY` requires zero observed rows and cannot
  construct `BackendReaderReceipt`.
- `incompatible`: cannot enter the physical runtime or a family processor.

Missing required fields are rejected before record conversion. Missing units, coordinate or
reference frames, component order, dimensions, history, horizon, normalization identity, or
embodiment are incompatibilities. Required state/action values are never zero-filled to
manufacture compatibility. Model-owned padding remains downstream of a valid physical
binding and retains strict masks.

## Reader And Row Receipts

`RowValidationReceipt` is the only M12 object that records bounded row observation. A
real-data receipt requires at least one ordered record-provenance fingerprint and an exact
count. Its dataset schema, manifest receipt, dataset, backend, source revision, and store
revision must match. A fixture receipt remains `contract_fixture_only`, carries zero rows,
and cannot be promoted by changing a boolean.

`BackendReaderReceipt` binds the reader ID/version, dataset-config fingerprint, semantic
manifest receipt, row-validation receipt, cursor, resume state, and resume mode. It is
backend-neutral and converts to the existing `BackendBatchContext` without importing a
backend implementation. Any source/store/schema/projector/statistics drift fails before
physical binding.

`bind_with_reader_receipt` accepts a canonical `TrainingBatch`.
`bind_records_with_reader_receipt` accepts tiny canonical record mappings and reuses the
existing record converter and collator. Both emit `BoundTrainingBatch.provenance` as
`autovla.bound_batch_provenance.v1`, binding:

- binding and compatibility-report fingerprints;
- semantic-manifest, backend-reader, and row-validation receipt fingerprints;
- backend-context provenance and ordered record provenance;
- exact versus explicit-projection level and optional projection receipt;
- real-data evidence and literal `NO_BACKEND_WINNER`.

The older direct `BackendBatchContext` methods remain an M11 compatibility surface. M12
production integration must use the reader-receipt methods.

## M12 Production Runtime Bridge

Wave 6 新增 Data-owned `DataBackendBindingAdapter`。LeRobot、WebDataset 与 RoboDM
后端各自返回同一类型的适配器；适配器只接收已观察行的有序样本身份、记录来源指纹、
cursor/resume 元数据和严格 semantic manifest receipt，不打开或复制 payload。它统一
生成 `BackendBatchReceiptInput`，其中 `BackendReaderReceipt` 是规范来源，按需派生
`BackendBatchContext`。三个后端使用固定 reader/validator 身份，但没有优先级、评分或
采样策略变化，保持 literal `NO_BACKEND_WINNER`。

production chain 为：

`backend.binding_adapter -> BackendBatchReceiptInput -> DatasetModelRuntime.bind_production_batch|bind_production_records -> BoundTrainingBatch + RealBatchReceipt -> prepare_real_for_family`

`RealBatchReceipt` 是 immutable、deterministic、JSON-safe sidecar，不持有图像、状态、
动作或路径。它绑定 immutable source manifest、semantic/reader/bound provenance、
backend/source/store revision、有序 record/sample identity、binding/projector/compatibility、
embodiment/normalization，以及相机、状态、动作、严格 bool mask 和 timestamps 的形状与
内容指纹。公开身份拒绝绝对用户路径、home 缩写和凭据片段。

`prepare_real_for_family` 在调用 family processor 前强制存在并复核
`BoundBatchProvenance` 与 `RealBatchReceipt`。`contract_fixture_only`、`incompatible`、
样本顺序漂移、未知物理语义、缺失 state/action/mask/timestamps、schema/revision 漂移和
未收据化显式投影均 fail closed。M11 direct bind/prepare 仅保留旧兼容面，不构成
production real-data 证明。

## Cursor And Provenance

`BackendBatchContext` binds the backend key, dataset identity and dataset-config
fingerprint, manifest fingerprint, schema fingerprint, source revision, store revision, and
ordered per-record provenance fingerprints. Cursor, resume state, and resume mode describe
consumption position but cannot redefine that receipt. Its provenance fingerprint is
derived rather than accepted as caller-provided text.

`bind`, `bind_records`, the M12 reader-receipt methods, and `prepare_for_family` all converge
on the same context validator. Direct physical batches must already carry the receipt's
manifest, schema, source/store revision, dataset/config identity, and ordered record
provenance. Record conversion checks each record envelope before array materialization and
then verifies that conversion preserved the same identity. Backend-specific cursor values
remain opaque key/value items.

## Family Handoff

`prepare_for_family` calls the existing family-owned `prepare_batch` only after binding,
compatibility, provenance, and model-side physical shape checks. GR00T N1.6, GR00T N1.7, and
Pi0.5 continue to own image processing, tokenization, physical projector implementation,
family normalization, padding, device movement, and inverse action decoding. This shared
module adds no family-private import.

## Current Dataset Surface

`configs/data/m11_black_rubber_bellows_72x98.yaml` exposes a bounded metadata observation:
72 state values, 98 action values, three cameras, and 30 Hz. It records no row or media
read. Units, frames, ordering, history, horizon, normalization, and embodiment remain
unknown, so the result remains `incompatible` for every active family.

M12 does not create a semantic manifest for that dataset, read a dataset file, or mint a
real-data receipt. Its units, frames, physical order, action semantics, temporal alignment,
normalization ownership, masks, and embodiment mapping remain unresolved.

## Reference Reuse Decision

Existing AutoVLA production readers, `TrainingSample`, `PaddedBatchCollator`, `TrainingBatch`,
M11 binding contracts, and family processor entry points are reused directly. StarVLA,
LeRobot, WebDataset, RoboDM-style stores, VLA Foundry, Dexbotic, and FluxVLA were considered
as architecture references; no external code was copied or adapted, no new dependency was
introduced, and no notice change is required. A native sidecar is necessary because this
repository already owns the canonical fingerprints, resume state, and physical binding
semantics.

## Deferred Integration

三个 production backend 已可通过统一 adapter mint `BackendReaderReceipt`、context 输入和
完整 `RealBatchReceipt`，但本 wave 不修改 `DataModule`、`TrainingEngine`、runtime profile
或 family implementation，因此尚未消费真实 reader loop，也未把 receipt 写入训练
checkpoint/readiness chain。Family-owned `ModelInputSchema`、版本化 physical projector、
data-config manifest selection、真实 source indexing、bounded row consumption、DataModule
composition 与 Training receipt consumption 仍由后续授权 wave 接线。

Residual validation 仍需要 authoritative dataset semantics、真实 payload 的生产 reader
证据、完整 family schema/projector、accepted family assets/licenses，以及另行授权的
CUDA/runtime 验证。本 wave 只有 tiny in-memory fixture，不声明 robot、model quality、
throughput、distributed、真实数据集兼容性或 backend winner；`NO_BACKEND_WINNER`
保持 literal。
