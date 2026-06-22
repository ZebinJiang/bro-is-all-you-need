---
name: integrating-starvla-components
description: Use when adding or modifying StarVLA models, backbones, action heads, datasets, benchmarks, training configs, inference bridges, or evaluation adapters.
---

# Integrating StarVLA Components

Use this skill for StarVLA engineering work before changing model, data, training, inference, or evaluation paths.

## Core Workflow

1. Inspect the current StarVLA layout first: `starVLA/model`, `starVLA/config`, `starVLA/dataloader`, `starVLA/training`, `examples`, and `docs/agent_skills`.
2. Identify whether the task is model/framework work, dataset/benchmark integration, inference/eval bridge work, or training configuration work.
3. Load only the relevant reference:
   - dataset, benchmark, or robot integration: read `references/starvla-dataset-template-map.md`.
   - model, backbone, action head, framework, or policy modification: read `references/starvla-model-integration.md`.
4. Prefer StarVLA-native extension points and examples over new wrapper trees. Do not create a competing `src/` layout.
5. Keep baseline changes explicit. If editing an existing framework or backbone path, record why an adapter/config overlay is insufficient.
6. Validate in tiers: local static checks first; smoke training/eval only when resources and Slurm policy allow it.

## Template Assets

This skill bundles a snapshot of StarVLA's upstream agent templates under `assets/integrate-starvla-dataset/templates/`.

Treat the canonical upstream copies as:

`docs/agent_skills/integrate-starvla-dataset/assets/templates/`

Before using or modifying a bundled template, compare it with the canonical StarVLA copy and prefer the canonical file when it differs.

## Required Outputs

For implementation plans or subagent assignments, include:

- target StarVLA files and closest existing examples;
- model/data/action tensor shapes and normalization assumptions;
- config keys and CLI overrides involved;
- dataset modality/schema requirements when relevant;
- validation commands and expected evidence;
- baseline contamination risk and rollback notes.

## Common Mistakes

- Treating `docs/agent_skills` as executable Codex skills. They are StarVLA engineering templates, not `SKILL.md` entrypoints.
- Editing existing framework paths without first checking whether a new config, registry entry, adapter, or example-local bridge is enough.
- Forgetting that `modality.json` language conditioning expects `annotation.human.task_description.original_key` to map to `task_index`.
- Training with `action_horizon` that does not match `data_config.py` action indices.
- Returning normalized actions from eval bridges when the benchmark expects physical, un-normalized actions.
