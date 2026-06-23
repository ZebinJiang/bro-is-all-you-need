# Code Input Reference Records

`code-input/` is a local staging area for user-provided references. The full
upstream source archives and extracted trees are intentionally not tracked in
the product PR. Only this review record and `LICENSE_REVIEW.md` remain tracked.

## Current Tracking Policy

- Tracked:
  - `code-input/REFERENCE_ASSETS.md`
  - `code-input/LICENSE_REVIEW.md`
- Not tracked:
  - `code-input/dexbotic-main.zip`
  - `code-input/FluxVLA-main.zip`
  - `code-input/dexbotic-main/**`
  - `code-input/FluxVLA-main/**`
  - binary fixtures such as `.mp4`, `.npy`, `.parquet`, model weights, and
    checkpoints

The reviewable upstream source registry lives in
`docs/references/upstream_sources.yaml`.

## Assets Reviewed Before Removal From PR Tracking

### dexbotic

- Original archive path: `code-input/dexbotic-main.zip`
- Archive SHA256:
  `a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30`
- Upstream repository from README evidence:
  `https://github.com/dexmal/dexbotic.git`
- License evidence reviewed: `dexbotic-main/LICENSE`
- License: MIT
- Reuse status: reference-only; no GenesisVLA source copy/adaptation recorded.

### FluxVLA

- Original archive path: `code-input/FluxVLA-main.zip`
- Archive SHA256:
  `aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d`
- Upstream repository from README evidence:
  `https://github.com/limxdynamics/FluxVLA`
- License evidence reviewed: `FluxVLA-main/LICENSE`
- License: Apache-2.0
- Reuse status: reference-only; no GenesisVLA source copy/adaptation recorded.

## Reuse Policy

Any future copied or adapted code must record:

- source path;
- destination path;
- license;
- reuse class: `copied`, `adapted`, or `inspired`;
- attribution/header handling.

Reference-only use does not make `code-input/**` a runtime dependency, package
input, CI import path, Pyright include, model asset, dataset, or test fixture.
