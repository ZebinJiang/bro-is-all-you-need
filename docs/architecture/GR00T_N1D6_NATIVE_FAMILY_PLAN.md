# GR00T N1D6 Native Family Plan

## Status

`gr00t-n1d6` is implemented as an AutoVLA-native metadata and dry-run adapter family. It does not load the GR00T runtime, checkpoint weights, tokenizers, processors, or model configs.

## Layers

Layer 1: metadata-only family.

- family key: `gr00t-n1d6`
- upstream reference: NVIDIA Isaac-GR00T / GR00T-N1.6
- modalities: language, image views, proprioception/state
- action output: continuous action chunk
- runtime status: metadata-only, dry-run adapter supported, upstream runtime not loaded

Layer 2: dry-run adapter.

- validates expected camera count
- validates generic `TrainingBatch`
- emits `ModelInput`
- records family/fingerprint/action metadata
- performs no IO and no runtime import

Layer 3: future runtime adapter.

- documented only
- requires GR00T code license review, model-card/weight-license review, dependency profile approval, checkpoint provenance, and compute-node validation
- not activated in this task

## Guarantees

- no weight load
- no tokenizer load
- no network
- no checkpoint download
- no GR00T runtime import during registry lookup
- no checkpoint compatibility claim
