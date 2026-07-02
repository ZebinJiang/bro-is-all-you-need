# AutoVLA Data Format Pipeline Suite

## Purpose

`AUTOVLA-M3-DATA-FORMAT-PIPELINE-SUITE-001` turns PR #19 timing evidence into
first-class AutoVLA data-format candidates for the next formal telemetry run.
It does not select the final training backend and does not start fine-tuning.

## Candidate Matrix

| Candidate | Role | Implementation status | Dependency mode |
| --- | --- | --- | --- |
| Raw ZJH / LeRobot v2.1 | Source baseline | Manifest and bounded read comparator | No new dependency |
| WebDataset-native | First-class candidate | Build, validate, and benchmark entrypoints | Approved `webdataset==1.0.2` package route |
| Robo-DM-style | First-class candidate | AutoVLA-owned container/index route | No upstream Robo-DM package claim |
| LeRobot v3 | Required comparison route | Explicit dependency decision path when local route is absent | Dependency-blocked unless separately approved |

## Contract

Every runnable candidate emits a common data-format manifest with:

- source dataset path and fingerprint;
- generated artifact root, file count, size, and checksum manifest;
- sample, episode, camera, action, and state dimensions;
- payload contract for action, language, state, action mask, and three RGB
  camera streams;
- `generated_artifacts_tracked=false`;
- `no_source_mutation=true`;
- `no_training=true`;
- `no_model_load=true`;
- no checkpoint, tokenizer, HF, W&B, endpoint, or robot side effects.

## Entry Points

```bash
python -m autovla.dataloader.format_pipeline build-validate-benchmark \
  --source-dataset /home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz \
  --working-root /home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_data_format_pipeline_suite \
  --output-dir runs/tmp/AUTOVLA-M3-DATA-FORMAT-PIPELINE-SUITE-001/pipeline-output \
  --max-episodes 4 \
  --max-samples 512 \
  --samples-per-shard 128 \
  --seed 11 \
  --worker-count 8 \
  --candidate raw_zjh_lerobot_v21_baseline \
  --candidate webdataset_native \
  --candidate robodm_style \
  --candidate lerobot_v3
```

Generated stores stay under `datasets/working/autovla_data_format_pipeline_suite/**`
and must not be staged.

## Relationship To PR #19

PR #19 selected WebDataset-native in bounded timing evidence:

| Candidate | p50 ms | p95 ms | Interpretation |
| --- | ---: | ---: | --- |
| WebDataset-native | 26.743256 | 50.360388 | Current fastest measured route |
| Robo-DM-style | 30.076333 | 38.863741 | Close comparator retained |
| Raw ZJH / LeRobot v2.1 | 171.072641 | 189.900773 | Baseline dominated by raw media decode |

This suite uses that evidence to prepare comparable format candidates. The final
training backend decision is deferred to the next formal telemetry stage.
