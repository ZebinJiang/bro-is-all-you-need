---
name: cleanup-proposal
description: Read-only cleanup inventory and deletion proposal for Manager audit and user confirmation.
---

Use this skill before any cleanup/deletion task.

## Required proposal fields

For every candidate path, report:

- path;
- type and size;
- what the file/directory contains;
- what role it served;
- why it appears safe to delete;
- deletion risk;
- recovery option;
- whether it is inside the project root;
- whether it touches protected inputs such as `code-input/`, `related-assets/`, `datasets/readonly/`, or `assets/input/`.

## Workflow

1. Produce a read-only proposal.
2. Manager audits and removes unsafe candidates.
3. Manager asks the user for explicit confirmation.
4. Only after confirmation may deletion execute.

## Hard limits

- Do not delete files.
- Do not propose protected input directories unless the user explicitly named them.
- Do not propose outside-project cleanup unless the user gave a one-time explicit external cleanup path.
