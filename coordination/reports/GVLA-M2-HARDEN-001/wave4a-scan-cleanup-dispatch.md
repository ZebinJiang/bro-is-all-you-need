# GVLA-M2-HARDEN-001 Wave 4A Scan Cleanup Dispatch

## Trigger

Quality Wave 4 publication stopped before commit, push, PR update, and remote
inspection because the first required staged scan failed:

```text
git diff --cached --check
coordination/reports/GVLA-M2-HARDEN-001/wave0-manager-preflight.md:148: new blank line at EOF.
coordination/reports/GVLA-M2-HARDEN-001/wave1-dispatch.md:51: new blank line at EOF.
```

Wave 4 report:
`coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave4-publication.md`.

## Dispatch Decision

Dispatch `60-OWNER - Quality` for a narrow Wave 4A publication scan cleanup.
Quality remains the sole publication writer.

## Allowed Write Scope

Quality may modify only:

- `coordination/reports/GVLA-M2-HARDEN-001/wave0-manager-preflight.md`
- `coordination/reports/GVLA-M2-HARDEN-001/wave1-dispatch.md`
- `coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave4-publication.md`
- `coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave4a-publication.md`

The only authorized content cleanup is removal of the EOF blank-line scan
blockers reported above, plus Quality's own Wave 4A publication report.

## Required Actions

1. Verify workspace:
   - `pwd`
   - `git rev-parse --show-toplevel`
   - `git branch --show-current`
   - `git rev-parse HEAD`
   - `git status --short`
2. Remove only the two EOF blank-line blockers listed above.
3. Restage the same Wave 4 explicit pathspecs, including the Wave 4 and Wave 4A
   publication reports, and do not use `git add .`.
4. Rerun all Wave 4 staged scans.
5. If scans pass, commit, push the existing branch without force, update
   existing Draft PR #2 only, and inspect exact remote/PR SHA evidence.
6. Write:
   `coordination/reports/GVLA-M2-PR2-VERIFY-003/owner-quality-wave4a-publication.md`.

## Hard Boundaries

- No DevSpace MCP.
- No source, test, workflow, bootstrap, or task-state edits.
- No `runs/tmp/**` staging.
- No new PR, merge, force push, reset, restore, clean, rm, stash, or broad
  cleanup.
- Do not mark M2 complete and do not start M3.
- Do not modify `.agent-docs/feature_list.json` pass fields.

## Current Parent State

- Parent remains `BLOCKED_TEST`.
- `request_changes` remains true.
- M2 milestone remains not complete.
