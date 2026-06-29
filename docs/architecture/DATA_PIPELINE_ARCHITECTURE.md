# AutoVLA Data Pipeline Architecture

## Layer 1: External Formats

Layer 1 contains external dataset formats such as LeRobot-compatible ZJH datasets. These formats are import sources, not hot training-path APIs. Layer 1 adapters may inspect small metadata files, validate schema shape, and produce dry-run plans. They must not decode media, read parquet rows, fit statistics, convert datasets, or write into `datasets/readonly/**` during readiness review.

## Layer 2: AutoVLA Dataset Artifact

Layer 2 is the AutoVLA Dataset Artifact contract. `DatasetArtifactV1` records normalized metadata:

- dataset manifest and provenance;
- modality mapping for cameras, state, action, language, sample index, and episode index;
- transform declarations;
- statistics scope and action-statistics subset rules;
- small metadata checksums;
- deterministic dataset, transform, and statistics fingerprints.

The statistics scope is exactly one of `action_only`, `vision_language_only`, or `mixed`. Vision-language/dialogue-only data must not contribute to action normalization statistics. Mixed datasets must explicitly declare which action subset is valid for action statistics. Action-only statistics require declared action data.

## Layer 3: Fast Training View

Layer 3 is the future training-optimized view over approved artifacts. It should consume AutoVLA-native manifests, indexes, cached features, and fitted statistics only after a scoped conversion or preparation task creates them under governed paths. Training code should not depend directly on ZJH/LeRobot import layouts, raw media paths, or external-format metadata quirks.

## Import Formats Are Not The Hot Path

External import formats are boundary inputs. They may be inspected by adapters and converted by future governed ingestion tasks, but they are not the runtime contract for fast training. This keeps heavy training code independent from source dataset layout, avoids repeated media/parquet scans, and makes fingerprints/statistics reproducible.

## Current Readiness Boundary

`zjh-adapter` currently provides metadata-only preview and dry-run Artifact JSON writing. It does not perform conversion, media decode, parquet reads, statistics fitting, GPU/Slurm work, model loading, network calls, W&B/HF actions, endpoint calls, or robot actions.
