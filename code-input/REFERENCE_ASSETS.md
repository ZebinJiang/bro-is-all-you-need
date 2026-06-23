# Code Input Reference Assets

These assets are tracked for PR review only. They are not GenesisVLA runtime
dependencies, package inputs, CI import targets, or product code.

## Tracking Policy

- `code-input/dexbotic-main.zip` is tracked as the original user-provided source
  archive for review.
- `code-input/FluxVLA-main.zip` is tracked as the original user-provided source
  archive for review.
- `code-input/dexbotic-main/**` is tracked as the extracted reviewable
  reference tree.
- `code-input/FluxVLA-main/**` is tracked as the extracted reviewable reference
  tree.
- `code-input/REFERENCE_ASSETS.md` and `code-input/LICENSE_REVIEW.md` are
  tracked as the local asset review records.
- `code-input/**` must not be imported by GenesisVLA tests or source.
- `code-input/**` must not be included in setuptools package discovery.
- `code-input/**` must not be included in Pyright source includes.
- `code-input/**` must not be included in product Black/Ruff gates except for
  documentation-policy checks on these review records.

## Assets

### dexbotic-main

- Asset name: `dexbotic-main`
- Zip path: `code-input/dexbotic-main.zip`
- Zip size: `34527983` bytes
- Zip SHA256:
  `a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30`
- Extraction path: `code-input/dexbotic-main`
- File count after extraction: `234`
- Top-level directories:
  `.github`, `dexbotic`, `dockerfiles`, `docs`, `hardware`, `playground`,
  `resources`, `script`, `test_data`
- Detected license files: `LICENSE`
- Detected NOTICE/COPYRIGHT files: none detected as standalone files
- README files: `README.md`, `README.zh-CN.md`
- Metadata files: `pyproject.toml`
- Source URL / provenance: local user-provided zip; README references
  `https://github.com/dexmal/dexbotic.git`, `https://dexbotic.com/docs/`, and
  `https://arxiv.org/pdf/2510.23511`
- Redistribution decision: allowed for this review-only PR asset bundle under
  MIT License terms, preserving the original `LICENSE` file.
- Reuse policy: reference-only by default. Any copied or adapted code must
  preserve the MIT license notice and record source path, destination path,
  license, and copied/adapted/inspired classification.
- Publication exclusion: `code-input/**/*.mp4` files are intentionally not
  tracked or uploaded. The original zip is preserved unchanged for provenance;
  extracted MP4 files remain local-only review context and are not runtime
  assets.

### FluxVLA-main

- Asset name: `FluxVLA-main`
- Zip path: `code-input/FluxVLA-main.zip`
- Zip size: `22038177` bytes
- Zip SHA256:
  `aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d`
- Extraction path: `code-input/FluxVLA-main`
- File count after extraction: `458`
- Top-level directories:
  `.github`, `assets`, `checkpoints`, `configs`, `datasets`, `docs`,
  `fluxvla`, `scripts`, `test`, `tools`
- Detected license files: `LICENSE`
- Detected NOTICE/COPYRIGHT files: none detected as standalone files
- README files:
  `README.md`, `README_ja.md`, `README_zh-CN.md`,
  `tools/sarm_annotate/README.md`
- Metadata files: `setup.cfg`, `setup.py`
- Source URL / provenance: local user-provided zip; README references
  `https://huggingface.co/limxdynamics/FluxVLAEngine`,
  `https://fluxvla.limxdynamics.com`, and
  `https://github.com/limxdynamics/FluxVLA/issues/1`
- Redistribution decision: allowed for this review-only PR asset bundle under
  Apache License 2.0 terms, preserving the original `LICENSE` file.
- Reuse policy: reference-only by default. Any copied or adapted code must
  preserve applicable Apache-2.0 attribution/license notices and record source
  path, destination path, license, and copied/adapted/inspired classification.

## Extraction Safety Evidence

- Extraction root was restricted to `code-input`.
- Absolute paths, `..` path components, path traversal, unexpected top-level
  directories, and zip symlink entries were rejected before extraction.
- No target extraction directory existed before extraction, so no existing
  reference tree was overwritten.

## Runtime Boundary

The extracted trees include upstream examples, configs, test fixtures, images,
and small binary fixtures. Extracted MP4 files are excluded from tracking and
upload. The tracked assets remain reference artifacts only. Their presence in
the PR does not authorize GenesisVLA runtime use, package discovery, test
imports, Pyright source inclusion, model checkpoint use, dataset use, or CI
execution against the upstream projects.
