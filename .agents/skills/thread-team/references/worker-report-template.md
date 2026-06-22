# Worker Report Template

Workers send this to the leader thread after implementation, self-review, verification, and commit.

```text
Worker complete and ready for leader integration.

Worker thread ID: <worker-thread-id>
Role: <role>
Branch: <worker-branch>
Commit SHA: <sha>

Task completed:
<summary>

Files changed:
<files>

Self-review:
- Bugs or risks found and fixed: <summary or none>
- Scope drift checked: <yes/no plus notes>
- Generated/cache/unrelated files checked: <yes/no plus notes>
- Shared contracts preserved or changed: <summary>

Peer coordination:
- Peer threads contacted: <thread IDs and outcomes, or none>
- Decisions needing leader awareness: <summary or none>

Verification:
<commands run and results, or why not run>

Unresolved issues:
<none or details>

Ready for leader integration: <yes/no>
```
