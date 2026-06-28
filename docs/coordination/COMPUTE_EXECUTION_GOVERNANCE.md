# Compute Execution Governance

## Purpose

This policy keeps heavy validation, training, GPU work, and Slurm work out of login-node execution unless a top-level prompt explicitly authorizes the exact action and scope.

The canonical state file is `coordination/COMPUTE_EXECUTION_STATE.yaml`.

## Default posture

Prompt-controlled loops are governance-only unless the resolved loop spec explicitly authorizes compute execution.

Lightweight local checks may run on the login node when they inspect files, parse governance artifacts, validate syntax, or run static drift scans.

Heavy validation, training, evaluation, dataset conversion, inference serving, GPU jobs, and Slurm jobs require explicit authorization and the project compute policy path. The Manager must not start them automatically.

Governance files, loop templates, task cards, and Tool Memory entries must not invent default compute resources. Partition, QoS, node count, GPU count, memory, wall time, account, reservation, and wrapper arguments must come from an explicit top-level prompt, a resolved loop spec, or an already-approved project Slurm configuration. If any required resource decision is absent, the loop records a compute blocker instead of guessing.

## Required compute authorization

A loop spec that authorizes compute must record:

- `compute_authorized`;
- `authorized_actions`;
- `purpose`;
- `command_or_wrapper`;
- `execution_location`;
- `resource_class`;
- `resource_source`;
- `evidence_path`;
- `safety_stop_condition`;
- `expected_output`;
- `rollback_or_cleanup_note`;
- `authorizing_prompt_or_task`;
- `slurm_authorized`;
- `escalation_authorized`;
- `scheduler_policy_ack`;
- `scheduler_rejection_status`.

Missing compute authorization is `BLOCKED_COMPUTE_AUTH` for compute-dependent loops. Missing environment discovery, missing filled Slurm configuration, missing wrapper availability, or missing evidence paths are `BLOCKED_COMPUTE_ENV`. Scheduler-policy conflicts, disallowed bypass attempts, scheduler rejection, or site-policy ambiguity are `BLOCKED_COMPUTE_POLICY`.

These compute blockers are distinct from `BLOCKED_LOOP_SPEC`: a loop can have a syntactically complete spec and still be blocked because compute authorization, environment evidence, or scheduler policy is absent.

## Login-node rule

The login node is limited to lightweight repository checks. If a requested validation appears heavy or resource-consuming, the Manager records the blocker and routes through compute-node or Slurm policy only after explicit authorization.

`LOGIN_NODE_CPU_SATURATION_REQUIRES_COMPUTE_ROUTING` is the durable Tool Memory signature for this failure mode. Full pytest suites, package builds, wheel installs, long Pyright/Black sweeps, dataset conversion, training, evaluation, inference, or any command classified as `heavy_validation` must not continue on the login node unless the resolved loop spec explicitly marks `heavy_validation_on_login_node_allowed: true`. The default is fail-closed routing through Compute/HPC.

Every loop spec that may execute validation commands must classify them with `compute_command_classification`. Allowed lightweight classifications are `file_inspection`, `yaml_json_parse`, `python_syntax_check`, `drift_scan`, and `git_diff_check`. Unknown or heavy classifications require Compute/HPC routing before execution.

## Slurm rule

Slurm work uses project wrappers and records equivalent raw commands, run ids, logs, and output paths. A dry-run or local parse check is not acceptance evidence for real cluster behavior.

Every Slurm command is gated by both compute authorization and Slurm authorization. A loop must not convert a local validation request into `srun`, `sbatch`, queue inspection beyond permitted metadata, cancellation, priority mutation, or scheduler policy probing unless the top-level prompt or resolved loop spec authorizes that exact action.

Escalated shell execution is a separate authorization. Approval to use compute does not imply approval to run a command outside the local sandbox, and sandbox escalation does not imply approval to submit or mutate Slurm jobs.

The Manager and workers must not bypass scheduler policy, cgroups, accounting, partition/QoS limits, reservations, or site resource controls. If the scheduler rejects a job or wrapper preflight because of policy, account, partition, resource, dependency, reservation, or environment constraints, the loop records `BLOCKED_COMPUTE_POLICY` or `BLOCKED_COMPUTE_ENV` as applicable and stops before retrying with broader resources.

`SLURM_SANDBOX_OR_ENV_WRAPPER_RETRY_WITH_ESCALATION` allows a retry of the same approved project wrapper only when Compute/HPC routing, command-local escalation, and the resolved compute policy authorize the exact retry. It does not authorize raw `srun`/`sbatch`.

`SLURM_POLICY_REJECTION_STOP_DO_NOT_BYPASS` is a hard stop. A scheduler policy rejection must not be converted into broader resources, direct raw scheduler commands, or a bypass of accounting/cgroup/site controls.

Git publication may observe Git LFS `locksverify` proxy timeouts. `GIT_LFS_LOCKSVERIFY_PROXY_TIMEOUT_CANDIDATE` is candidate-only advisory memory. It must not become a default, canonical, template, or state-level bypass. A one-off `locksverify=false` retry requires task-specific authorization and scan-clean publication evidence.

## Failure classes

- `BLOCKED_COMPUTE_AUTH`: compute, Slurm, GPU, escalation, or external execution was requested without explicit authorization for the action and scope.
- `BLOCKED_COMPUTE_ENV`: required compute environment evidence is missing, stale, unresolved, or unavailable, including unfilled Slurm config, missing wrapper, missing project environment, or missing evidence path.
- `BLOCKED_COMPUTE_POLICY`: the requested action would bypass or conflict with scheduler/site policy, or the scheduler/wrapper rejected the request for policy or resource reasons.
 - `BLOCKED_COMPUTE_ROUTE`: command classification is heavy, unknown, or compute-required, but no Compute/HPC Owner route and authorization are present.
