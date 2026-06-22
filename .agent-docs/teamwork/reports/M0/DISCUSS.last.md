M0 DISCUSS is complete. I wrote the full discussion artifact to `.agent-docs/teamwork/reports/M0/DISCUSS.md` and did not modify source/docs/configs/tests/scripts.

===HANDOFF===
Completed:
- Read required governance, blueprint, Teamwork, repository layout, and quality-gate baseline files.
- Ran read-only investigation over docs, pyright config, pre-commit, CI, Makefile, tests, PR template, and GenesisVLA package presence.
- Answered M0 discussion topics A-G.
- Identified decisions, Claude open questions, risks, and PLAN scope recommendation.
- Wrote `.agent-docs/teamwork/reports/M0/DISCUSS.md`.

Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- PLAN must decide whether to create minimal `genesisvla/` stubs and whether to add `pytest`/`pyright` to project dev dependencies.
- PLAN must define the approved worker plan and TDD red-green validation sequence.

Decisions:
- Use `docs/genesisvla/` for GenesisVLA RFC and standards docs.
- Keep M0 quality gates scoped to GenesisVLA/new meta-test paths, not legacy StarVLA backlog.
- Add a new `genesis-check` Make target rather than changing existing `make check`.
- Add a new GenesisVLA CI workflow rather than modifying nonexistent legacy workflows.
- Update existing `.github/PULL_REQUEST_TEMPLATE.md` rather than creating a duplicate lowercase template.

Files Affected:
- .agent-docs/teamwork/reports/M0/DISCUSS.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
