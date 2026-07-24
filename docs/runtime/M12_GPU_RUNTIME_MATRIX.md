# M12 GPU runtime evidence matrix

This matrix records exact M12 evidence levels. It does not advertise intended
capability as completed runtime support.

| Family | Executable source | Runtime lock | Environment | Asset/access state | Checkpoint/CUDA | Data/runtime topology |
|---|---|---|---|---|---|---|
| `gr00t_n1d6` | complete family source and strict loader contracts | resolved: Torch `2.7.1`, DeepSpeed `0.19.2` | acceptance deferred to compute | local bundle structurally complete; `ASSET_ACCESS_RECEIPT_MISSING`; large-shard rehash deferred to compute | no M12 checkpoint load or CUDA construction executed | semantic binding contracts present; no real-data step, DDP, ZeRO, cross-node, or profiling receipt |
| `gr00t_n1d7` | complete family source and strict loader contracts | resolved family contract: DeepSpeed `0.17.6` | acceptance deferred to compute | `GR00T_N1D7_CHECKPOINT_LICENSE_CONFLICT_UNRESOLVED`; no payload acquired | not eligible for checkpoint load or CUDA construction | no real-data step, DDP, ZeRO, cross-node, or profiling receipt |
| `pi0_5` | complete family source, conversion, and strict loader contracts | production and conversion locks resolved | acceptance deferred to compute | `PI05_CHECKPOINT_AND_GEMMA_TERMS_RECEIPT_MISSING`; no payload acquired | not eligible for conversion, checkpoint load, or CUDA construction | semantic binding contracts present; no real-data step, DDP, ZeRO, cross-node, or profiling receipt |

M12 executed no model construction, checkpoint deserialization, optimizer
step, prediction/decode, fresh-process resume, DDP, DeepSpeed ZeRO, cross-node
run, or profiler on a GPU. The project-local validation environment does not
contain Torch or DeepSpeed, so the published Draft is a static architecture and
contract candidate with external asset, terms, environment, data, and compute
gates still open.

LeRobot, WebDataset, and RoboDM remain first-class backend contracts. No real
backend was selected or benchmarked in M12: `NO_BACKEND_WINNER`.
