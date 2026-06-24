# Status Report Template

Use this when the user asks for thread-team status, progress, blockers, or what the leader will do next.

```text
Thread-team status.

Leader:
- Thread ID: <leader-thread-id>
- Integration branch: <branch>
- Current phase: <phase number and name>
- Next leader action: <one concrete next action>

Worker roster:
| Role | Thread ID | Branch | Working directory | Responsibility | Startup | Status |
| --- | --- | --- | --- | --- | --- | --- |
| <worker> | <id> | worker-<short-task>-<worker-role> | <path> | <scope> | not-started/started/verified/replaced | registered/dispatched/running/blocked/reported/integrated/archived |

Progress:
- Reports collected: <count>/<count>
- Merge progress: <not-started / current branch / complete>
- Final review: <pending/complete>

Blockers and decisions:
- Active blockers: <none or details>
- Decisions needed from user: <none or details>
- Recent leader decisions: <brief list>

Heartbeat and cleanup:
- Heartbeat automation: <none / active id / deleted>
- Next heartbeat: <time or n-a>
- Cleanup status: <pending/complete/n-a>

Risk notes:
<none or concise details>
```
