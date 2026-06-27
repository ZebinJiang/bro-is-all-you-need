# New Thread Bootstrap

## Purpose

This document bootstraps new Codex Manager, Owner, and short-lived worker threads for prompt-controlled loops.

## Required startup order

Each new thread reads:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
5. `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`
6. `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`
7. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
8. the assigned task card or loop spec
9. the relevant role charter or loop prompt template

The active model label remains `gpt-5.5` unless the top-level user prompt explicitly changes it.

## Prompt-first behavior

The Manager proceeds from the top-level prompt. It does not conduct a default interview. It asks the user only when required policy, authorization, validation evidence, external action, deletion, credential, endpoint, budget, timeout, or publication information is missing or ambiguous.

## Fail-closed startup checks

Before work starts, the thread checks:

- repository path and branch;
- task id and loop id;
- allowed write paths and protected paths;
- required Owner routes;
- budget and timeout policy source;
- compute authorization;
- validation evidence ledger path;
- scan gate;
- exact-head and PR visibility gate;
- Owner Dispatch Memory path;
- Tool Memory policy.

Any missing or ambiguous required field results in `BLOCKED_LOOP_SPEC`.

## Silent Owner handling

If a persistent Owner dispatch records a completed turn with no visible output or missing report, the Manager records:

- `OWNER_THREAD_COMPLETED_NO_OUTPUT`
- `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`

The completed turn is not approval and must not satisfy required-review evidence.
