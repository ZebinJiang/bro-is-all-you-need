# M10 Production Model Zoo

The active keys are exactly `gr00t_n1d6`, `gr00t_n1d7`, and `pi0_5`.
`pi0` and `pi0_fast` are inactive with `DEFERRED_BY_USER_PRIORITY`. The default
`families` status listing excludes deferred keys; `families --include-deferred`
preserves their status metadata without allocating a model. Asset `list`
continues to enumerate exact registered asset specifications.

| Family | Source architecture | Asset/checkpoint gate | Runtime claim |
| --- | --- | --- | --- |
| `gr00t_n1d6` | complete at Isaac-GR00T `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | inventory ready; full shard verification and receipt issuance require compute | none |
| `gr00t_n1d7` | complete at Isaac-GR00T `9c7e746b2cd37a810070a98ef41d290a07e806c2` | blocked by conflicting checkpoint terms and missing Cosmos license/access receipts | none |
| `pi0_5` | AutoVLA-native PyTorch source mapped to OpenPI `15a9616a00943ada6c20a0f158e3adb39df2ccac` | blocked by checkpoint/Gemma terms, local assets and deterministic conversion evidence | none |

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
registered specifications. Runtime memory, GPU utilization and distributed
efficiency remain unmeasured until authorized compute validation.

`NO_BACKEND_WINNER` remains literal.
