# AutoVLA Testing Standard

## Scope

This standard applies to AutoVLA-native paths and policy tests. It does not
turn historical StarVLA tests, examples, or known backlog into the M0 acceptance
surface.

## TDD-First

AutoVLA uses TDD-first development for behavior changes. Tests are written
and observed failing before implementation, then the implementation is kept as
small as the validated behavior allows.

## Test Categories

- Unit tests validate pure behavior and layer contracts.
- Failure-mode tests cover invalid input, missing resources, and unsafe states.
- Config validation tests check schema, defaults, and migration behavior.
- Smoke tests verify runnable entrypoints without claiming model quality.
- Minimal documentation snippets keep examples synchronized with supported APIs.

## M0 Policy Tests

`tests/meta/test_repo_policy.py` owns M0 repository policy coverage:

- `test_should_have_autovla_docs`
- `test_should_have_make_autovla_check`
- `test_should_have_pyright_strict_config`
- `test_should_have_pr_template_with_test_plan`

## Local Gate

`make autovla-check` is the M0 local gate. It runs Black, Ruff, Pyright, and
pytest for AutoVLA-owned paths and meta policy tests.

## StarVLA Backlog Isolation

Existing StarVLA backlog does not block AutoVLA CI. Do not use full-repo
`make check` as the M0 acceptance gate because legacy lint or type issues are
outside this milestone.

## Slurm Boundary

CPU and static checks can run locally for M0. Compute-heavy tests require Slurm
allocation and wrapper evidence in later milestones when runtime behavior is in
scope.
