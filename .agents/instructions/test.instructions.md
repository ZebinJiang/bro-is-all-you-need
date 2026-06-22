---
description: Load these instructions when adding, updating, or running tests.
---

# Test Instructions

- Prioritize tests that cover the changed behavior with minimal runtime.
- Login nodes should run only lightweight structure/static checks.
- Real tests, debug runs, evaluation, and GPU-dependent checks should run on compute nodes through Slurm helpers or formal jobs.
- Use the official GR00T repository's existing test layout and commands when present.
- Do not create a parallel template-owned test framework unless the task requires it.
- Slurm-only behavior cannot be accepted from local smoke alone.
- Record test commands, run ids, output paths, and risks.
