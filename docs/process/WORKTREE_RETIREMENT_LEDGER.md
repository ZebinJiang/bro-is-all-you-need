# Worktree Retirement Ledger

This ledger records the Stage 1 inventory for existing worktrees. Retirement
decisions must remain conservative: retain PR #16, retain open draft PRs, retain
unknown unique source state, and remove only completed/stale worktrees with no
unpreserved source/test/config diff.

| Worktree | Branch / state | HEAD | Status | Retirement decision |
| --- | --- | --- | --- | --- |
| `/home/cz-jzb/workspace/vla-flywheel` | `main` | `1c0078155c89524047ec1fab947af83dd4058137` | root | retain root |
| `.worktrees/autovla-m3-persistent-zjh-training-store` | `dev/feat-autovla-m3-persistent-zjh-training-store` | `aaf3b79dccd1e82b57b09867b7ba3097f982b240` | PR #16 draft-open | retain open PR |
| `.worktrees/autovla-m3-data-format-pipeline-suite` | `dev/feat-autovla-m3-data-format-pipeline-suite` | `33c89aa97c7236e7b4034c6b8d9180a83618c3ee` | PR #20 merged | safe-retire-candidate |
| `.worktrees/autovla-m3-data-backend-bakeoff-dashboard` | `dev/feat-autovla-m3-data-backend-bakeoff-dashboard` | `bcf7a7ff8a6093bc54617a449b5d05a4c6ca03c0` | PR #18 merged | safe-retire-candidate |
| `.worktrees/autovla-m3-native-loader-timing-report-v2` | `dev/feat-autovla-m3-native-loader-timing-report-v2` | `f6243129506f938006c698b3fd50c5a625d06017` | PR #19 merged | safe-retire-candidate |
| `.worktrees/autovla-m3-zjh-gr00t-pipeline-readiness` | `dev/feat-autovla-m3-zjh-gr00t-pipeline-readiness` | `fa6b69a5d83ba7acd40546a23269d51e28bef8a3` | PR #13 merged | safe-retire-candidate |
| `.worktrees/autovla-m3-cpu-compute-microloop` | `dev/feat-autovla-m3-cpu-compute-microloop` | `aaef614686004af40979124ba66644be88d4a883` | completed M3 support | safe-retire-candidate |
| `.worktrees/autovla-m3-runner-readiness` | `dev/feat-autovla-m3-runner-readiness` | `00b881ad6bf7fac7844c96ef1ab7ec3544b88490` | completed M3 support | safe-retire-candidate |
| Other non-root worktrees | multiple | see runtime inventory | unknown or historical | retain until per-worktree diff audit |

## Retirement Rules

- Use `git worktree remove <path>` only for entries classified `safe-retire-candidate`.
- Do not use `--force`, `rm -rf`, `git clean`, branch deletion, or recursive
  deletion.
- Preserve any unique report not represented by this process archive before
  removal.
- Run `git worktree prune` only after safe removals.
- Retain PR #16 until the user makes an explicit backend decision.
