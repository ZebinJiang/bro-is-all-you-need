# Owner Topology Governance

## Purpose

Owner topology is the normative role-separation contract for prompt-controlled
loops. It records who owns the specification, delivery, implementation, review,
publication, tool recovery, and compute authorization before the Manager may
dispatch Owners or child agents.

Missing or inconsistent topology fails closed as `BLOCKED_OWNER_TOPOLOGY`.
Spec shape errors that prevent topology parsing may still fail as
`BLOCKED_LOOP_SPEC`.

## Required Topology Fields

Every resolved loop spec includes `owner_topology` with at least:

- `task_class`
- `spec_owner`
- `delivery_owner`
- `reviewer_owner` or `reviewer_owners`
- `fallback_policy.blocked_status: BLOCKED_OWNER_TOPOLOGY`
- `fallback_policy.compatibility_shim_decision: READY_FOR_USER_DECISION_COMPATIBILITY_SHIM`

The topology may also include:

- `implementation_owner` or `implementation_owners`
- `publisher_owner`
- `tooling_owner`
- `compute_owner`
- `write_scope`
- `compatibility_shim`

## Task Classes

Allowed `task_class` values are:

- `small_domain_task`
- `governance_task`
- `tooling_task`
- `packaging_task`
- `cross_cutting_refactor`
- `repo_wide_rename`
- `publication_task`
- `compute_task`

`cross_cutting_refactor` and `repo_wide_rename` are risky cross-cutting task
classes. They require explicit implementation and reviewer Owners.

## Fail-Closed Rules

The Manager stops with `BLOCKED_OWNER_TOPOLOGY` when any rule below is true:

- Cross-cutting or repo-wide work omits topology or omits implementation or
  reviewer Owners.
- A non-empty `write_scope` is present without `implementation_owner` or
  `implementation_owners`.
- Publication, PR mutation, ready transition, merge, or remote branch update is
  authorized without `publisher_owner`.
- Tool recovery, wheelhouse fill, dependency fill, or toolenv recovery is
  authorized without `tooling_owner`.
- Compute, GPU, Slurm, scheduler, or dependency execution is authorized without
  `compute_owner`.
- One Owner is the sole implementation Owner and sole reviewer Owner on a risky
  cross-cutting task.
- An implementation Owner is listed but that Owner has no `Implementer` child.
- A publisher Owner is listed for PR publication but that Owner has no
  `Publisher` child.
- A compatibility shim is implicitly authorized instead of returning
  `READY_FOR_USER_DECISION_COMPATIBILITY_SHIM`.

## Reviewer Does Not Patch

Reviewer Owners do not patch the code or governance artifact they are reviewing.
They may write only their approved review report/evidence. If a reviewer finds
a defect, the Manager returns to an implementation Owner or records the blocker.

Quality keeps scan, validation, exact-head, and publication safety authority
separate from implementation authority. Quality may own a `Publisher` child for
scan-gated publication, but Quality must not act as the sole implementation and
sole reviewer Owner on risky cross-cutting work.

## Data Owner Guidance

Data may be an `implementation_owner` only for scoped data contracts,
manifests, fixture policy, dataset evidence, and transform/data-governance
artifacts that the prompt explicitly assigns to Data.

Data is a `reviewer_owner` when the task changes a broad rename, repo-wide
path, compatibility policy, or other cross-cutting surface that could affect
dataset provenance, immutable input policy, generated fixture policy, or data
evidence paths. In that reviewer role Data does not patch; it verifies that the
implementation Owner preserved data contracts and governed paths.

For an AutoVLA rename, Data is normally a reviewer Owner for dataset/path
impact. Data is not the implementation Owner unless the prompt assigns a data
contract write scope to Data and routes a Data `Implementer` child.

## Model Owner Guidance

Model may be an `implementation_owner` only for scoped model contracts,
interfaces, policy/tensor/action shape records, or model-governance artifacts
that the prompt explicitly assigns to Model.

Model is a `reviewer_owner` when the task changes a broad rename, compatibility
policy, model-family naming surface, or any repo-wide reference that could
affect model contracts. In that reviewer role Model does not patch; it checks
that the implementation Owner preserved model semantics and did not imply
unvalidated runtime support.

For an AutoVLA rename, Model is normally a reviewer Owner for naming and model
contract impact. Model is not the implementation Owner unless the prompt
assigns a model contract write scope to Model and routes a Model `Implementer`
child.

## AutoVLA Rename Topology

An AutoVLA repo-wide rename uses:

- `task_class: repo_wide_rename`
- `spec_owner: Product/Spec`
- `delivery_owner: Architecture`
- `implementation_owner: Engineering/Codebase Migration`
- `reviewer_owners`: Architecture, Data, Model, Training, Quality
- `publisher_owner`: Quality when PR publication is authorized
- `tooling_owner`: Tooling only when tool recovery is authorized
- `compute_owner`: Compute/HPC only when compute or scheduler execution is
  authorized

Architecture owns delivery/spec integration for the reference topology so that
delivery authority is independent from the Engineering implementation writer.
Engineering/Codebase Migration remains the implementation Owner when the prompt
assigns the rename write scope to that role.

Data and Model are reviewer Owners for the rename unless their own data/model
contract write scopes are explicitly assigned with corresponding Implementer
children.

Tooling, Deployment, and Compute/HPC are not mandatory reviewer Owners in the
reference topology when no tool recovery, connector fallback, endpoint, robot,
serving, compute, GPU, Slurm, or scheduler surface is authorized. If any of
those surfaces is authorized, the relevant Owner must be routed and the loop
fails closed without the matching topology role.

Compatibility shim behavior is not implicit. If a rename raises a compatibility
shim question, the loop returns
`READY_FOR_USER_DECISION_COMPATIBILITY_SHIM` before implementing or publishing
that shim.
