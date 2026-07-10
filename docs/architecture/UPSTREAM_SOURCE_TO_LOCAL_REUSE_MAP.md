# Upstream Source To Local Reuse Map

## Final M4 Reuse Decision

| Reference | Local implementation | Reuse mode | Dependency impact |
| --- | --- | --- | --- |
| StarVLA | Existing AutoVLA core registry, contracts, model metadata, and runner | Existing local implementation retained | None |
| WebDataset 1.0.2 | Existing `webdataset_builder.py` and `webdataset_reader.py` behind the M4 factory | Lazy public `TarWriter` and `WebDataset` package API use | No new dependency |
| RoboDM | Existing AutoVLA-owned tar/index builders and grouped reader behind `robodm_container_v1` | No upstream code; RoboDM-style only | None; stdlib-backed |
| Isaac GR00T | `gr00t_n1d6_metadata` | Metadata only | No runtime import |
| OpenPI | `pi0_metadata` and `pi05_metadata` | Metadata only | No JAX/Flax/OpenPI import |
| LeRobot | Existing local source-format compatibility | Existing implementation retained | None |
| Dexbotic, FluxVLA, VLA Foundry | Registry/config/runner design comparison only | No source copied or adapted | None |

No upstream source expression was copied, adapted, or vendored. WebDataset is
loaded only after `webdataset_tar` is selected. RoboDM native storage/API
compatibility is not claimed and its backend capability records
`native_compatible=false`.

The two integrations establish canonical-batch equivalence only. Decision:
`NO_BACKEND_WINNER`. There is no default, performance claim, model-runtime
readiness claim, or production selection.
