---
name: explicit-path-transfer
description: One-time transfer workflow for user-specified external dataset or long-term storage paths.
---

Use this skill when the user explicitly provides an external path for dataset staging or long-term storage.

## Required record

- exact user-provided source path;
- exact destination path;
- direction: inbound or outbound;
- transfer mode: copy, symlink, or manifest-only;
- estimated size;
- reason for transfer;
- command or script used;
- evidence path under `runs/transfers/<run_id>/`;
- statement that the external path is not reusable after this task without new explicit user instruction.

## Hard limits

- Do not browse, scan, or modify external paths beyond the explicit user scope.
- Do not copy full datasets into every run directory.
- Do not use external paths again after task completion without a new user instruction.
