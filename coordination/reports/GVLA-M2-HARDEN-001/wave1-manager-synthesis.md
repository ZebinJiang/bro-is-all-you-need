# GVLA-M2-HARDEN-001 Wave 1 Manager Synthesis

## Workspace

- Canonical worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- Branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- Published head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- Current normalized conclusion remains: `BLOCKED_TEST`
- `request_changes`: `true`

## Owner Planning Reports

| Owner | Plan | Conclusion | Manager disposition |
| --- | --- | --- | --- |
| Quality | `runs/tmp/GVLA-M2-HARDEN-001/quality/remote-ci-plan.md` | `PASS` | Q-W1 may proceed first as the only Wave 2 writer. |
| Architecture | `runs/tmp/GVLA-M2-HARDEN-001/architecture/contract-plan.md` | `REQUEST_CHANGES` | Design accepted as actionable; Manager updated the contract task card to include the missing A-W1 scope before dispatch. |
| Data | `runs/tmp/GVLA-M2-HARDEN-001/data/transform-action-plan.md` | `REQUEST_CHANGES` | D-W1 waits until Architecture contract integration is complete. |
| Data | `runs/tmp/GVLA-M2-HARDEN-001/data/batch-statistics-plan.md` | `REQUEST_CHANGES` | D-W1 waits until Architecture contract integration is complete. |
| Data | `runs/tmp/GVLA-M2-HARDEN-001/data/fixture-legacy-plan.md` | `REQUEST_CHANGES` | D-W1 waits until Architecture contract integration is complete. |
| Training | `runs/tmp/GVLA-M2-HARDEN-001/training/m3-consumer-plan.md` | `REQUEST_CHANGES` | M3 readiness can be achieved by planned M2 hardening; no M3 implementation authorized. |
| Model | `runs/tmp/GVLA-M2-HARDEN-001/model/model-consumer-plan.md` | `REQUEST_CHANGES` | M4 readiness can be achieved by planned M2 hardening; no M4/model implementation authorized. |

## Manager Scope Decision

Architecture found that the existing `GVLA-M2-CONTRACT-HARDEN-002` card was too narrow for A-W1 because it omitted statistics ownership and typed batch/collate files needed to close the M3-blocking public contract defects.

Manager updated `coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml` to include:

- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/collate.py`
- `tests/dataloader/test_dataset_statistics.py`
- `tests/dataloader/test_collate.py`

This is a task-scope clarification only. Manager did not implement source, tests, tooling, workflow, or PR changes.

## Wave 2 Order

Wave 2 remains serial, with no parallel writes:

1. `GVLA-M2-REMOTE-CI-003` Q-W1, Quality single writer, to fix fresh-runner CI/bootstrap/build gate and meta policy coverage.
2. `GVLA-M2-CONTRACT-HARDEN-002` A-W1, Architecture single writer, after Q-W1 retires.
3. `GVLA-M2-DATA-HARDEN-002` D-W1, Data single writer, after A-W1 integrates and reviews accept the public contract.
4. `GVLA-M2-PR2-VERIFY-003` Q-W2, Quality single publication writer, only after implementation and full local gate pass.

## Key Decisions For Later Writers

- Preserve local bootstrap default offline-first behavior and exit 66; CI may use bounded `--fill-wheelhouse`.
- CI cache may include only wheelhouse and pip cache, never project-local venvs.
- Transform contract hardening should introduce JSON-safe immutable specs, explicit serializable transform protocol, versioned fingerprints, `TransformContext`, and typed `CollatedBatch`.
- Data should not define a second spec or batch type after Architecture lands the public contract.
- Canonical action mask shape for consumers is `[B,H_max,D_max]`; sample mask is `[H,D]`.
- `first_step_policy="zero"` must be resolved explicitly as lossy, rejected for inverse, or made reversible with reference state.
- Real Parquet/LeRobot fixture claims need explicit dependency/scope approval before being asserted as real-format support.
- M2 remains numpy-only and device-neutral; no M3/M4/training/model implementation is authorized.

## Deviations And Cleanup Debt

- Model Owner first wrote `runs/tmp/GVLA-M2-HARDEN-001/model/model-consumer-plan.md` in the main checkout by relative path, then wrote the canonical worktree file and recorded the deviation.
- The main-checkout stray remains intentionally untouched at `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/GVLA-M2-HARDEN-001/model/model-consumer-plan.md`.
- Manager did not remove or clean the stray. It requires later Manager/user cleanup decision.
- Training Owner had a similar earlier main-checkout write in a prior Wave 5 consultation and reported it was deleted before correction; no new cleanup was performed in this Wave 1 Manager synthesis.

## DevSpace MCP Compliance

- Manager used DevSpace MCP: no.
- Architecture Owner used DevSpace MCP in this task: no.
- Data Owner used DevSpace MCP in this task: no.
- Quality Owner used DevSpace MCP in this task: no.
- Training Owner used DevSpace MCP in this task: no.
- Model Owner used DevSpace MCP in this task: no.
- Evidence depends on DevSpace MCP: no.
- Result: `PASS`.

Historical Owner bootstrap turns may contain DevSpace MCP calls before the repository-internal prohibition was enforced for current tasks; those historical startup-smoke artifacts are not used as execution evidence for `GVLA-M2-HARDEN-001`.

## Subagent Retirement Ledger

- Persistent Owner threads used: Architecture, Data, Quality, Training, Model.
- No new Owner threads created.
- No Owner threads archived.
- Q-RO1: used, retired.
- A-RO1: used directly in Architecture Owner thread, retired.
- D-RO1: used, retired.
- D-RO2: used, retired.
- D-RO3: used, retired.
- T-RO1: used, retired.
- M-RO1: used, retired.
- Write-capable subagents used in Wave 1: none.

## Current Conclusion

`BLOCKED_TEST`

Wave 1 planning is complete and actionable. Proceed to Wave 2 Q-W1 only; do not start Architecture or Data writers until the prior writer retires.
