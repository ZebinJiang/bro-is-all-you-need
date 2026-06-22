# Local Teamwork Workspace

This directory is reserved for project-local Teamwork state.

Expected files:

```text
task-board.md
task-board.md.lock
```

The global Teamwork scripts may be used as providers, but this project should route task state to this local workspace.

The active Codex Manager session metadata is stored one level up:

```text
.agent-docs/teamwork/codex-manager-session.json
```

Do not commit this directory unless the user explicitly changes the local-only governance policy.
