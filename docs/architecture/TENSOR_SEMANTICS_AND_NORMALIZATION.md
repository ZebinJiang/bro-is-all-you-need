# Tensor Semantics and Normalization

## Ownership boundary

`autovla.core.semantics` is the backend-neutral source of truth for axis names,
layouts, known axis sizes, alignment policies, and mask meanings. It imports neither
NumPy nor Torch. `autovla.data.normalization` owns immutable concrete statistics and
NumPy execution. The optional Torch adapter imports Torch only when invoked and applies
the same statistics and alignment plan.

The protected StarVLA dataset path remains an ingestion boundary. It may provide
physical-unit arrays and source metadata, but it does not define AutoVLA layout,
normalization, padding, or loss-mask semantics.

## Explicit layouts

`TensorLayout` stores ordered `AxisName` values and optional known positive sizes.
Persisted statistics bind all sizes from their arrays, so `[D]`, `[T]`, and `[T,D]`
cannot be reconstructed from rank alone. Supported axis vocabulary includes batch,
time, feature, action, state, camera, frame, height, width, channel, statistic, token,
and embodiment. Scalar layout is the empty axis tuple.

The required statistics forms are:

| Form | Required layout |
| --- | --- |
| scalar | `()` |
| feature vector `[D]` | `(feature,)` |
| temporal vector `[T]` | `(time,)` |
| per-horizon feature `[T,D]` | `(time, feature)` |

Embodiment-specific values live under
`NormalizationStatistics.embodiments[embodiment][feature]`; lookup falls back to the
global feature only when no embodiment override exists.

## Alignment policy

Every mismatch has one explicit policy. `exact`, `broadcast_missing_axes`,
`time_index`, `truncate_time`, `pad_time`, `repeat_time`, and `reject` are separate
fingerprinted choices. Exact requires identical ordered axes and shape. Missing-axis
broadcast accepts only source axes contained in the target and only equal or singleton
sizes. Time index maps every target timestep to one source timestep. Truncate, pad, and
repeat resolve deterministic time-index plans. Pad uses `-1` plan positions and an
explicit finite pad value. Any omitted, incompatible, or ambiguous choice fails closed.

## Statistics and masks

`FeatureStatistics` and `FeatureNormalizationStatistics` are the same class object.
The class owns read-only arrays, validates finite active values, stores method, layout,
known sizes, names, statistics mask semantics, constant-feature policy, and alignment.
JSON uses `null` for non-finite inactive slots, remains valid under `allow_nan=False`,
and round-trips to the same content fingerprint.

The masks below are distinct contracts and must not be substituted for each other:

- temporal validity;
- action-dimension validity;
- statistics validity;
- padding validity;
- loss inclusion;
- camera validity;
- frame validity.

Each `SemanticMask` carries a `MaskKind`, layout, and true-value interpretation.
Statistics masks select which parameters are active. Action masks select physical
action elements. Padding and temporal masks remain separate even when their values
happen to match.

## Constant features and execution

An active zero scale or zero range follows `ConstantFeaturePolicy`: `raise` rejects
construction; `identity` excludes only that slot from normalization. There is no hidden
epsilon. NumPy normalization reads every active element once and writes one owned
output, with time and space complexity `O(N)` for `N` values. Broadcasted parameters
are views. The Torch adapter transfers only the compact reshaped statistics/mask plan
to the existing tensor device; it does not move the action tensor through CPU memory.

No dataset, checkpoint, model asset, remote code, backend benchmark, or runtime winner
is introduced by this contract. `NO_BACKEND_WINNER`.
