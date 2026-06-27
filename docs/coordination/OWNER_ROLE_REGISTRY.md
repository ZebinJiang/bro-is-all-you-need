# Owner Role Registry

## Purpose

The Owner Role Registry defines durable role names, thread-level runtime
requirements, expected report duties, and refresh state for prompt-controlled
loops. It is separate from live tool state, Tool Memory, and one-off bootstrap
review evidence.

`docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md` is the normative runtime layer
for Manager -> Owner thread -> Owner-owned child-agent dispatch.

## Required Thread-Level Owners

All eight domain roles below are persistent Owner roles when routed. A routed
role must be refreshed before dispatch, may spawn only direct child agents, and
must return an Owner report before Manager gate acceptance.

| Role | Thread name | Required report responsibility |
| --- | --- | --- |
| Architecture | `10-OWNER · Architecture` | contracts, schema, API, protocol, baseline contamination review |
| Training | `20-OWNER · Training` | training/runtime feasibility, no-auto-compute review, future loop usability |
| Data | `30-OWNER · Data` | dataset immutability, transforms, manifests, evidence-path review |
| Model | `40-OWNER · Model` | model path, policy interface, tensor/action contract review |
| Deployment | `50-OWNER · Deployment` | endpoint, serving, RTC, publication and robot safety review |
| Quality | `60-OWNER · Quality` | scans, validation ledger, completion gate, publication safety review |
| Tooling | `70-OWNER · Tooling` | Tool Memory, connector fallback, tool-environment recovery review |
| Compute/HPC | `80-OWNER · Compute/HPC` | compute, GPU, Slurm, scheduler, login-node safety review |

The Manager remains `00-MANAGER · GenesisVLA Program` and is the control-plane
router. The Manager is not a domain Owner and may not directly substitute for a
domain Owner report.

## Required Role Fields

Every domain Owner entry in `coordination/OWNER_ROLE_REGISTRY.yaml` must carry:

- `role_type: persistent_owner`
- `thread_level: true`
- `can_spawn_child_agents: true`
- `child_agent_depth_limit: 1`
- `requires_role_refresh_before_dispatch: true`
- `owner_report_required: true`
- `completed_no_output_is_approval: false`

Tooling and Compute/HPC additionally use
`lifecycle: create_or_refresh_when_routed`. If no live Tooling or Compute/HPC
thread exists and the top-level prompt routes work to that role, the Manager
records `OWNER_THREAD_REQUIRED` or `ROLE_REFRESH_REQUIRED` before dispatch.

## Child-Agent Ownership

Child agents are owned by exactly one Owner thread. The allowed child-agent
types are:

- Explorer
- Planner
- Implementer
- Reviewer
- Tester
- ToolEnvRunner
- ComputeRunner
- Publisher

ToolEnvRunner is Tooling-owned. ComputeRunner is Compute/HPC-owned. Publisher is
Quality-owned. A child-agent report can be cited only through its parent Owner
report.

## Refresh Classification

Persistent Owners with completed turns but no report or no visible output must
be classified as `OWNER_THREAD_COMPLETED_NO_OUTPUT`. If dispatch cannot be
trusted for that role, record `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`.

This classification blocks approval until a refreshed Owner channel or
explicitly authorized bootstrap fallback produces a valid Owner report.
