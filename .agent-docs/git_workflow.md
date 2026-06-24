# Git Workflow

## Branch rule

Every new task must be developed on a `dev/*` branch. Do not develop task changes directly on `main` or `master`.

Recommended branch names:

```text
dev/<task-id>-<short-description>
dev/code-input-<integration-name>
dev/research-<idea-name>
```

## Starting a task

1. Inspect current branch and working tree.
2. If on `main` or `master`, create or switch to an appropriate `dev/*` branch before editing.
3. If a previous PR was merged, sync `main`/`master` and then recreate or rebase the dev branch.
4. Do not append unrelated work to an existing dev branch.

## Completion and PR rule

After every completed GenesisVLA milestone:

1. Ensure validation evidence is recorded.
2. Ensure Slurm submission evidence exists for cluster-dependent work.
3. Run the required local scans below and record the output or skip reason.
4. Ensure `.agent-docs/progress.txt` is updated when the task records governance evidence.
5. Create a commit with a structured message.
6. Push the `dev/*` branch to the configured remote, using the user-provided GitHub proxy when needed.
7. Open or update a pull request for the milestone deliverables.
8. Record the PR URL in the milestone review/progress records and provide the PR URL to Claude and the user.
9. The Manager may merge only if the user explicitly asks the Manager to review and merge.

The user's standing rule is that a milestone is not complete until the pushed PR URL exists. If commit, push, or PR creation is blocked by scans, network, credentials, permissions, or remote state, record `ready_to_publish_blocked` with the exact blocker and do not mark the milestone complete.

## Required local scans

Run these before every commit, push, or PR. No output from a blocking scan means pass. Any positive finding blocks the commit, push, or PR unless the user explicitly overrides the risk.

Branch check:

```bash
branch="$(git branch --show-current)"
case "$branch" in
  dev/*) printf 'branch: %s\n' "$branch" ;;
  *) echo "branch must be dev/* before commit, push, or PR: $branch"; exit 1 ;;
esac
```

Whitespace and conflict-marker check:

```bash
git diff --check
git diff --cached --check
```

Secret-pattern scan over staged/tracked content:

```bash
secret_pattern='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{20,}|WANDB_API_KEY[[:space:]]*[:=][[:space:]]*[A-Za-z0-9_-]{20,}|wandb_api_key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
if git grep --cached -nIE "$secret_pattern" -- .; then
  echo "secret-like staged content found; stop"
  exit 1
fi
if git grep -nIE "$secret_pattern" -- .; then
  echo "secret-like tracked working-tree content found; stop"
  exit 1
fi
```

Blocked artifact-extension scan for staged files that will exist after commit:

```bash
blocked_artifacts='(\.pt|\.pth|\.ckpt|\.safetensors|\.onnx|\.bin|\.parquet|\.arrow|\.npy|\.npz|\.zip|\.tar|\.tar\.gz|\.tgz|\.zst)$'
if git diff --cached --name-only --diff-filter=ACMR | grep -Ei "$blocked_artifacts"; then
  echo "blocked staged artifact extension found; stop"
  exit 1
fi
```

Large staged-file scan for files that will exist after commit:

```bash
git diff --cached --name-only --diff-filter=ACMR -z \
  | xargs -0 -r stat -c '%s %n' \
  | awk '$1 > 52428800 {print "large staged file:", $0; bad=1} END {exit bad}'
```

Large text-diff scan:

```bash
git diff --cached --numstat \
  | awk '$1 != "-" && $2 != "-" && ($1 + $2) > 20000 {print "large text diff:", $0; bad=1} END {exit bad}'
```

Optional stronger scan when `gitleaks` is installed:

```bash
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --redact
fi
```

## Commit message convention

Use:

```text
<type>(<scope>): <Description>.
```

Allowed types:

```text
feat, fix, bugfix, docs, style, refactor, perf, test, chore, scm
```

Commit body should include:

```md
## Summary

## Why

## Impact

## Validation

## Slurm Evidence

## Risks / Notes
```

## Merge handling

If a PR has already been merged, do not continue using a stale dev branch. Sync or recreate the dev branch before the next task.
