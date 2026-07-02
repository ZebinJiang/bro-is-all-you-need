# Data Format Decision Summary

This summary consolidates the M3 data-format publication state after PR #20.
It is a decision-support record, not a final training backend selection.

| Candidate | Evidence | Current decision |
| --- | --- | --- |
| Raw ZJH / LeRobot v2.1 | Source baseline and bounded decode comparator. | Keep as source baseline and likely next telemetry path. |
| WebDataset-native | PR #19 native timing and PR #20 pipeline suite. | First measured candidate; fastest in native-loader timing evidence. |
| Robo-DM-style | PR #19 showed close timing and PR #20 retained it as AutoVLA-owned candidate. | Keep as secondary formal comparison route. |
| WebDataset streaming Training Store | PR #16 draft, CPU benchmark p50 slower than raw decode. | Reviewable research artifact, not performance-ready. |
| LeRobot v3 | Required comparison path. | Dependency-blocked until approved local route exists. |

## Boundaries

- No generated candidate stores, source media, checkpoints, model weights, or
  dataset dumps are tracked by this archive.
- No fine-tune, model load, tokenizer load, Hugging Face operation, W&B
  operation, Slurm run, endpoint, robot, or deployment action is authorized by
  this summary.
- Final backend class remains `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

## Recommended Next Telemetry Direction

Use the raw path with heavy telemetry for the next GR00T-N1.6 dry-run gate, then
compare WebDataset-native and Robo-DM-style candidates under an explicitly
selected uv environment profile.
