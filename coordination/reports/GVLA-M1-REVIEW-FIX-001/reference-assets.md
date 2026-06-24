# GVLA-M1-REVIEW-FIX-001 Reference Asset Review

## Result

Conclusion: `PASS_REFERENCE_TRACKING_ALLOWED`

The two user-provided code-input archives were inspected before extraction.
Both contain redistributable open-source licenses and were safely extracted into
`code-input` without path traversal, symlink, absolute-path, or overwrite
issues.

## Assets Reviewed

| Asset | Zip | Extraction | Files | License | Redistribution decision |
| --- | --- | --- | ---: | --- | --- |
| `dexbotic-main` | `code-input/dexbotic-main.zip` | `code-input/dexbotic-main` | 234 | MIT | Allowed as review-only reference asset with original `LICENSE` preserved. |
| `FluxVLA-main` | `code-input/FluxVLA-main.zip` | `code-input/FluxVLA-main` | 458 | Apache-2.0 | Allowed as review-only reference asset with original `LICENSE` preserved. |

## Extraction Safety

- Extraction root: `/home/cz-jzb/workspace/vla-flywheel/code-input`
- Accepted top-level zip directories: `dexbotic-main`, `FluxVLA-main`
- Rejected conditions checked before extraction: absolute paths, `..`
  components, path traversal outside `code-input`, unexpected top-level
  directories, and symlink entries.
- Existing target directory status before extraction: neither
  `code-input/dexbotic-main` nor `code-input/FluxVLA-main` existed, so no
  existing extraction tree was overwritten.

## License / Attribution Decision

- `dexbotic-main/LICENSE`: MIT License; original license preserved.
- `FluxVLA-main/LICENSE`: Apache License 2.0; original license preserved.
- Standalone `NOTICE`, `COPYING`, or `COPYRIGHT` files: none detected.
- README and metadata files are preserved in the extracted trees.
- `code-input/dexbotic-main/hardware/xlerobot/demo_collect_longans_into_the_box.mp4`
  is an upstream Git LFS pointer in the provided zip, not a recovered video
  blob. Per user decision, extracted MP4 files under `code-input/**` are not
  tracked or uploaded. The original zip remains tracked unchanged as the source
  artifact.

No code was copied or adapted from these assets into GenesisVLA source as part
of this Manager asset extraction step.

## Reuse Policy

Any future copied or adapted GenesisVLA code must record:

- source path;
- destination path;
- license;
- copied/adapted/inspired classification;
- reason for reuse;
- attribution/header handling.

Inspired-only use must still be recorded in the relevant task report.

## Review-Only Boundary

`code-input/**` is tracked only because the user explicitly requested reviewer
visibility for the reference source and archives. The assets must not become
runtime dependencies, package include targets, test imports, Pyright includes,
GenesisVLA product code, datasets, checkpoints, or CI execution inputs.
