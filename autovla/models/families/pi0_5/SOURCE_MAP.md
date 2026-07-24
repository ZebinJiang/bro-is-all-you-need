# Pi0.5 Material Source Map

Source license is Apache-2.0. Gemma, tokenizer, checkpoint, and derived-weight
terms are separate. Each material local file appears once.

| Local file | Pinned OpenPI source | Reuse | AutoVLA change |
|---|---|---|---|
| `config.py` | `src/openpi/models/pi0_config.py` (`584d83f199e092203b59861a861c64768a4e0300`) | adapted constants | frozen typed contract |
| `_openpi_compat/modeling.py` | `src/openpi/models_pytorch/gemma_pytorch.py` (`ecc597a9a23ffb26db8c1907fd264c4af797d786`) | adapted graph | pure PyTorch modules and explicit masks |
| `backbone.py` | `src/openpi/models_pytorch/gemma_pytorch.py` (`ecc597a9a23ffb26db8c1907fd264c4af797d786`) | adapted execution | AutoVLA backbone and layer K/V output |
| `action_head.py` | `src/openpi/models_pytorch/pi0_pytorch.py` (`e68ddb7cc02c2fd256e9b48ac9d0fb9df966536a`) | adapted flow | AutoVLA action head and fixed hooks |
| `model.py` | `src/openpi/models_pytorch/pi0_pytorch.py` (`e68ddb7cc02c2fd256e9b48ac9d0fb9df966536a`) | adapted composition | canonical model outputs and parameter roles |
| `processor.py` | `src/openpi/models/tokenizer.py` (`8a4966d6298619e52c7ba53359ccbbb8ba0b8cf6`) and `src/openpi/transforms.py` (`272375ea95a5e43a42a6c0ff14cf89d34da76a45`) | adapted preprocessing | verified local SentencePiece and typed receipts |
| `conversion.py` | `examples/convert_jax_model_to_pytorch.py` (`632c0b8782c1ecb5cb380130a30a3152b220eafd`) | adapted conversion | canonical namespace and deterministic manifest |
