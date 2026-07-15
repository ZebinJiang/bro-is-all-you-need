# Loop Decision Ledger

## AUTOVLA-M9-ARCHITECTURE-COMPLETION-UNIFIED-SEMANTICS-UPSTREAM-INTEGRATION-001

| Decision | Outcome | Evidence |
| --- | --- | --- |
| President routing | The President Manager uses `gpt-5.6-sol / max`. | User override and `coordination/MODEL_ROUTING_POLICY.yaml` schema v5. |
| Non-President routing | Every Owner, worker, validator, compute executor, reviewer, repair writer, publisher, and Manager-facing return uses `gpt-5.6-sol / medium`. | User override and routing policy schema v5. |
| Return mechanics | Execution and return use the same profile; return switching and Return Synthesizer fallback are disabled. | Routing policy and validator. |
| Explicit reasoning levels | `max` remains a valid schema value but is active only for the President Manager in this goal; no reasoning level is silently aliased. | User override and routing policy. |
| Review cadence | Architecture-first construction, one frozen candidate, one final Owner fan-out, one consolidated repair, no Owner re-review. | M9 top-level goal and `coordination/VALIDATION_POLICY.yaml`. |
| PR #34 adoption | PR #34 merged into its stacked base by merge commit `e7a4a7084926a472dc9701acb78f11daebe9dc7e`. | Live GitHub query and merge-parent verification. |

## GVLA-GOVERNANCE-PROMPT-LOOP-V2-OWNER-RETAIN-001

| Decision | Outcome | Evidence |
| --- | --- | --- |
| Historical model label | `gpt-5.5` was the pre-M7 default and is superseded for active routing. | `AUTOVLA-M7-PR33-PRODUCTION-RUNTIME-CLOSURE-GOVERNANCE-ROUTING-001`. |
| Active routing | President Manager uses `gpt-5.6-sol / max`; ordinary non-President execution uses `gpt-5.6-sol / medium`; every non-President Manager-facing return uses `gpt-5.6-sol / max`. | `coordination/MODEL_ROUTING_POLICY.yaml`. |
| Missing required loop fields | Fail closed as `BLOCKED_LOOP_SPEC`. | `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`. |
| Budget and timeout source | Must be supplied by top-level prompt or resolved loop spec. | No numeric fallback values are defined. |
| Silent persistent Owners | Record `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT` and `OWNER_THREAD_COMPLETED_NO_OUTPUT`. | `coordination/OWNER_DISPATCH_MEMORY.yaml`. |
| Owner Dispatch Memory | Separate from Tool Memory. | Dedicated YAML and governance docs. |
| Tool Memory authority | Advisory only. | `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`. |
| Compute execution | Governance-only local checks for this task. | `coordination/COMPUTE_EXECUTION_STATE.yaml`. |
| Draft PR mutation | Requires scans, exact head, and explicit visibility authority. | Prompt loop protocol. |
| PR7 lifecycle | PR #7 merge installs governance but does not activate normal loop mode. | `docs/coordination/LOOP_ACTIVATION_GATE.md`. |
| Runtime smoke | `GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` must pass before PR #6 loop use. | `docs/coordination/OWNER_RUNTIME_SMOKE.md`. |
| Child report authority | Child reports cannot bypass parent Owner reports. | `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md`. |
| Completed-no-output | Completed Owner turns with no output block activation. | `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`. |
| PR #6 ordering | PR #6 exact-head review waits for activation and remains review-only unless separately authorized. | `coordination/LOOP_BACKLOG.yaml`. |

## AUTOVLA-M7-PR33-PRODUCTION-RUNTIME-CLOSURE-GOVERNANCE-ROUTING-001

| Decision | Outcome | Evidence |
| --- | --- | --- |
| 2026-07-13 model override | All ordinary implementation, validation, compute, repair, and publication workers use `gpt-5.6-sol / xhigh`. | User override and `coordination/MODEL_ROUTING_POLICY.yaml`. |
| Owner override | Owner creation, refresh, and dispatch use `gpt-5.6-luna / max`. | User override and routing policy schema v2. |
| Manager return override | Goal Manager and every Manager-facing return use `gpt-5.6-sol / xhigh`; one xhigh Return Synthesizer is the fallback when the raw thread cannot emit that return. | User override and routing policy schema v2. |
| Historical routing evidence | Existing `gpt-5.6-sol / medium` execution and `gpt-5.6-sol / ultra` return records remain immutable pre-override evidence and are not valid for new dispatches. | `runs/tmp/AUTOVLA-M7-PR33-PRODUCTION-RUNTIME-CLOSURE-GOVERNANCE-ROUTING-001/governance/thread-routing-ledger.jsonl`. |
| Runtime smoke | The already completed routing smoke is not rerun; the validator establishes a new policy epoch before the next child is created. | `docs/coordination/OWNER_RUNTIME_SMOKE.md`. |

## AUTOVLA-M8-ARCHITECTURE-FIRST-GPU-DEEPSPEED-MODEL-ASSET-FOUNDATION-001

| Decision | Outcome | Evidence |
| --- | --- | --- |
| President routing | The President Manager uses `gpt-5.6-sol / max`. | User override and `coordination/MODEL_ROUTING_POLICY.yaml`. |
| Execution routing | All non-President implementation, validation, review, compute, repair, and publication execution uses `gpt-5.6-sol / medium`. | User override and routing policy schema v3. |
| Manager-facing return routing | Every non-President Manager-facing blocker or final return uses `gpt-5.6-sol / max`. Same-thread override is preferred; one read-only max Return Synthesizer is the fallback when the execution thread cannot switch. | User override and routing policy schema v3. |
| Historical routing evidence | Earlier xhigh, Luna, or other model-routing rows remain historical evidence only and do not authorize a new M8 dispatch. | Active routing validator and M8 task card. |
