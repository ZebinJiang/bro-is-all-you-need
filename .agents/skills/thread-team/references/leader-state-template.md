# Leader State Template

Use this compact record while coordinating a thread team.

Persist it to `.thread-team/state.md` under the repo root, kept out of commits via the exclude file located by `git rev-parse --git-path info/exclude` (in a linked worktree `.git` is a file, so do not hardcode `.git/info/exclude`). Update it immediately after every state change. After compaction or interruption, reread this file before acting.

```md
Thread-team leader state.

Leader thread ID:
Integration branch:
Repo path:
User objective:
Worker runtime settings:
- Model: Codex app default / <explicit user-requested model>
- Thinking: Codex app default / <explicit user-requested reasoning level>

Team roster:
| Role | Thread ID | Branch | Working directory | Responsibility | Startup | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Leader | <id> | <branch> | <leader-checkout-path> | Plan, decide, poll, merge, final review | n/a | active |
| <worker> | <id> | worker-<short-task>-<worker-role> | <worktree-path> | <scope> | not-started/started/verified/replaced | registered/dispatched/running/blocked/reported/integrated/archived |

Retired workers:
- <old worker>: archived, replaced by <new worker>, reason <startup stuck/no post-dispatch response/etc.>

Workspace isolation:
- <worker>: working directory <path>, branch <branch>, HEAD <sha>, verified yes/no

Dependency map:
- <dependency>

Decision log:
- <decision>

Polling state:
- Phase 4 mode: startup-gate/heartbeat-polling/complete
- Heartbeat automation: <id, or none / deleted>
- Last heartbeat:
- Next heartbeat:
- Workers awaiting reports:
- Stall watch: <worker: passes with no activity, or none>

Worker reports:
- <worker>: pending/received, commit <sha>

Merge order:
1. <worker branch>
2. <worker branch>

Integration log:
- <branch>: <merge result> / <per-merge verification result>

Final review:
- pending/complete

Cleanup:
- Heartbeat automation deleted: yes/no/n-a
- Leader-created worktrees removed: yes/no/n-a
```
