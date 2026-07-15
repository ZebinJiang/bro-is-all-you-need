# Model Assets

Model assets are local-only, revision-pinned, and verified against a complete
file manifest before use. Source-code license, checkpoint weight terms, model
card terms, and tokenizer/support-data terms are separate review fields.

GR00T uses a typed `Gr00tModelAssetBundle` with two independently verified
receipts:

| Role | Key | Revision | Content boundary |
| --- | --- | --- | --- |
| Base checkpoint | `gr00t_n1d6` | `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61` | structured local checkpoint, metadata, and existing reviewed Eagle subtree |
| Eagle support data | `gr00t_n1d6_eagle_support` | `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | 10 declared non-executable JSON/text tokenizer/config files plus NVIDIA `LICENSE` |

The support-data manifest rejects undeclared files and contains no Python.
Construction verifies both receipts and the checkpoint namespace split before
checking optional runtime dependencies or allocating a model. Missing or
incomplete bundles therefore fail closed. The local reviewed `_nvidia/eagle`
implementation is used; remote code, network resolution, arbitrary pickle, and
Hugging Face upload are not allowed. PyTorch fallback loading uses
`weights_only=True`, while the preferred checkpoint representation remains
structured safetensors.

Assets under `base_model/` are runtime state and must never be staged in Git.
Local verification proves file integrity and provenance only. It does not grant
redistribution rights or establish runtime, numerical, or model-quality parity.
