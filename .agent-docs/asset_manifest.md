# Asset Manifest

Register user-provided assets used by validation, examples, experiments, Slurm jobs, code integration, research planning, or one-time external transfers. User-provided inputs are immutable unless the user explicitly asks for mutation.

## Asset categories

- `code-input`: user-provided code staged under `code-input/`.
- `related-asset`: papers, notes, open-source repositories, patches, or reference implementations staged under `related-assets/`.
- `dataset-source`: original dataset files under `datasets/readonly/`.
- `dataset-derived`: derived reusable artifacts under `datasets/working/` or `datasets/cache/`.
- `vla-baseline-source`: source implementation for a registered VLA baseline.
- `vlm-checkpoint`: VLM checkpoint or weight artifact.
- `llm-checkpoint`: LLM checkpoint or weight artifact.
- `vision-backbone-checkpoint`: vision backbone checkpoint or weight artifact.
- `policy-checkpoint`: VLA policy checkpoint or action-head artifact.
- `tokenizer`: tokenizer, vocabulary, or preprocessing artifact.
- `robot-embodiment-config`: robot morphology, action space, or embodiment config.
- `simulator-environment-config`: simulator or benchmark environment config.
- `inference-serving-config`: local or remote inference/serving config.
- `evaluation-benchmark-config`: benchmark or evaluation config.
- `config`: reference config.
- `document`: paper, note, design doc, or report.
- `external-source-once`: user-explicit external source path used for one task only.
- `external-storage-once`: user-explicit external long-term storage path used for one task only.
- `other`: anything else.

## Template

```text
Asset name:
Path:
Type: code-input | related-asset | dataset-source | dataset-derived | vla-baseline-source | vlm-checkpoint | llm-checkpoint | vision-backbone-checkpoint | policy-checkpoint | tokenizer | robot-embodiment-config | simulator-environment-config | inference-serving-config | evaluation-benchmark-config | config | document | external-source-once | external-storage-once | other
Provided by:
Checksum, if available:
Allowed use: planning | local smoke | dry-run | Slurm validation | training | evaluation | inference | serving | reference only | one-time transfer
Mutation allowed: no | yes, with reason
Contains sensitive data: no | yes, describe handling constraints
Expected target or use:
One-time external path scope, if applicable:
Transfer manifest path, if applicable:
Notes:
```

## Registered assets

Asset name: FluxVLA source snapshot
Path: `code-input/FluxVLA-main.zip`
Type: code-input
Provided by: user
Checksum, if available: sha256 `aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d`
Allowed use: planning | reference only
Mutation allowed: no
Contains sensitive data: unknown until inspected; treat as third-party source and do not copy into implementation without license review and attribution
Expected target or use: read-only reference for AutoVLA planning, especially runner lifecycle, deployment/inference patterns, acceleration hooks, registry/config organization, checkpoint lifecycle, and engineering closure patterns described in the AutoVLA blueprint
One-time external path scope, if applicable: n/a
Transfer manifest path, if applicable: n/a
Notes: Source archive is staged input under `code-input/`. Do not mutate or directly integrate. Any integration must go through Code-Input Integration Workflow, Claude-approved worker plan, license/source attribution review, and file-header attribution for copied code.

Asset name: Dexbotic source snapshot
Path: `code-input/dexbotic-main.zip`
Type: code-input
Provided by: user
Checksum, if available: sha256 `a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30`
Allowed use: planning | reference only
Mutation allowed: no
Contains sensitive data: unknown until inspected; treat as third-party source and do not copy into implementation without license review and attribution
Expected target or use: read-only reference for AutoVLA planning, especially dataclass/typed config ideas, transform pipeline organization, backend enum/config patterns, and maintainability lessons described in the AutoVLA blueprint
One-time external path scope, if applicable: n/a
Transfer manifest path, if applicable: n/a
Notes: Source archive is staged input under `code-input/`. Do not mutate or directly integrate. Any integration must go through Code-Input Integration Workflow, Claude-approved worker plan, license/source attribution review, and file-header attribution for copied code.
