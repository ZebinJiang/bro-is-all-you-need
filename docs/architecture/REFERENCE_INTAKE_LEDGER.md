# Reference Intake Ledger

## Scope

Task: `AUTOVLA-M3-TRAINING-SPINE-MODEL-ZOO-GR00T-N1D6-REUSE-001`

The intake conclusion is inspiration-only reuse. No upstream source is copied, adapted, vendored, imported, or made a dependency by this task.

## Ledger

| Project | Source reviewed | License | Reuse class | Notes |
| --- | --- | --- | --- | --- |
| StarVLA | Current engineering base and public repo/paper metadata | Expected MIT; re-confirm before code copy | Inspired | Modular backbone/action-head/trainer separation informs AutoVLA boundaries. |
| Dexbotic | `code-input/LICENSE_REVIEW.md` | MIT | Inspired | Registry/factory and layered config ideas only. |
| FluxVLA | `code-input/LICENSE_REVIEW.md` | Apache-2.0 | Inspired | Interface decoupling and deployment-aware naming ideas only. |
| VLA Foundry | Upstream license file | MIT | Inspired | Training-stack and telemetry structure ideas only. |
| NVIDIA Isaac-GR00T | Upstream code license file | Apache-2.0 code; model weights separate | Inspired | Family metadata and adapter-boundary ideas only. |
| OpenPI | Upstream license file | Apache-2.0 | Inspired roadmap | Pi-family roadmap metadata only. |
| LeRobot | Upstream license file | Apache-2.0 | Inspired | Dataset convention ideas only. |
| WebDataset | Upstream license file | BSD-3-Clause | Inspired | Streaming backend and throughput pattern ideas only. |
| Qwen / Qwen-VL | Upstream license file | Apache-2.0 | Inspired | Sample-format discipline and preprocessing ideas only. |

## Publication Decision

This ledger is publication-safe because it contains metadata and design decisions only. It does not include upstream source trees, archives, model weights, checkpoints, datasets, or copied code snippets.
