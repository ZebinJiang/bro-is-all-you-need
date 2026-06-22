---
name: codex-pr-codereview
description: Review a GitHub PR or GitLab MR for high-signal bugs, regressions, performance risks, baseline contamination, and AGENTS.md violations.
---

## Scope

Review the target PR/MR diff and relevant `AGENTS.md`, `boundaries.txt`, and local governance files. Do not post comments or merge unless the Manager has user authorization.

## Review focus

- compile/runtime errors;
- clear logic bugs;
- baseline-path contamination;
- Slurm/dataset boundary violations;
- missing validation or Slurm evidence;
- time/space complexity regressions;
- GPU/distributed inefficiency;
- Chinese comment/docstring requirement violations;
- unsafe secrets/infra/cluster behavior.

## Output

If issues are found, list each issue with file/line or nearest symbol, severity, confidence, impact, and suggested fix. If no high-signal issues are found, say so directly.
