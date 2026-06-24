# License Review For Code Input Reference Records

Task lineage: `GVLA-M1-REVIEW-FIX-001`, tightened by M1 closure Workstream C.

## Decision Summary

Current conclusion: `PASS_REFERENCE_METADATA_ONLY`

Both reviewed user-provided archives contained redistributable open-source
licenses when inspected, but the full archives and extracted source trees are
not tracked in the product PR. Review provenance is preserved as metadata in
`code-input/REFERENCE_ASSETS.md` and `docs/references/upstream_sources.yaml`.

No GenesisVLA source file has been copied or adapted from these assets.

## Asset Decisions

| Asset | License evidence reviewed | Decision |
| --- | --- | --- |
| `dexbotic-main` | Archive path `dexbotic-main/LICENSE` contained MIT License text and a Dexmal copyright notice. | Metadata-only reference is allowed. Full archive/source tracking is removed from the product PR. |
| `FluxVLA-main` | Archive path `FluxVLA-main/LICENSE` contained Apache License 2.0 text. | Metadata-only reference is allowed. Full archive/source tracking is removed from the product PR. |

## NOTICE / COPYRIGHT Review

- `dexbotic-main`: no standalone `NOTICE`, `COPYING`, or `COPYRIGHT` file was
  detected during review; license evidence was in `LICENSE`.
- `FluxVLA-main`: no standalone `NOTICE`, `COPYING`, or `COPYRIGHT` file was
  detected during review; license evidence was in `LICENSE`.

## Reuse Rules

If later work copies, adapts, or substantially rewrites code from either
reference source into GenesisVLA source, the implementing task must record:

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

The reviewed upstream sources are not GenesisVLA runtime dependencies,
distribution package inputs, test imports, Pyright includes, product
lint/format targets, CI execution inputs, datasets, checkpoints, model weights,
or external service configuration.

The original upstream archives and extracted trees should remain local-only
when present in a developer checkout and must not be tracked in the product PR.
