# StarVLA Model Integration

Use this reference when adding or modifying StarVLA models, Qwen/VLM backbones, action heads, framework classes, policy decoders, inference paths, or training behavior.

## Start With Existing Paths

Inspect these locations before designing changes:

- `starVLA/model/framework/` for framework classes and `build_framework` usage.
- `starVLA/model/modules/` for reusable model modules and action components.
- `starVLA/config/training/` and `starVLA/config/frameworks/` for config patterns.
- `starVLA/training/train_starvla.py` and related `train_*` entrypoints for CLI overrides and trainer behavior.
- `examples/*/train_files/*.yaml` for real framework/dataset config combinations.
- `examples/*/eval_files/model2*_interface.py` for benchmark bridge patterns.

## Model Change Checklist

1. Identify the closest existing framework/backbone/action-head example and cite exact files.
2. Decide whether the change belongs in config, a registry entry, an adapter, a subclass, or an existing framework file.
3. Record tensor contracts: image batch shape, language input form, state shape, action horizon, action dimension, and normalized vs physical action space.
4. Check memory and distributed implications: backbone size, attention implementation, gradient checkpointing, mixed precision, CPU/GPU transfers, and synchronization points.
5. Preserve baseline behavior by gating new behavior behind explicit config names or new classes.
6. Keep new code comments and docstrings in Chinese per project rule.
7. Add or update a minimal example config under the natural StarVLA example/config location when the new behavior needs user-facing activation.

## Dataset Template Interaction

Model work often depends on dataset conventions. If the task touches state/action dimensions, action horizon, modality names, robot type, data mix, action normalization, or eval bridge behavior, also read `starvla-dataset-template-map.md` and compare against:

`docs/agent_skills/integrate-starvla-dataset/assets/templates/`

## Validation Expectations

- Local static checks for changed Python/YAML/JSON.
- Shape-level tests or dry-run paths for new forward/predict-action behavior when possible.
- Training smoke only after config and dataset shape checks pass.
- Slurm wrapper dry-run and formal Slurm evidence when the validation requires cluster compute.

## Review Focus

- Accidental baseline contamination in existing framework/backbone paths.
- Wrapper layers that duplicate existing StarVLA abstractions.
- Mismatched `action_horizon`, `action_dim`, `state_dim`, or normalization keys.
- Eval bridges returning normalized actions to environments that expect physical actions.
- Hidden performance regressions from repeated image conversion, CPU/GPU copies, or unbatched per-step work.
