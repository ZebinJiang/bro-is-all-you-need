# Tool Environment Lessons

## Worktree-local Tooling

Several earlier validation tasks relied on `runs/tmp/m1-tool-venv` inside a
specific worktree. That venv is ignored and worktree-local; it does not
propagate to new branches, detached validation worktrees, or root main after
sync. Reports that depend on such a venv must record the exact worktree and
path.

## Git and GitHub Tooling

Sandboxed git operations may fail when they need to write `.git/FETCH_HEAD`,
`.git/index.lock`, `.git/ORIG_HEAD.lock`, or `.git/worktrees/**`. When a task
authorizes the exact git mutation, retry only that exact command in the approved
escalated environment and record the sandbox failure separately from a real git
or credential failure.

GitHub CLI authentication failures inside the sandbox should be rechecked in an
approved escalated environment before being treated as real credential blockers.
Do not write tokens or credential material to repository files or logs.

## Proxy Use

Network commands may use the user-provided proxy only for the command that needs
network access:

```bash
export http_proxy=http://192.168.32.11:18000
export https_proxy=http://192.168.32.11:18000
```

Do not persist these variables to global shell, Conda, Slurm, or system
configuration.

## uv Direction

AutoVLA should move toward uv-managed profile environments. A single universal
environment for every model zoo backend is rejected because model-specific
dependencies can be large, mutually incompatible, CUDA-sensitive, or restricted
by local asset availability.
