# Cleanup Policy

## Purpose

Cleanup can be destructive. The Manager must not delete files immediately from a user request. Cleanup requires proposal, Manager audit, and explicit user confirmation.

## Required sequence

1. Assign a cleanup-proposal subagent or run a read-only cleanup inventory.
2. Produce a proposal listing each candidate path.
3. For each candidate, include:
   - path;
   - file type and size;
   - what it contains;
   - what role it served;
   - why it appears safe to delete;
   - deletion risk;
   - recovery option;
   - whether it is inside the project repository.
4. Manager audits the proposal and removes unsafe candidates.
5. Manager asks the user for explicit confirmation.
6. Only after confirmation may Manager execute deletion.
7. Record deleted paths and recovery notes in `.agent-docs/progress.txt`.

## Hard exclusions

Do not propose deletion of:

- `code-input/` user-staged code unless user explicitly asks;
- `related-assets/` research assets unless user explicitly asks;
- `datasets/readonly/` original datasets;
- `assets/input/` user inputs;
- files outside the project repository, unless the user gave a one-time external cleanup exception;
- secrets or credentials without user review;
- git metadata unless the user explicitly requests git-history work.
