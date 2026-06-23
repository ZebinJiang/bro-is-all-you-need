# License Review For Code Input Reference Assets

Task: `GVLA-M1-REVIEW-FIX-001`

## Decision Summary

Current conclusion: `PASS_REFERENCE_TRACKING_ALLOWED`

Both reviewed source archives contain redistributable open-source licenses and
preserve their original license files in the extracted trees. The assets may be
tracked in the PR as reference-only review evidence, subject to the boundaries
below.

No GenesisVLA source file has been copied or adapted from these assets in this
task at the time of this review.

## Asset Decisions

| Asset | License evidence | Decision |
| --- | --- | --- |
| `dexbotic-main` | `code-input/dexbotic-main/LICENSE` contains MIT License text and copyright notice for Dexmal. | Redistribution allowed for review-only source/reference tracking when the original license file is preserved. |
| `FluxVLA-main` | `code-input/FluxVLA-main/LICENSE` contains Apache License 2.0 text. | Redistribution allowed for review-only source/reference tracking when the original license file is preserved. |

## NOTICE / COPYRIGHT Review

- `dexbotic-main`: no standalone `NOTICE`, `COPYING`, or `COPYRIGHT` file was
  detected. The MIT `LICENSE` file is preserved.
- `FluxVLA-main`: no standalone `NOTICE`, `COPYING`, or `COPYRIGHT` file was
  detected. The Apache-2.0 `LICENSE` file is preserved.
- README and package metadata files are preserved in the extracted trees.

## Reuse Rules

If later work copies, adapts, or substantially rewrites code from either
reference tree into GenesisVLA source, the implementing task must record:

- source path;
- destination path;
- license;
- reuse class: `copied`, `adapted`, or `inspired`;
- reason for reuse;
- attribution or header handling.

Direct copies or adaptations must preserve original license and copyright
notices where present. Inspired-only design references do not require source
headers, but must still be recorded in the task report.

## Non-Runtime Policy

Tracking these assets does not make them part of GenesisVLA runtime,
distribution package inputs, test imports, Pyright includes, product lint/format
targets, CI execution inputs, datasets, checkpoints, model weights, or external
service configuration.

The tracked upstream fixtures under `code-input/**`, including `.npy` files,
images, PDFs, and zipped source archives, are accepted only as reviewable
reference assets under the user's explicit decision for this task. Extracted
MP4 files under `code-input/**` are intentionally excluded from tracking and
upload.

`code-input/dexbotic-main/hardware/xlerobot/demo_collect_longans_into_the_box.mp4`
is an upstream Git LFS pointer in the provided zip, not a recovered video blob.
The extracted `.gitattributes` preserves the original upstream LFS rule, but
the extracted MP4 file itself is not tracked or uploaded. The original zip
remains tracked as the source artifact.
