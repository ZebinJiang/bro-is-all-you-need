# Model Zoo And Native Adapter Strategy

This strategy records the first AutoVLA model-zoo readiness surface for
`AUTOVLA-M3-ZJH-DATASET-GR00T-N1D6-PIPELINE-READINESS-001`.

## Registry Boundary

`autovla.models` owns model-family metadata and adapter skeletons. Registry keys
are opaque configuration identifiers, not loaders. Looking up a registry entry
must not import StarVLA model code, NVIDIA Isaac-GR00T runtime code, torch,
transformers, tokenizers, checkpoint readers, training code, Slurm helpers, or
network clients.

The first canonical key is:

- `gr00t-n1d6`: GR00T N1.6/N1.6.1 metadata-only adapter skeleton.

## GR00T-Series Metadata

The GR00T-series candidate set currently contains:

- `gr00t-n1d6`
- `gr00t-n1d6.1`
- `qwen-gr00t-bridge-reference`

Only `gr00t-n1d6` is registered as an AutoVLA model-zoo entry. The other names
are roadmap metadata and do not imply checkpoint compatibility.

Manager has already checked the external reference
`https://github.com/NVIDIA/Isaac-GR00T/releases/tag/n1.6.1-release`, tag
`n1.6.1-release`, short commit `5dc80c4`, with release notes describing minor
fixes for GR00T 1.6. AutoVLA records that fact as reference metadata only. It
does not fetch, vendor, import, or execute upstream code.

## PI-Series Metadata

The PI-series candidate set currently contains:

- `pi0-roadmap`
- `pi0.5-roadmap`
- `qwen-pi-bridge-reference`

These entries are roadmap metadata only. They do not create compatibility
aliases, model loaders, checkpoint loaders, tokenizer loaders, or training
paths.

## StarVLA-Style Pluggable Direction

AutoVLA keeps the StarVLA-style idea that backbone, processor, action head,
checkpoint source, trainer, and dataset view should be separately registered
components. M3.1 only adds the metadata skeleton needed to name those future
interfaces. It does not activate a trainer, import StarVLA runtime paths, or
claim checkpoint compatibility.

## Qwen-Action / OpenVLA-Style Candidates

Qwen-action and OpenVLA-style candidates remain roadmap candidates until source,
license, checkpoint, tokenizer, action-head, and dataset compatibility evidence
is reviewed. They should enter through the same model-zoo metadata and native
adapter path as GR00T/PI candidates, not through one-off training code.

## Native Adapter Contract

Native adapter skeletons may expose:

- a stable `model_registry_key`;
- source family and release reference metadata;
- checkpoint/source metadata fields;
- explicit native chain, checkpoint, tokenizer, action-head, dataset, and
  training policies;
- fail-closed methods for future `FrameworkProtocol` operations.

They must not:

- instantiate a real model;
- construct a tokenizer;
- load or download checkpoints;
- probe local caches;
- call Hugging Face, W&B, endpoints, robots, GPU/CUDA, Slurm, or training code;
- import legacy `starVLA/**` model runtime paths;
- create `genesisvla` compatibility shims.

## Checkpoint And Source Policy

Runtime behavior remains unavailable until a later user-approved task provides:

- source/license review evidence;
- governed source checksum or vendoring decision;
- governed checkpoint URI/path and checksum;
- tokenizer compatibility evidence;
- action-head, mask, and loss compatibility evidence;
- focused tests that prove the adapter obeys AutoVLA model contracts.

Until those fields are present, `gr00t-n1d6` must raise a clear
`ModelAssetsUnavailableError` for forward or action prediction.
