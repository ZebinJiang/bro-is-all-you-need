# GR00T N1.7 Integration

The active key `gr00t_n1d7` maps to official Isaac-GR00T GA source
`9c7e746b2cd37a810070a98ef41d290a07e806c2` and checkpoint revision
`2fc962b973bccdd5d8ce4f67cc63b264d6886495`. Its distinct Cosmos/Qwen3-VL
backbone, dynamic image grid and `(horizon,state,action)=(40,132,132)` contract
remain family-owned; generic assembly receives import strings and typed
requirements only.

The family processor owns the executable action boundary. Forward projection
reads each `_ActionProjection.source_indices` as `XYZ + ROT6D`, where ROT6D is
the first two rows of an SO(3) matrix, and writes `XYZ + axis-angle` to the six
`canonical_pose_indices` consumed by the family-neutral
`SE3RelativeActionTransform`. Inverse projection reconstructs those two matrix
rows. Both directions require exact NumPy `float32` or `float64` `[40,132]`
actions, same-shape boolean masks, finite values, and closed per-pose validity;
zero or collinear ROT6D axes fail closed. Projection is copy-on-write and
preserves all dimensions and masks outside the owned source/canonical slots.
Inverse-after-forward is exact within numeric tolerance for canonical SO(3)
rows; finite non-orthogonal ROT6D inputs are deterministically canonicalized by
Gram-Schmidt because the six-dimensional encoding is not one-to-one.

Source code is Apache-2.0. The packaged checkpoint license conflicts with the
model-card claim, and immutable Cosmos-Reason2-2B license/access receipts are
missing. Consequently no canonical asset bundle, checkpoint load, CUDA,
distributed, inference or runtime-ready claim is authorized. Unsafe checkpoint
convenience files were inventoried but never opened or executed.
