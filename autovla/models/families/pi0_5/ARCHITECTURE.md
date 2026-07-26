# Pi0.5 Architecture Contract

Pinned source: Physical Intelligence OpenPI
`15a9616a00943ada6c20a0f158e3adb39df2ccac`.

## Graph

- `backbone.vision_tower.vision_model` is the 27-layer SigLIP encoder.
- `backbone.multi_modal_projector.linear` projects 1152-wide image tokens.
- `backbone.language_model` is the 18-layer 2048-wide PaliGemma prefix.
- `action_head.gemma_expert.model` is the 18-layer 1024-wide action expert.
- `action_head.{action_in_proj,time_mlp_in,time_mlp_out,action_out_proj}`
  owns the four flow projections.

The converter emits exactly this state-dict tree. Prefix layers emit their own
rotated PaliGemma K/V tensors; the matching expert layer reads that immutable
pair. Prefix queries cannot attend to suffix tokens, while all valid action
suffix tokens share one bidirectional suffix block.

## Fixed Semantics

- PaliGemma token embeddings are multiplied by `sqrt(2048)`.
- Gemma prefix and expert heads use independent 256-wide Q/K/V projections.
- Time uses 1024 sinusoidal channels over periods `[0.004, 4.0]`, followed by
  `1024 -> 1024 -> 1024` with SiLU after both linear layers.
- State is q01/q99-normalized, discretized into 256 bins, and placed in the
  SentencePiece prompt. The action/state envelope is 32D and horizon is 50.
- Training uses flow matching; prediction uses exactly ten Euler steps from
  `t=1` to `t=0`. Fixed noise and time hooks remain test-only inputs.

This contract establishes source and namespace alignment only. Converted
checkpoint loading, A100 numerical comparison, DDP, and ZeRO validation remain
separate acceptance gates.
