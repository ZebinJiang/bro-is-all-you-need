# P0 PLAN — GenesisVLA Supervision Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use the project `feature-dev` / `coding_integration_engineer` path approved by Claude for P0 EXECUTE. This plan is not self-approved; EXECUTE starts only after Claude chooses `approve_execute`.

**Goal:** Build the project-local Codex Manager dispatch wrapper for P0 without changing StarVLA source, tests, configs, datasets, Slurm config, or baseline paths.

**Architecture:** Add one Python CLI at `scripts/teamwork/dispatch_codex_manager.py`. The wrapper resolves local Teamwork paths, validates boundaries, renders a Codex command preview, executes `codex exec` or `codex exec resume`, writes `.last.md` output only, updates local session metadata, and appends one dispatch event. It remains dispatch/routing infrastructure and never chooses milestones, approves gates, submits Slurm jobs, pushes, opens PRs, or marks completion.

**Tech Stack:** Python 3 standard library only: `argparse`, `datetime`, `json`, `os`, `shlex`, `subprocess`, `sys`, and `pathlib`.

---

## Current Workspace Note

A prior EXECUTE dispatch in this same conversation was interrupted by a newer PLAN-only
instruction after the approved worker had already created
`scripts/teamwork/dispatch_codex_manager.py`. Before this latest PLAN dispatch, that
worker also applied a narrow resume-command-order fix. This PLAN stage does not
validate, accept, modify, or roll back that file. It remains an interruption artifact
for Claude Supervisor to consider when deciding the next gate.

## Plan Scope

The EXECUTE stage is scoped to exactly one source artifact:

```text
scripts/teamwork/
  dispatch_codex_manager.py
```

No other source files, scripts, tests, baseline paths, dataset files, Slurm configs, or
StarVLA implementation files are in scope for P0 EXECUTE. The only non-source writes
allowed during the smoke invocation are the local Teamwork metadata/output files listed
in the Worker Plan and Validation Plan below.

## Confirmed Claude Supervisor Decisions

Include these decisions verbatim in EXECUTE scope and worker prompts:

1. **`next-actor.json` write authority**: Direct writes to `.agent-docs/teamwork/next-actor.json` are authorized for Codex Manager **during P0 only** (wrapper not yet built). After P0, all `next-actor.json` updates must flow through the wrapper. The PLAN must document this transition and ensure the wrapper sets `next-actor.json` in future milestones.

2. **Wrapper prompt creation policy**: The wrapper must accept `--prompt-path` for Claude-provided prompts (the standard pattern). It may also auto-detect an existing prompt at the standard path `<teamwork-root>/prompts/<milestone>/<stage>.prompt.md`. Claude always provides or pre-approves the prompt; the wrapper never generates prompt content.

3. **Unit test scope for P0**: P0 acceptance requires:
   - `dispatch_codex_manager.py --dry-run` output shows all local Teamwork paths under `.agent-docs/teamwork/`.
   - One wrapper smoke invocation that verifies `.agent-docs/teamwork/codex-manager-session.json` is updated with session_id, dispatch_mode, last_prompt_path, last_report_path, updated_at, and last_exit_code.
   - Full pytest unit test suite is M0 scope, not P0.

4. **Sandbox for all stages**: Always use `-s workspace-write`. Stage write restrictions come from prompt instructions, not sandbox mode.

5. **`.last.md` promotion policy**: Wrapper only ever writes to `.last.md`. Claude promotes manually (or via prompt) after accepting the report. No automatic promotion.

6. **Codex model and reasoning**: All dispatch commands must explicitly set `model=gpt-5.5` and pass `-c model_reasoning_effort=xhigh`.

## In Scope Vs Out Of Scope

In scope for P0 EXECUTE:

- Create `scripts/teamwork/dispatch_codex_manager.py`.
- Create parent directory `scripts/teamwork/` only as needed for the wrapper file.
- Read existing local Teamwork state under `.agent-docs/teamwork/`.
- Update `.agent-docs/teamwork/codex-manager-session.json` during the approved smoke invocation.
- Append a dispatch event to `.agent-docs/teamwork/messages.jsonl` during the approved smoke invocation.
- Write Codex captured output only to `.agent-docs/teamwork/reports/<milestone>/<stage>.last.md`.
- During P0 only, allow direct `next-actor.json` writes if the wrapper implementation needs to set the local next actor. After P0, this path must be wrapper-mediated.

Out of scope for P0 EXECUTE:

- No changes to StarVLA source code, model paths, configs, datasets, Slurm configs, tests, or baseline paths.
- No generated `.planning/` artifacts.
- No pytest unit test suite; full unit test coverage is M0 scope.
- No `sbatch`, `srun`, Slurm submission, compute jobs, training, evaluation, inference, or dataset conversion.
- No git commits, pushes, PR creation, branch publication, or merge actions.
- No milestone selection, gate approval, feature completion, `passes: true`, or roadmap progress mutation.
- No reads or writes to global `~/.claude/skills/teammate/workspace/` for project-specific Teamwork state.

## Wrapper Interface Design

The EXECUTE worker must implement this CLI:

```text
dispatch_codex_manager.py [OPTIONS]

Required:
  --milestone MILESTONE_ID
      Example: P0
  --stage STAGE
      Allowed: DISCUSS, PLAN, EXECUTE, VERIFY, REVIEW

Optional:
  --repo-root PATH
      Default: auto-detect git root from the wrapper location or current working directory.
  --teamwork-root PATH
      Default: <repo-root>/.agent-docs/teamwork.
  --prompt-path PATH
      Explicit Claude-provided prompt file.
      Default: <teamwork-root>/prompts/<milestone>/<stage>.prompt.md.
  --report-path PATH
      Canonical report path for validation and metadata.
      Default: <teamwork-root>/reports/<milestone>/<stage>.md.
      The wrapper must not write this file automatically.
  --mode {bootstrap,resume,auto}
      Default: auto.
      auto uses <teamwork-root>/codex-manager-session.json:
      session_id present -> resume-by-id; session_id absent -> bootstrap.
  --session-id SESSION_ID
      Explicit Codex session id for resume.
  --use-last
      Explicit opt-in to `codex exec resume --last`, guarded by ambiguity checks.
  --dry-run
      Print resolved paths, routing table, and command preview; do not execute Codex.
  --sandbox {read-only,workspace-write,danger-full-access}
      Default: workspace-write.
      P0 commands must use workspace-write unless Claude changes policy.
  --model MODEL
      Default: gpt-5.5.
  --reasoning-effort EFFORT
      Default: xhigh.
```

Forbidden behavior to enforce:

- Do not add or accept `--approve-gate`, `--mark-complete`, `--set-passes`, `--push`, `--pr`, `--sbatch`, `--srun`, `--submit`, or any Slurm submission flags.
- If any forbidden flag appears in `sys.argv`, print a governance-specific error and exit non-zero before dispatch.
- Let `argparse` reject unknown options.
- Do not accept prompt paths under `~/.claude`.
- Do not write to paths outside `<teamwork-root>` except for the wrapper file itself during EXECUTE.
- Do not read prompts from global `~/.claude` paths.
- Do not promote `.last.md` to canonical `.md`.

Required output in `--dry-run`:

- Resolved `repo_root`.
- Resolved `teamwork_root`.
- Resolved prompt path.
- Canonical report path.
- Report capture path ending in `.last.md`.
- Local routing table for:
  - `workspace/task-board.md`
  - `claude-inbox.md`
  - `messages.jsonl`
  - `next-actor.json`
  - `codex-manager-session.json`
  - `prompts/<milestone>/<stage>.prompt.md`
  - `reports/<milestone>/<stage>.md`
  - `reports/<milestone>/<stage>.last.md`
- Exact command preview containing:
  - `codex exec` or `codex exec resume`
  - `-C <repo-root>`
  - `-s workspace-write`
  - `-m gpt-5.5`
  - `-c model_reasoning_effort=xhigh`
  - `-o <report-capture-path>`
  - stdin from `<prompt-path>`

## Wrapper Behavior Sequence

The EXECUTE worker must implement this sequence exactly:

1. Parse CLI arguments.
2. Reject explicit forbidden flags before dispatch:
   - `--approve-gate`
   - `--mark-complete`
   - `--set-passes`
   - `--push`
   - `--pr`
   - `--sbatch`
   - `--srun`
   - `--submit`
3. Validate `--stage` is one of `DISCUSS`, `PLAN`, `EXECUTE`, `VERIFY`, or `REVIEW`.
4. Resolve `repo_root`:
   - If `--repo-root` is provided, resolve it.
   - Otherwise, prefer `git rev-parse --show-toplevel` from the current working directory.
   - Fallback to `Path(__file__).resolve().parents[2]`.
5. Validate `repo_root`:
   - `repo_root/.git` must exist.
   - If not, print `repo-root must be a git repository root` and exit non-zero.
6. Resolve `teamwork_root`:
   - Default: `<repo-root>/.agent-docs/teamwork`.
   - It must exist.
   - It must be inside `repo_root`.
   - It must not be under `Path.home() / ".claude"`.
7. Resolve prompt path:
   - If `--prompt-path` is provided and exists, use it.
   - If `--prompt-path` is provided and missing, print a clear error and exit non-zero.
   - If no `--prompt-path`, use `<teamwork-root>/prompts/<milestone>/<stage>.prompt.md`.
   - If the default prompt is missing, print a clear error and exit non-zero.
   - Prompt path must be inside `teamwork_root`.
8. Resolve canonical report path:
   - If `--report-path` is provided, validate it is inside `teamwork_root`.
   - Otherwise use `<teamwork-root>/reports/<milestone>/<stage>.md`.
   - Do not write the canonical report path.
9. Resolve report capture path:
   - Always use `<teamwork-root>/reports/<milestone>/<stage>.last.md`.
   - Create the parent directory if needed.
10. Resolve local Teamwork routing paths:
    - `<teamwork-root>/workspace/task-board.md`
    - `<teamwork-root>/claude-inbox.md`
    - `<teamwork-root>/messages.jsonl`
    - `<teamwork-root>/next-actor.json`
    - `<teamwork-root>/codex-manager-session.json`
11. Determine dispatch mode:
    - `--mode bootstrap`: dispatch mode is `bootstrap`; command starts with `codex exec`.
    - `--mode resume --session-id X`: dispatch mode is `resume-by-id`; command uses `codex exec -C <repo-root> -s <sandbox> resume X`.
    - `--mode resume --use-last`: run the ambiguity check, then dispatch mode is `resume-last`; command uses `codex exec -C <repo-root> -s <sandbox> resume --last`.
    - `--mode auto`: read `codex-manager-session.json`; if `session_id` exists, use `resume-by-id`; otherwise use `bootstrap`.
12. Build the Codex command as an argument list, not a shell string:
    - Bootstrap:
      `["codex", "exec", "--json", "-C", repo_root, "-s", sandbox, "-m", model, "-c", f"model_reasoning_effort={effort}", "-o", capture_path, "-"]`
    - Resume by id:
      `["codex", "exec", "-C", repo_root, "-s", sandbox, "resume", session_id, "-m", model, "-c", f"model_reasoning_effort={effort}", "-o", capture_path, "-"]`
    - Resume last:
      `["codex", "exec", "-C", repo_root, "-s", sandbox, "resume", "--last", "-m", model, "-c", f"model_reasoning_effort={effort}", "-o", capture_path, "-"]`
    - Note: current Codex CLI accepts `-C` and `-s` as parent `codex exec` options before the `resume` subcommand. Do not place those flags after `resume`, because `codex exec resume --help` does not advertise them there.
13. Build a shell-safe command preview with `shlex.join(...) + " < " + shlex.quote(prompt_path)`.
14. If `--dry-run`:
    - Print the resolved path summary.
    - Print the local Teamwork routing table.
    - Print the exact command preview.
    - Exit `0`.
15. If not dry-run:
    - Read the prompt text from `prompt_path`.
    - Run the command with `subprocess.run(..., input=prompt_text, text=True, capture_output=True, check=False)`.
    - Preserve `stdout`, `stderr`, and `returncode` for metadata/event writing.
16. Attempt best-effort session id extraction from JSONL `stdout` only for bootstrap runs.
17. Update `<teamwork-root>/codex-manager-session.json`.
18. Append one JSONL dispatch event to `<teamwork-root>/messages.jsonl`.
19. During P0 only, if the wrapper sets `next-actor.json`, set it to Claude after Codex handoff; after P0, this wrapper is the required route for future `next-actor.json` updates.
20. Exit with the Codex return code.

## `--use-last` Ambiguity Check

When `--use-last` is requested, the wrapper must:

1. Read `<teamwork-root>/codex-manager-session.json`.
2. Confirm `session_id` is null. If `session_id` exists, print `session_id exists; use --session-id instead of --use-last` and exit non-zero.
3. Run `codex exec resume --help` with `subprocess.run(..., capture_output=True)` and confirm the output contains `--last`.
4. Determine the last bootstrap timestamp:
   - Prefer `last_bootstrap_at` if present in the session file.
   - Otherwise use `updated_at` when `dispatch_mode` is `bootstrap`.
   - If no usable timestamp exists, fail closed.
5. Check for ambiguity:
   - Look only inside repository-local session metadata if such metadata exists under `<repo-root>/.codex`.
   - If `<repo-root>/.codex` does not exist, record that no repo-local metadata was available and treat the check as inconclusive.
   - If any repo-local session metadata file is newer than the last bootstrap timestamp, exit non-zero.
   - If the check is inconclusive, exit non-zero unless Claude explicitly supplied `--use-last` and the session file records a prior no-ambiguity reason for this P0 bootstrap.
6. Record the result in `codex-manager-session.json` under:
   - `use_last_fallback: true`
   - `use_last_fallback_reason`
   - `use_last_checked_at`
7. If any ambiguity check fails, do not run Codex.

## Session ID Extraction

The wrapper must include:

```text
try_extract_session_id(jsonl_events: str) -> tuple[str | None, str]
```

Expected behavior:

- Accept JSONL text from `codex exec --json` stdout.
- Parse each non-empty line as JSON.
- Look for stable id candidates in conservative locations:
  - top-level `session_id`
  - top-level `conversation_id`
  - top-level `thread_id`
  - nested `session_id`, `conversation_id`, or `thread_id` under `payload`
  - nested `id` under `payload` only if the event type clearly names session creation, conversation creation, or thread creation.
- Return `(id_value, "jsonl:<field>")` for a stable match.
- Ignore malformed JSON lines.
- Return `(None, "not_found")` if no stable id exists.
- Never crash dispatch if extraction fails.

Metadata behavior:

- If extraction succeeds, write `session_id` and `session_id_extraction_method`.
- If extraction fails, write:
  - `session_id: null`
  - `session_id_extraction_method: "not_found"`
- If the Codex command fails before any parseable events, write:
  - `session_id: null`
  - `session_id_extraction_method: "command_failed_or_no_events"`

## Worker Plan

Claude approves exactly one write-capable worker for P0 EXECUTE.

Worker type: `coding_integration_engineer`

Count: `1`

Mode: serial

Scope:

- Create `scripts/teamwork/dispatch_codex_manager.py` only.
- Run the approved dry-run and smoke validation commands.
- Update `.agent-docs/teamwork/codex-manager-session.json` only through the smoke invocation.

Core writable paths:

- `scripts/teamwork/dispatch_codex_manager.py` (create)
- `.agent-docs/teamwork/codex-manager-session.json` (update for smoke test)

Smoke side-effect paths authorized by validation:

- `.agent-docs/teamwork/messages.jsonl` (append dispatch event for smoke test)
- `.agent-docs/teamwork/reports/P0/PLAN.last.md` (wrapper output capture during smoke test)
- `.agent-docs/teamwork/next-actor.json` (P0-only direct write if the wrapper sets next actor during smoke)

Read-only paths:

- All StarVLA source and baseline paths.
- `AGENTS.md`
- `boundaries.txt`
- `CLAUDE.md`
- `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- `.agent-docs/teamwork/claude_supervisor_usage.md`
- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/teamwork/reports/P0/DISCUSS.md`
- `.agent-docs/teamwork/prompts/P0/PLAN.prompt.md`
- `scripts/slurm/discover_slurm_environment.py`
- `scripts/maintenance/generate_cleanup_proposal.py`
- `~/.claude/skills/teammate/scripts/sync_task_board.py`

Stop condition:

- `scripts/teamwork/dispatch_codex_manager.py` exists.
- Dry-run validation passes.
- One smoke invocation updates `codex-manager-session.json`.
- One smoke invocation appends a dispatch event to `messages.jsonl`.
- Worker reports changed files, commands run, validation output, residual risks, rollback notes, and affected paths to Codex Manager.

Worker must not:

- Modify any file outside the core writable paths and validation side-effect paths above.
- Modify source code, tests, StarVLA configs, datasets, Slurm configs, baseline paths, `.agent-docs/feature_list.json`, `.agent-docs/progress.txt`, or `.agent-docs/review.txt`.
- Run `sbatch`, `srun`, training, evaluation, inference, dataset conversion, git commit, git push, PR creation, or remote publication.
- Launch additional workers.
- Set `passes: true` or mark P0 complete.

No parallel workers. No additional EXECUTE workers.

VERIFY note:

- V5 below names a `code_reviewer` read-only review. That is a VERIFY-stage review check, not an additional P0 EXECUTE worker. If Claude wants strict one-worker-total for all P0 remaining stages, Codex Manager can perform the read-only source review inline and record that V5 was manager-reviewed instead of worker-reviewed.

## Implementation Tasks For EXECUTE Worker

### Task 1: Create Wrapper File And CLI Skeleton

Files:

- Create: `scripts/teamwork/dispatch_codex_manager.py`

Steps:

- Create `scripts/teamwork/` if missing.
- Add a Python shebang.
- Add a Chinese module docstring describing purpose, inputs, outputs, and governance limits.
- Implement `argparse` arguments exactly as defined above.
- Implement explicit forbidden-flag detection before normal parse.
- Implement `main() -> int` and `if __name__ == "__main__": raise SystemExit(main())`.

Expected local check:

```bash
python scripts/teamwork/dispatch_codex_manager.py --help
```

Expected result:

- Help text lists required and optional flags.
- Unknown or forbidden flags exit non-zero.

### Task 2: Implement Path Resolution And Boundary Guards

Files:

- Modify: `scripts/teamwork/dispatch_codex_manager.py`

Steps:

- Add helper functions:
  - `resolve_repo_root(raw: str | None) -> Path`
  - `ensure_inside(path: Path, parent: Path, label: str) -> Path`
  - `resolve_teamwork_root(repo_root: Path, raw: str | None) -> Path`
  - `resolve_prompt_path(teamwork_root: Path, milestone: str, stage: str, raw: str | None) -> Path`
  - `resolve_report_paths(teamwork_root: Path, milestone: str, stage: str, raw: str | None) -> tuple[Path, Path]`
- Use `Path.resolve()` before boundary checks.
- Reject prompt paths under `Path.home() / ".claude"`.
- Create only the report capture parent directory, not canonical report content.

Expected local check:

```bash
python scripts/teamwork/dispatch_codex_manager.py --milestone P0 --stage PLAN --dry-run
```

Expected result:

- Dry-run succeeds only if `.agent-docs/teamwork/prompts/P0/PLAN.prompt.md` exists.
- Dry-run prints only project-local routing paths.

### Task 3: Implement Dispatch Mode And Command Preview

Files:

- Modify: `scripts/teamwork/dispatch_codex_manager.py`

Steps:

- Add helper functions:
  - `read_session_file(path: Path) -> dict`
  - `determine_dispatch_mode(args, session_data: dict) -> tuple[str, str | None]`
  - `build_codex_command(...) -> list[str]`
  - `format_command_preview(command: list[str], prompt_path: Path) -> str`
- Use `shlex.join` for command preview.
- Include `--json` for bootstrap commands so session extraction has JSONL events to parse.
- Include `-m gpt-5.5` and `-c model_reasoning_effort=xhigh`.
- Use `-s workspace-write` by default and in all P0 validation commands.

Expected local check:

```bash
python scripts/teamwork/dispatch_codex_manager.py --milestone P0 --stage PLAN --dry-run
```

Expected result:

- Command preview includes `codex exec`, `--json` for bootstrap, `-C`, `-s workspace-write`, `-m gpt-5.5`, `-c model_reasoning_effort=xhigh`, `-o .agent-docs/teamwork/reports/P0/PLAN.last.md`, and stdin from the prompt path.

### Task 4: Implement `--use-last` Ambiguity Check

Files:

- Modify: `scripts/teamwork/dispatch_codex_manager.py`

Steps:

- Add `check_use_last_allowed(teamwork_root: Path, repo_root: Path, session_data: dict) -> tuple[bool, str]`.
- Confirm `session_id` is null.
- Confirm `codex exec resume --help` advertises `--last`.
- Confirm no newer repo-local `.codex` session metadata exists after bootstrap timestamp, or fail closed.
- Store a clear reason for success or failure.

Expected local check:

```bash
python scripts/teamwork/dispatch_codex_manager.py --milestone P0 --stage PLAN --mode resume --use-last --dry-run
```

Expected result:

- Succeeds only when ambiguity checks pass.
- Otherwise exits non-zero before printing an executable command.

### Task 5: Implement Execution, Metadata Write, And Message Event

Files:

- Modify: `scripts/teamwork/dispatch_codex_manager.py`

Steps:

- Add `run_codex(command: list[str], prompt_path: Path) -> subprocess.CompletedProcess[str]`.
- Add `try_extract_session_id(jsonl_events: str) -> tuple[str | None, str]`.
- Add `write_session_metadata(...) -> None`.
- Add `append_dispatch_event(messages_path: Path, payload: dict) -> None`.
- Use atomic write for `codex-manager-session.json`: write temp file in the same directory, then `os.replace`.
- Append one JSON object per line to `messages.jsonl`.
- Record:
  - `session_id`
  - `session_id_extraction_method`
  - `use_last_fallback`
  - `use_last_fallback_reason`
  - `dispatch_mode`
  - `repo_root`
  - `active_milestone`
  - `current_stage`
  - `last_prompt_path`
  - `last_report_path`
  - `sandbox`
  - `model`
  - `reasoning_effort`
  - `codex_command_preview`
  - `updated_at`
  - `last_exit_code`
- Event payload should include:
  - `actor: "codex-manager-wrapper"`
  - `event_type: "dispatch"`
  - `milestone`
  - `stage`
  - `dispatch_mode`
  - `prompt_path`
  - `report_capture_path`
  - `exit_code`
  - `timestamp`

Expected local check:

```bash
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 \
  --stage PLAN \
  --prompt-path .agent-docs/teamwork/prompts/P0/PLAN.prompt.md \
  --mode auto
```

Expected result:

- Command exits with Codex exit code.
- `codex-manager-session.json` receives the required fields.
- `messages.jsonl` receives one new dispatch event.
- `.agent-docs/teamwork/reports/P0/PLAN.last.md` exists and is non-empty if Codex produced output.

## Validation Plan

VERIFY must pass these checks before P0 EXECUTE is accepted.

### V1. File Existence

Command:

```bash
test -f scripts/teamwork/dispatch_codex_manager.py
```

Expected result:

- Exit code `0`.

### V2. Dry-Run Output

Command:

```bash
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 \
  --stage PLAN \
  --dry-run
```

Output must show:

- Prompt path under `.agent-docs/teamwork/prompts/P0/`.
- Report path under `.agent-docs/teamwork/reports/P0/`.
- Report capture path under `.agent-docs/teamwork/reports/P0/` and ending in `.last.md`.
- Codex command with:
  - `-C /home/cz-jzb/workspace/vla-flywheel`
  - `-s workspace-write`
  - `-m gpt-5.5`
  - `-c model_reasoning_effort=xhigh`
- No global `~/.claude/skills/teammate` paths in any routing field.

### V3. Smoke Invocation

Command:

```bash
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 \
  --stage PLAN \
  --prompt-path .agent-docs/teamwork/prompts/P0/PLAN.prompt.md \
  --mode auto
```

After completion:

- `.agent-docs/teamwork/codex-manager-session.json` is updated with:
  - `dispatch_mode`
  - `last_prompt_path`
  - `last_report_path`
  - `updated_at`
  - `last_exit_code`
  - `model`
  - `reasoning_effort`
  - `session_id` or `session_id: null`
- `.agent-docs/teamwork/messages.jsonl` has a new dispatch event.
- `.agent-docs/teamwork/reports/P0/PLAN.last.md` has output if Codex completed far enough to write final output.
- If `session_id` extraction fails, the metadata records `session_id_extraction_method: "not_found"` or `command_failed_or_no_events`.

### V4. Path Boundary

Command:

```bash
git status --short
```

Expected result:

- New or changed paths from this P0 EXECUTE are limited to:
  - `scripts/teamwork/dispatch_codex_manager.py`
  - `.agent-docs/teamwork/codex-manager-session.json`
  - `.agent-docs/teamwork/messages.jsonl`
  - `.agent-docs/teamwork/reports/P0/PLAN.last.md`
  - `.agent-docs/teamwork/next-actor.json` only if wrapper sets it during P0 smoke
- Pre-existing unrelated dirty files must be called out separately and not reverted.

### V5. Script Review

Read-only review target:

```text
scripts/teamwork/dispatch_codex_manager.py
```

Review method:

- Preferred VERIFY stage: Claude approves one read-only `code_reviewer` worker.
- If Claude wants no further workers in P0, Codex Manager performs the read-only review inline and records it as a Manager review.

Review must confirm:

- No Slurm job submission.
- No `git push`, PR creation, branch publication, merge, or commit calls.
- No milestone or gate selection logic.
- No writes to global `.claude` paths.
- No prompt reads from global `.claude` paths.
- No canonical `.md` report promotion.
- Chinese docstrings and comments in new code.
- Time complexity is trivial relative to file sizes: linear in session metadata size, prompt size, and JSONL output size.
- No baseline contamination or StarVLA source modification.

## Rollback Plan

Rollback action:

```bash
rm scripts/teamwork/dispatch_codex_manager.py
```

If `scripts/teamwork/` becomes empty after rollback, Claude may approve removing that empty directory during cleanup, but deletion is not required for functional rollback.

Recovery:

- Existing manual Codex dispatch remains operative:

```bash
codex exec \
  -C /home/cz-jzb/workspace/vla-flywheel \
  -s workspace-write \
  -m gpt-5.5 \
  -c model_reasoning_effort=xhigh \
  -o .agent-docs/teamwork/reports/<milestone-id>/<stage>.last.md \
  - < .agent-docs/teamwork/prompts/<milestone-id>/<stage>.prompt.md
```

Risk:

- Low. The wrapper is additive. Removing it restores pre-P0 manual dispatch behavior.

Metadata recovery:

- If smoke metadata becomes misleading, Claude can dispatch a follow-up governance task to replace `.agent-docs/teamwork/codex-manager-session.json` with known-good routing metadata. Do not delete or rewrite Teamwork history without Claude approval.

## Risk List

- Session id extraction may fail across CLI versions. Mitigation: record `session_id: null`, record extraction method, and use `--last` only under explicit opt-in and ambiguity checks.
- `--use-last` can attach to the wrong session if another Codex session is created in the same repository. Mitigation: fail closed when repo-local metadata is inconclusive or newer than bootstrap.
- Wrapper scope creep could bypass Claude gates. Mitigation: reject forbidden flags and keep milestone, stage, gate, Slurm, git, PR, and completion decisions outside the wrapper.
- Global teammate scripts are useful references but can write global state if misrouted. Mitigation: wrapper resolves and prints all local paths under `.agent-docs/teamwork/` and rejects global prompt/state paths.
- P0 smoke invocation can create confusing `.last.md` output. Mitigation: wrapper writes `.last.md` only; Claude handles canonical promotion manually.
- Stage write restrictions depend on prompt content because sandbox remains `workspace-write`. Mitigation: wrapper records stage, prompt path, and command; Claude reviews the prompt and output.
- Chinese docstrings and comments may conflict with line length limits. Mitigation: use concise Google-style Chinese docstrings and keep lines near the 100-character local limit.
- Existing dirty worktree entries may predate P0. Mitigation: VERIFY separates pre-existing changes from P0 wrapper changes and does not revert unrelated files.

## Recommended Next Stage

Recommended gate decision: `approve_execute`, pending Claude review of this PLAN.

EXECUTE should be dispatched with exactly the worker plan above:

- worker type: `coding_integration_engineer`;
- count: 1;
- mode: serial;
- writable scope limited to the listed P0 wrapper and smoke metadata paths;
- stop after wrapper creation, dry-run pass, smoke invocation pass, and worker report.

Do not start EXECUTE until Claude explicitly approves this plan.

## Self-Review

Spec coverage:

- Wrapper Interface Design: covered.
- Wrapper Behavior Sequence: covered.
- `--use-last` Ambiguity Check: covered.
- Session ID Extraction: covered.
- Worker Plan: covered with all required fields.
- Validation Plan V1-V5: covered.
- Rollback Plan: covered.
- Risk List: covered.
- In-scope vs out-of-scope clarification: covered.
- Recommended next stage: EXECUTE pending Claude approval.

Placeholder scan:

- No `TBD`, `TODO`, or implementation placeholders remain.

Files affected by PLAN:

- `.agent-docs/teamwork/reports/P0/PLAN.md` (written)
- `scripts/teamwork/dispatch_codex_manager.py` already exists as an interrupted prior EXECUTE artifact; this PLAN update did not modify it.

===HANDOFF===
Completed:
- Read required governance, Teamwork, DISCUSS, Python CLI reference, and task-board routing files.
- Incorporated Claude Supervisor answers from `.agent-docs/teamwork/roadmap_progress.md`.
- Drafted the P0 EXECUTE implementation plan for one approved write-capable worker.
- Defined wrapper interface, behavior sequence, ambiguity check, session extraction, validation, rollback, risks, and scope boundaries.
- Wrote `.agent-docs/teamwork/reports/P0/PLAN.md`.

Pending:
- Claude gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
- If approved, EXECUTE must create only `scripts/teamwork/dispatch_codex_manager.py` plus approved smoke metadata/output.
- VERIFY must run V1-V5 before P0 can proceed to REVIEW.

Decisions:
- EXECUTE scope is exactly one wrapper artifact: `scripts/teamwork/dispatch_codex_manager.py`.
- Wrapper accepts Claude-provided/pre-approved prompts only; it never generates prompt content.
- Wrapper writes only `.last.md`; canonical report promotion stays manual or prompt-driven after Claude review.
- All dispatch commands use `-s workspace-write`, `-m gpt-5.5`, and `-c model_reasoning_effort=xhigh`.
- `next-actor.json` direct writes are P0-only; after P0, future updates must flow through the wrapper.

Files Affected:
- `.agent-docs/teamwork/reports/P0/PLAN.md` (written)
- `scripts/teamwork/dispatch_codex_manager.py` (interrupted prior EXECUTE artifact; not modified by this PLAN stage)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
