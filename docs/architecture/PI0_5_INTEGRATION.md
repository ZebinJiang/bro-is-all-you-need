# Pi0.5 Integration

The active key `pi0_5` maps to Physical Intelligence OpenPI
`15a9616a00943ada6c20a0f158e3adb39df2ccac`. AutoVLA owns the PyTorch processor,
prefix/backbone, action expert, model, checkpoint adapter and conversion schema.
JAX, Flax and Orbax are conversion-only; production imports do not patch shared
Transformers or import those runtimes.

OpenPI source is Apache-2.0, while Gemma, tokenizer, checkpoint and derived
weight terms are separate. Wave 4 produced no local Pi0.5 asset root or
conversion. `PI05_CHECKPOINT_AND_GEMMA_TERMS_RECEIPT_MISSING` is the first
blocker; normalization selection and deterministic safetensors conversion also
remain absent. Source completeness does not imply checkpoint, CUDA, DDP,
DeepSpeed, cross-node, inference or model-quality readiness.
