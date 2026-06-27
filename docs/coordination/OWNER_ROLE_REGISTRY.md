# Owner Role Registry

## Purpose

The Owner Role Registry defines durable role names, expected report duties, and refresh state for prompt-controlled loops. It is separate from live tool state and separate from Tool Memory.

## Required roles

| Role | Thread name | Required report responsibility |
| --- | --- | --- |
| Manager | `00-MANAGER · GenesisVLA Program` | control-plane routing, loop status, user report |
| Architecture | `10-OWNER · Architecture` | contracts, schema, API, protocol, baseline contamination review |
| Training | `20-OWNER · Training` | training/runtime feasibility and no-auto-compute review |
| Data | `30-OWNER · Data` | dataset immutability and evidence-path review |
| Model | `40-OWNER · Model` | model path, policy interface, tensor contract review |
| Deployment | `50-OWNER · Deployment` | endpoint, serving, RTC, publication safety review |
| Quality | `60-OWNER · Quality` | scans, validation ledger, completion gate review |
| Tooling | short-lived or registered Owner | tool memory, connector action, local fallback review |
| Compute/HPC | short-lived or registered Owner | compute, GPU, Slurm, login-node safety review |

## Refresh classification

Persistent Owners with completed turns but no report or no visible output must be classified as `OWNER_THREAD_COMPLETED_NO_OUTPUT`. If dispatch cannot be trusted for that role, record `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`.

This classification blocks approval until a refreshed Owner channel or approved replacement reviewer produces a report.
