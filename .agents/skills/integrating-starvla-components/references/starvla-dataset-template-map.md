# StarVLA Dataset Template Map

Use this reference when integrating a new robot, dataset, benchmark, or evaluation environment into StarVLA.

## Canonical Template Sources

Canonical upstream templates live in:

`docs/agent_skills/integrate-starvla-dataset/assets/templates/`

Bundled snapshot templates for this skill live in:

`assets/integrate-starvla-dataset/templates/`

Compare the bundled snapshot against the canonical source before copying. Prefer the canonical StarVLA copy if it has changed.

## Template Roles

| Template | Target location | Purpose |
| --- | --- | --- |
| `data_config.py` | `examples/<BENCH>/train_files/data_registry/data_config.py` | Registers robot data layout, modality config, state/action transforms, embodiment tag, and dataset mixtures. |
| `modality.json` | each LeRobot dataset `meta/modality.json` | Maps video/state/action/annotation keys from raw dataset fields into StarVLA/GR00T modality groups. |
| `training_config.yaml` | `examples/<BENCH>/train_files/starvla_<FRAMEWORK>_<BENCH>.yaml` | Defines framework, backbone path, action/state dimensions, dataset mix, action type, image size, optimizer, and smoke-train settings. |
| `run_train.sh` | `examples/<BENCH>/train_files/run_<BENCH>_train.sh` | Launches `starVLA/training/train_starvla.py` with accelerate/deepspeed and snapshots launcher/config into the run directory. |
| `model2bench_interface.py` | `examples/<BENCH>/eval_files/model2<BENCH>_interface.py` | Bridges a StarVLA checkpoint to the benchmark environment or server for closed-loop evaluation. |

## Required Consistency Checks

- `training_config.yaml.framework.action_model.action_horizon` must match `data_config.py` action indices.
- `training_config.yaml.framework.action_model.state_dim` and `action_dim` must match the total widths of state/action groups in `data_config.py` and `modality.json`.
- `modality.json` must preserve `annotation.human.task_description.original_key = "task_index"` unless the language-conditioning path is deliberately changed and tested.
- `data_config.py` robot type strings must match `training_config.yaml.datasets.vla_data.data_mix` entries and eval bridge `ROBOT_SPECS`.
- Eval bridges should return physical un-normalized actions unless the target benchmark explicitly expects normalized actions.
- `dataset_statistics.json` must travel with checkpoints used by eval bridges.

## Validation Ladder

1. Static import/syntax check for generated Python files.
2. Dataset metadata check: modality keys, state/action slices, dimensions, and task annotations.
3. Local self-test for `model2bench_interface.py` with dummy images/state and a fake or small checkpoint when feasible.
4. Short smoke training with tiny steps only after dataset/config shape checks pass.
5. Closed-loop mock or recorded-episode evaluation before real environment evaluation.
