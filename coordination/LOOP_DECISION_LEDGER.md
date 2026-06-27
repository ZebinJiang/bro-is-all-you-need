# Loop Decision Ledger

## GVLA-GOVERNANCE-PROMPT-LOOP-V2-OWNER-RETAIN-001

| Decision | Outcome | Evidence |
| --- | --- | --- |
| Active model label | Preserve `gpt-5.5`. | Prompt-controlled loop docs and state files. |
| Missing required loop fields | Fail closed as `BLOCKED_LOOP_SPEC`. | `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`. |
| Budget and timeout source | Must be supplied by top-level prompt or resolved loop spec. | No numeric fallback values are defined. |
| Silent persistent Owners | Record `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT` and `OWNER_THREAD_COMPLETED_NO_OUTPUT`. | `coordination/OWNER_DISPATCH_MEMORY.yaml`. |
| Owner Dispatch Memory | Separate from Tool Memory. | Dedicated YAML and governance docs. |
| Tool Memory authority | Advisory only. | `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`. |
| Compute execution | Governance-only local checks for this task. | `coordination/COMPUTE_EXECUTION_STATE.yaml`. |
| Draft PR mutation | Requires scans, exact head, and explicit visibility authority. | Prompt loop protocol. |
