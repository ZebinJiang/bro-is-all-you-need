---
name: thread-team
description: "Use when the user explicitly asks for a thread team, parallel Codex threads, worker threads, leader/worker collaboration, or multi-thread branch work; or when a task appears large, parallelizable, and branch-isolatable enough that thread-team mode should be proposed. First evaluates whether thread-team execution has higher net benefit than direct single-thread execution, then either recommends direct execution, proposes thread-team mode for user confirmation, or runs a Codex-app-specific six-phase leader workflow when justified and authorized."
---

# Thread Team

Use this skill to evaluate and, when warranted, run Codex like a small engineering team. The current thread is the **leader thread**. New Codex threads are **worker threads**. Workers implement scoped tasks on their own branches in their own working directories; the leader plans, delegates, coordinates decisions, polls progress, merges branches, and performs the final review.

Do not substitute temporary subagents for real worker threads when Codex thread tools are available. If thread creation or cross-thread messaging tools are missing, say so and stop before pretending to run the workflow.

## Preflight Viability Assessment

Once this skill is triggered, do not assume worker-thread execution is automatically warranted. Before creating workers, the leader must evaluate whether thread-team execution is likely to beat direct single-thread execution for this specific task.

There are two common trigger paths:

- If the user explicitly requested thread-team mode, perform this assessment before creating workers. If direct execution looks better, briefly recommend direct execution and ask whether the user still wants a thread team.
- If the user did not request thread-team mode but the task looks large, parallelizable, and branch-isolatable, use this assessment only to decide whether to propose thread-team mode. Do not create workers without user confirmation.

Use thread team when the expected parallelism benefit clearly exceeds coordination overhead:

- Multiple independent work areas can proceed in parallel with low conflict risk.
- Tasks have clear ownership boundaries, branch boundaries, and acceptance criteria.
- Worker outputs can be reviewed and merged serially without reconstructing too much shared context.
- The likely time saved by parallel work is greater than worker setup, polling, report collection, merge, and final review cost.

Prefer direct single-thread execution, or ask the user to confirm before using thread team, when:

- The task would only create one or two worker threads and the subtasks are small.
- The work is a tight core-code refactor where one continuous context is more valuable than parallel throughput.
- Subtasks share the same files, contracts, or mental model, making merge/review overhead likely to erase parallel gains.
- The main value of worker branches would be process discipline rather than actual speed.
- The task is vague and cannot be split responsibly after local analysis.

If the assessment says direct execution is likely more efficient, report that recommendation briefly and ask whether the user still wants thread-team execution. If the user insists, continue with the six-phase workflow. If the user did not ask for thread-team mode, a positive assessment is only a recommendation to propose the mode, not authorization to start it.

Before any worker is created, state plainly that worker threads will use the current Codex thread tool schema and the user's configured default model unless the user explicitly requests a specific worker model. If the user explicitly requests worker model or reasoning settings, use those settings exactly when the thread tool supports them; otherwise omit model overrides and let the Codex app default apply.

## Codex Thread Tools

This is a Codex-thread skill. Prefer real Codex thread tools, not temporary subagents.

- Use `create_thread` to create worker threads. Follow the active Codex tool schema for worker runtime settings: omit `model` unless the user explicitly requested a specific worker model, and only set `thinking` when the user requested a reasoning level or the tool schema allows the leader to choose it for this workflow.
- Use `send_message_to_thread` to initialize workers, dispatch tasks, send leader decisions, ask workers for status, and request missing reports.
- Use `read_thread` to inspect or poll worker progress.
- Use `list_threads` to recover worker thread IDs when leader state is missing or stale.
- Use heartbeat automations for delayed polling when the leader should check back later instead of staying active in a long wait loop. Search for the automation tool before creating, updating, or deleting heartbeat automations. Every heartbeat automation this workflow creates must be deleted before the workflow ends — a leaked recurring heartbeat outlives the task and keeps waking the thread forever.
- Use `set_thread_title` to name worker threads when available.
- Use `set_thread_archived({ threadId, archived: true })` to archive a worker thread only when the workflow explicitly calls for retiring that worker, such as replacing a worker that never starts after dispatch.
- Use `fork_thread` only when the worker genuinely needs current leader history, or when a worktree fork from the leader context is the right starting point.
- Do not use `spawn_agent` as a substitute for worker threads when Codex thread tools are available.

If `create_thread`, `send_message_to_thread`, or `read_thread` are unavailable, stop and tell the user which required thread capability is missing. Do not pretend to run a thread team with subagents.

## Team Model

This is the collaboration model for the whole team. When initializing workers, send it as explicit rules, not a vague phrase — the registration and dispatch templates carry a worker-facing copy of these rules; use them verbatim rather than paraphrasing.

- The leader thread is the team lead. It owns planning, task decomposition, worker creation, per-worker task design, task dispatch, progress polling, team-wide decisions, merge orchestration, serial branch integration, final review, and final repair.
- Each worker thread is a team member. It owns exactly one task boundary, one worker branch, and one isolated working directory.
- Worker threads may message peer worker threads for collaboration, questions, requests, interface details, dependency clarification, review input, or coordination.
- Worker threads must message the leader for overall decisions, cross-responsibility issues, blockers they cannot solve, changes to shared contracts, work outside their assigned task, or when they cannot contact a needed peer — and when they finish.
- Worker threads must not merge into the leader branch unless the leader explicitly authorizes that exception.
- After receiving a formal dispatch, each worker must call `update_plan` with exactly these three worker phases: `Execute assigned task`, `Review and verify changes`, and `Commit changes and report completion to leader`.
- A worker is not done until it self-reviews, fixes its own findings, verifies relevant behavior, commits on its branch, and sends a structured report to the leader thread.
- The leader must not call the task complete after workers finish. Completion requires serial integration and a final whole-task review.

## Workspace Isolation

A branch alone does not isolate workers. Two threads sharing one checkout will overwrite each other's working tree, corrupt every diff, and silently mix changes across branches — this is the most common way a thread team fails in practice. Before any dispatch, the leader must guarantee each worker an exclusive working directory:

- For repo-scoped workers, create the isolation at thread-creation time: call `create_thread` with a project worktree target, for example `create_thread({ prompt, target: { type: "project", projectId: <project-id>, environment: { type: "worktree", startingState: { type: "branch", branchName: <integration-branch> } } } })`, so the worker thread starts inside its own worktree. Isolation decided at creation is far more reliable than telling an already-created worker to relocate. Record each worker's worktree path in leader state when the tool returns it; otherwise require the worker to report its actual `pwd`, branch, and HEAD during startup, then record the confirmed path.
- Only if `create_thread` cannot provide a worktree environment, fall back to manual isolation: create one git worktree per worker (`git worktree add <path> -b <worker-branch> <base-commit>`), then create the worker thread with a project target whose `projectId` or workspace root is that manual worktree path and whose environment is local. Tell the worker its exact working directory and base commit in the dispatch, and during the startup gate confirm from the worker's actual command activity that it is executing inside that directory before letting it proceed.
- Never let two workers share a working directory. If exclusive working directories cannot be arranged, do not run thread-team mode; fall back to direct single-thread execution and tell the user why.
- After integration, clean up worker worktrees that the leader created (`git worktree remove <path>`).

## Branch Naming

Use deterministic, readable worker branch names:

```text
worker-<short-task>-<worker-role>
```

Keep `<short-task>` and `<worker-role>` lowercase and hyphen-separated, for example `worker-auth-ui-frontend` or `worker-billing-api-backend`. If a replacement worker is needed, append a replacement suffix such as `-r2`.

## Leader State Persistence

Leader context can be compacted or interrupted mid-run, and state that lives only in the conversation is lost with it. Keep the leader state in a file and treat the file as the source of truth:

- When phase 1 completes, write the leader state record (`references/leader-state-template.md`) to `.thread-team/state.md` under the repo root, and keep it out of commits: add `.thread-team/` to the exclude file located by `git rev-parse --git-path info/exclude` (do not assume `.git/info/exclude` exists as a literal path — in a linked worktree `.git` is a file, not a directory). Never commit the state file.
- Update the file immediately after every state change: worker created, worktree assigned, dispatch sent, decision made, worker replaced, report received, branch merged, heartbeat scheduled or deleted.
- After compaction, interruption, or any suspicion of stale context, reread the state file before acting. Use `list_threads` only to fill gaps the file cannot answer.

## Worker Model and Dispatch Clarity

Worker threads may have weaker reasoning, less context, and less continuity than the leader thread. The leader must compensate with precise task design instead of expecting workers to infer intent from vague instructions.

- Worker runtime settings are creation settings controlled by the active Codex tool schema, not worker instructions. Record the effective worker model and thinking level in leader state when they are known; otherwise record that the Codex app defaults were used.
- Treat every worker dispatch as if the worker has weaker task understanding than the leader.
- Do not send vague goals such as "refactor this area" or "make this cleaner" without concrete boundaries.
- Each dispatch must spell out the exact task scope, working directory and base commit, files/packages likely involved, files/packages not owned by the worker, expected behavior, acceptance criteria, verification commands, commit requirements, and report format.
- For fragile behavior, include the specific invariants to preserve: event order, message text, public API, transcript format, permission behavior, concurrency behavior, or other user-visible contracts.
- If the leader has important context from prior analysis, worker reports, local diffs, failed attempts, or user decisions, include that context directly in the dispatch instead of assuming the worker can recover it.

## Mandatory Six-Phase Leader Workflow

Run exactly these six phases in order. Do not replace this with another workflow or split it into a different set of main phases.

Before creating workers, the leader must call `update_plan` with exactly these six phase names. Keep at most one phase `in_progress` at a time. Do not mark a phase `completed` until its detailed description below is satisfied.

When entering any phase, the leader must reread that phase's detailed description in this skill before acting. Do not rely only on the short `update_plan` phase name.

1. **Deep task analysis and parallel split**
   - The leader first reads the code, understands the user's objective, identifies task and code boundaries, and decides which parts can safely run in parallel.
   - The leader performs the Preflight Viability Assessment above and records whether thread-team execution has higher expected net benefit than direct execution.
   - If thread-team execution is not clearly beneficial, the leader reports the direct-execution recommendation and asks whether the user still wants a thread team before creating workers.
   - Before creating workers, state that worker threads will use the active Codex thread tool schema and the user's configured default model unless the user explicitly requests a specific worker model. Record the effective worker runtime settings in the initial leader state file when known.
   - The leader splits the current task into multiple executable worker tasks only after that deep analysis.
   - Calibration example — good split: one worker builds a new API endpoint, one builds the frontend page that consumes it, one writes the migration and seed data; the files barely overlap and the one shared contract (the API schema) is fixed by the leader up front. Bad split: three workers refactoring the same core module; they share files and a mental model, so merge and review cost erases the parallel gain.
   - On completing this phase, write the initial leader state file as described in Leader State Persistence.

2. **Worker thread initialization**
   - The leader creates independent worker threads, with one new branch per worker named according to `worker-<short-task>-<worker-role>`.
   - The leader arranges an exclusive working directory for every worker as described in Workspace Isolation, and records branch, base commit, and working directory in the leader state file.
   - This phase is only team-member initialization. The leader explains each worker's identity, the leader thread ID, and the full Team Model above using the registration template. Do not summarize the collaboration rules as a vague phrase; send the concrete rules to the worker.

3. **Per-worker deep task design and dispatch**
   - After the leader has every worker thread ID, the leader must not simply hand out tasks.
   - For each worker, the leader separately performs deep task analysis and designs a detailed execution plan: execution steps, task boundary, expected result, dependencies, collaboration targets, verification method, and special cautions.
   - Because worker threads may reason less strongly than the leader, the leader must make the dispatch self-contained and explicit. Include all important context, constraints, non-goals, invariants, and acceptance checks needed for the worker to execute without guessing.
   - The leader sends that worker-specific detailed execution plan, together with the full worker roster, all worker thread IDs, and the worker's working directory and base commit, to the worker thread assigned to that task.
   - Finish the design and dispatch for one worker before moving to the next worker.

4. **Progress polling and collaboration decisions**
   - After dispatching all workers, the leader first runs a startup gate before switching to delayed heartbeat polling.
   - Startup gate: immediately poll every worker with `read_thread` until each worker has clearly started responding to its formal dispatch. "Started" means the worker has a post-dispatch assistant turn, acknowledgement with intent, tool activity, command activity, implementation work, a status update, a blocker report, or a completion report for the assigned task.
   - During startup, confirm each worker's actual working directory, branch, and HEAD from either worker report text or observable command activity before treating its workspace isolation as verified. If the tool did not return a worktree path at creation time, this confirmation is mandatory before the worker proceeds beyond initial setup.
   - During the startup gate, distinguish a worker that is merely slow from a worker stuck before response. If at least one worker has started but another worker remains stuck with no post-dispatch response for a reasonable startup window, retire only the stuck worker: archive it with `set_thread_archived({ threadId, archived: true })`, create a replacement worker thread, give it a fresh worker identity/branch/working directory, and resend the same self-contained dispatch for the unstarted task.
   - After replacing a worker, update the leader state file with the retired worker, replacement worker, transferred responsibility, and replacement reason. Broadcast the replacement to every other active worker thread that is still executing normally: tell them the old worker thread ID is retired/invalid, give them the replacement worker thread ID and role, and tell them to use the replacement worker for any future peer coordination about that responsibility.
   - Do not use the replacement policy for workers that have already started and are doing normal long-running work, running tests, reporting blockers, asking questions, or otherwise making observable progress. Handle those through ordinary polling and leader decisions.
   - Only after every active worker has started should the leader move to heartbeat polling. Use a two-minute heartbeat for the current leader thread when delayed polling is available, so the leader wakes, performs one polling pass, and then stops again if workers are still running.
   - On each heartbeat wake, the leader polls active workers once with `read_thread`, handles new blocker reports or collaboration decisions, records decisions in the leader state file, and syncs decisions to affected workers.
   - Mid-task stall policy: if a started worker shows no new activity across roughly three consecutive polling passes and is not visibly inside a long-running command or waiting on a peer, send it a direct status request. If it stays silent through the next pass as well, treat it as stuck: decide whether to re-dispatch the remaining work to it, replace it using the same archive/replace/broadcast procedure as the startup gate, or pull the remaining work into the leader. Record the decision in the state file.
   - Replacement baseline rule: a mid-task replacement must not inherit "remaining work" by default, because the stuck worker may leave uncommitted changes, half-finished commits, or partially completed scope. Unless the stuck worker left committed work that the leader has inspected and verified, the replacement re-executes the full task from the integration branch/base commit in a fresh worktree. Only when a committed, verified intermediate commit exists may the replacement be dispatched to continue from that commit, with the dispatch stating exactly what is already done and what remains.
   - If active workers are still executing normally and not all reports are collected, schedule or keep the next two-minute heartbeat and stop the current leader turn instead of staying in a manual polling loop.
   - If every worker has proactively sent its completion report, or a polling pass shows every active worker has completed and reported, finish this phase and enter phase 5.
   - Worker threads may message each other for collaboration. If a worker needs to ask, request, or coordinate with another worker, it may send a message to that peer worker thread.
   - Workers message the leader for overall decisions, cross-responsibility issues, problems they cannot solve, unresolved blockers, or work outside all worker task scopes.
   - The leader makes the decision, records it, and syncs the decision to affected workers.

5. **Report collection and merge orchestration**
   - Workers finish by self-reviewing their own changes, fixing their own findings, verifying, committing on their worker branch, and reporting the task result to the leader.
   - Once all worker reports are collected, pause or delete the report-waiting heartbeat before starting merges. This is not yet the final deletion: if this phase later sends rework back to a worker, that worker is running asynchronously again, so re-enter phase-4-style polling for it — schedule a new heartbeat, collect its updated report — and only then resume the merge sequence. Delete heartbeats for good only when no worker has asynchronous work outstanding.
   - If the workflow is cancelled, blocked, switched to direct single-thread execution, or cannot continue to merge/review, delete every heartbeat automation created by this workflow before yielding unless the user explicitly asks to keep it.
   - After collecting all worker reports, the leader replans merge order based on dependencies, risk, conflicts, and shared contracts.
   - The leader merges worker branches into the leader branch one at a time according to that merge orchestration plan, and runs the relevant build/tests after each individual merge before merging the next branch. Per-merge verification is what makes a regression attributable to one worker's changes; skipping it forfeits the value of serial integration.
   - Conflict and rework policy: the leader resolves small mechanical conflicts directly. If a conflict or failed verification reveals overlapping design, a broken shared contract, or work that needs real rework, send it back to the owning worker with a fresh scoped dispatch describing the concrete findings, rather than silently rewriting that worker's code. If the worker is already archived or the fix is small, the leader fixes it directly and records that in the state file.
   - Record each merge result and its verification outcome in the leader state file.

6. **Final leader review and repair**
   - After all worker branches are merged, the leader reviews all changes for the whole task.
   - The leader checks whether any worker wrote wrong code or bug code, and checks for integration issues across worker changes.
   - If there is a problem, the leader fixes it directly, verifies again, and reviews the fix.
   - Before ending, confirm cleanup: every heartbeat automation created by this workflow is deleted, and worker worktrees created by the leader are removed.
   - If the workflow ends early for any reason — success, cancellation, blockage, user redirection, or fallback to direct execution — delete every heartbeat automation created by this workflow before the final response unless the user explicitly asks to keep it.
   - If there is no problem, the task may end only after this final leader review passes.

## Operating Rules

- Prefer 2-3 workers only when the preflight assessment shows enough independent work to justify them. Coordination cost grows with each worker; a two-worker split is not automatically worth thread-team mode; use it only when the parallelism benefit is concrete.
- Do not parallelize vague tasks before the leader has enough local context to split them responsibly.
- Do not let workers write to the leader's integration branch unless the user explicitly asks for that exception.
- Do not let workers decide team-wide architecture, public API, data model, or cross-worker contract changes alone.
- Maintain the leader state file as described in Leader State Persistence: roster, branches, working directories, responsibilities, dependencies, decisions, worker status, report status, merge order, and final review status.
- When context is compacted, interrupted, or stale, recover by rereading the leader state file before continuing.
- If the user asks for status, load `references/status-template.md` and report the team roster, current worker states, blockers, merge progress, heartbeat state, and next leader action.

## Reference Templates

Load only the template needed for the current phase:

- Register a worker: `references/worker-registration-template.md`
- Dispatch implementation work: `references/worker-dispatch-template.md`
- Worker completion report: `references/worker-report-template.md`
- Leader state tracking: `references/leader-state-template.md`
- Status report: `references/status-template.md`
- Final leader report: `references/final-report-template.md`
