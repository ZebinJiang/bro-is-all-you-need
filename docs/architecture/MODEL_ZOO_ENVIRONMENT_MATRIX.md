# Model Zoo Environment Matrix

| Family | Env profile | Expected dependencies | Expected assets | Risk | Install status | Fine-tune readiness |
| --- | --- | --- | --- | --- | --- | --- |
| AutoVLA core | `autovla-core` | numpy, omegaconf, quality tools | none | low | installed / existing | config and governance checks only |
| WebDataset data | `data-webdataset` | webdataset route when authorized | generated stores under ignored paths | medium | manual only | data pipeline candidate |
| Robo-DM-style data | `data-robodm` | future candidate dependencies | local tiny fixtures | medium | not installed | comparison placeholder |
| Zarr data | `data-zarr` | zarr stack when authorized | local zarr candidate artifacts | medium | not installed | future placeholder |
| LeRobot data | `data-lerobot` | LeRobot v2/v3 route | local approved dependency source | high | not installed | dependency decision required |
| GR00T-N1.6 | `model-gr00t-n1d6` | GR00T runtime deps when authorized | governed local checkpoint path | high | not installed | env-gated telemetry only |
| PI-series | `model-pi0` | PI runtime deps | local approved assets | high | not installed | placeholder |
| PI fast | `model-pi0-fast` | PI fast runtime deps | local approved assets | high | not installed | placeholder |
| OpenVLA | `model-openvla` | OpenVLA-style deps | local approved assets | high | not installed | placeholder |
| Qwen-action | `model-qwen-action` | Qwen-action deps | local approved assets | high | not installed | placeholder |

No row authorizes dependency installation, model loading, checkpoint loading, or
fine-tuning by itself.

## Next Goal

The post-matrix next goal is
`AUTOVLA-M3-GR00T-N1D6-WEBDATASET-TELEMETRY-DRYRUN-ENV-GATE-001`. It keeps
GR00T-N1.6 behind the manual uv profile boundary and only validates whether the
WebDataset telemetry dry-run environment is ready for a later explicitly
authorized run.
