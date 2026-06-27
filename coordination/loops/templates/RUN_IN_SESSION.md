# Run In Session

Use this checklist inside an active loop session:

- Confirm `pwd`, git root, branch, head, and status.
- Confirm branch is the loop branch.
- Confirm all writes are inside the loop allowlist.
- Confirm the resolved spec has all required fields.
- Confirm budget and timeout policy came from the top-level prompt or resolved spec.
- Confirm Owner Dispatch Memory path is distinct from Tool Memory path.
- Confirm compute authorization before any heavy command.
- Run local parse, syntax, drift, scope, and diff checks.
- Write validation evidence to the configured report path.
- Stop before commit, push, PR mutation, ready transition, merge, cleanup, or branch mutation unless the loop explicitly authorizes it and gates pass.
