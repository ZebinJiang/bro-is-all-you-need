# Explicit External Path Transfer Policy

## Purpose

The default sandbox boundary is the project repository. Sometimes the user may explicitly provide an external dataset path or a long-term storage path. In that case, the Manager may use a one-time exception for the exact path and task.

## Requirements

A valid external path exception must include:

- exact external source or destination path from the user;
- transfer direction: inbound dataset/reference asset or outbound long-term storage;
- purpose of the transfer;
- destination inside the project or external long-term storage path;
- whether copying, symlinking, or manifest-only registration is desired;
- expected size or size-estimation command when feasible.

## Allowed destinations

Inbound data should normally go to one of:

```text
datasets/readonly/   # original immutable dataset source files
datasets/working/    # derived/filtered/patched data
datasets/cache/      # reusable cache/index/features
assets/input/         # non-dataset reference assets
```

Outbound long-term artifacts may go to a user-specified external storage path only for the specific task. After the task, the Manager and subagents may not touch that path again without a new explicit user instruction.

## Transfer records

Use `scripts/data/transfer_explicit_path.sh` or an equivalent recorded command. Record:

- source;
- destination;
- direction;
- transfer mode;
- command;
- run id;
- manifest path;
- risk and recovery notes.

The transfer manifest should live under:

```text
runs/transfers/<run_id>/outputs/transfer_manifest.json
```

## Capacity rule

Do not copy full datasets into every run directory. Prefer project-level dataset directories, manifests, references, or symlinks where site policy permits.
