# M10 Production Model Zoo

The active keys are exactly `gr00t_n1d6`, `gr00t_n1d7`, and `pi0_5`.
`pi0` and `pi0_fast` are inactive with `DEFERRED_BY_USER_PRIORITY`. The default
`families` status listing excludes deferred keys; `families --include-deferred`
preserves their status metadata without allocating a model. Asset `list`
continues to enumerate exact registered asset specifications.

| Family | Source complete | Assembly eligible | Lifecycle gate | Runtime ready |
| --- | --- | --- | --- | --- |
| `gr00t_n1d6` | yes, Isaac-GR00T `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | yes, after accepted C1 receipt and C2R7 strict load | `BLOCKED_C3_DATA` | false |
| `gr00t_n1d7` | yes, Isaac-GR00T `9c7e746b2cd37a810070a98ef41d290a07e806c2` | false | `BLOCKED_ASSET_LICENSE` | false |
| `pi0_5` | yes, AutoVLA-native PyTorch mapped to OpenPI `15a9616a00943ada6c20a0f158e3adb39df2ccac` | false | `BLOCKED_ASSET_LICENSE` | false |

The C2R7 acceptance is one A100 strict checkpoint materialization of 1010
tensors with zero missing keys, unexpected keys, and shape mismatches. It is
not a real batch, forward, backward, optimizer, prediction, resume, DDP,
DeepSpeed, cross-node, scaling, quality, or deployment result.

Listing and config inspection are side-effect free. Definition lookup imports
only the selected lightweight family metadata. Assembly then consumes the
family-owned factories, dependencies, assets, transforms, precision and
topology contract. Asset bundles must be local and verified before construction.
No implicit network, remote code, arbitrary pickle, runtime fallback or
family-specific generic dispatch is permitted.

The registry moves only small immutable metadata. Tensor allocation, image and
language preprocessing, state/action padding, checkpoint tensors and GPU
placement remain behind the selected family assembly path. Therefore family
status listing is O(F) time and O(F) metadata space for five families, with zero
tensor/data movement. Asset listing is O(A) time and O(A) metadata space for
registered specifications. Checkpoint materialization memory was exercised only
by C2R7. Model-step memory, data movement, GPU utilization, collective
efficiency, scaling, and runtime quality remain unmeasured.

`NO_BACKEND_WINNER` remains literal.
