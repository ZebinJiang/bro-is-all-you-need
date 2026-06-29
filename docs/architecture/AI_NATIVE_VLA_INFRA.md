# AutoVLA AI-Native VLA Infrastructure

## Objective

AutoVLA is evolving from a narrow training-script surface into AI-native VLA
infrastructure. The active direction is to keep model, data, training,
evaluation, deployment-adjacent validation, and Agent-readable module ownership
separable while making every boundary auditable through registries, manifests,
and task evidence.

## Current M3.1 Readiness Tranche

This tranche installs the first dataset/model readiness boundary:

- ZJH/LeRobot-v2-compatible metadata adapter.
- AutoVLA Dataset Artifact v1 metadata contract.
- GR00T N1.6/N1.6.1 model-zoo metadata skeleton.
- Read-only local baseline metrics parser.
- Module docs and finetune-readiness report.

It does not authorize finetune, real model loading, tokenizer loading,
checkpoint download, full dataset conversion, W&B/HF network actions, GPU,
Slurm jobs, endpoint calls, or robot actions.

## Infrastructure Pillars

- Model zoo and native adapters: preserve native GR00T/PI/StarVLA functional
  chains conceptually while routing entrypoints through AutoVLA registry and
  adapter contracts.
- Data architecture: treat LeRobot/GR00T/RLDS/Dexdata/HDF5 as import formats,
  not the hot training path.
- Fast training view: future training consumes optimized AutoVLA artifacts with
  precomputed indexes, statistics, tokens, cache metadata, and measurable
  data-to-compute timing.
- Governance evidence: every milestone keeps reportable Owner decisions,
  validation evidence, and publication status.

## Non-Goals

- No compatibility shim for `genesisvla`.
- No external repository vendoring without license review.
- No hidden dependency expansion.
- No generated dataset/media/checkpoint artifacts in PRs.
- No runtime claim without focused tests and governed source/checkpoint evidence.

## Next Planning Questions

- Which DataLoader Perf Harness counters become M3.2 gate warnings versus hard
  failures?
- Which GR00T source/license/checkpoint evidence is sufficient for a later dry-run
  finetune plan?
- Which optimized training-store format should back the first real AutoVLA fast
  training view?
