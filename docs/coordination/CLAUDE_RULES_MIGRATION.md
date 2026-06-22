# Legacy Claude Rules Migration Note

## Status

This file is now a migration note, not an active startup dependency.

The active Codex-only governance authority is:

```text
docs/coordination/CODEX_MANAGER_GOVERNANCE.md
```

Root `CLAUDE.md` may remain as a historical archive while the repository transitions away from the previous Claude-supervised Teamwork flow. The active Codex Manager startup path must not require root `CLAUDE.md`.

## Migrated content

The durable rules that were kept are now represented in the active governance file and related coordination files:

- Manager-worker chain.
- One active milestone or validation gate.
- M1 and later worker coverage ledger.
- No inline Manager implementation for behavior-changing work.
- Verification and review as evidence stages, not fix stages.
- Quality evidence before acceptance.
- Publication gate for completed milestones.
- Legacy Teamwork state treated as historical reference unless the user restores Claude-supervised mode.

## Removal rule

Root `CLAUDE.md` can be deleted or moved to a legacy archive only after the active control-plane tests confirm that `AGENTS.md`, `MANAGER_ENTRYPOINT.md`, thread prompts, task cards, and meta tests no longer require it as a live input.
