# M10 Governance Meta Repair W1

Status: `REQUEST_CHANGES`

## Identity and boundaries

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-governance-meta-repair-w1`
- Branch: `dev/m10-governance-meta-repair-w1`
- HEAD: `3b078eb6d4be0f9b523c15ecc3a8994309af6472`
- Startup state: tracked-clean; index empty.
- Route: `gpt-5.6-sol / medium`.
- DevSpace MCP: `no`.
- Descendants: `none`.
- Git/PR mutation: no stage, commit, push, PR, merge, or integration-branch mutation.
- Slurm/GPU/network/install: not used; this was a lightweight local governance-test repair.

## Changed files

- `tests/meta/test_repo_policy.py`
- `coordination/reports/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/owner-governance-meta-repair-w1.md`

No baseline, source, product config, wrapper, workflow, Makefile, upstream registry, asset,
dataset, dependency, or other test path was modified.

## Semantic repair rationale

1. Strict Pyright profile: the test now asserts the approved public profile
   `envs/training-deepspeed/.venv`, Python 3.10, strict mode, the current product include
   surface, governance-test exclusion, and protected-path exclusions. It no longer claims
   that the quality bootstrap venv is a universal product environment.
2. Upstream provenance: schema v3 is parsed as YAML. Every active source row must carry one
   or more exact 40-character lowercase Git revisions, repository, license and license status,
   reviewed paths, reuse class, copy status, local destination, and notice action. The test
   rejects placeholders, tracked archives/source trees, undeclared reuse classes, inconsistent
   reference-only copy status, and unattributed adapted-source status. It explicitly preserves
   `NO_BACKEND_WINNER` and copied-code header/notice policy.
3. Product/governance wrapper split: the test finds the product file-inventory and Ruff gate
   lines, then checks each approved product scope independently. It separately requires product
   pytest/model pytest, governance pytest, product Ruff, governance Ruff, `code-input` exclusion,
   and asset-path safety markers without relying on obsolete contiguous shell substrings.
4. CI gate: the workflow is parsed with `yaml.safe_load` and command steps are inspected
   semantically, avoiding a generic `yaml.load` security-review surface. The
   assertion accepts the canonical product wrapper as a direct CI invocation and independently
   requires bootstrap, governance, and clean build gates with all build isolation arguments.
   This assertion remains fail-closed because the exact frozen HEAD does not contain either the
   direct product wrapper command or the clean build wrapper command.

## Exact blocker

At `3b078eb6d4be0f9b523c15ecc3a8994309af6472`,
`.github/workflows/autovla.yml` contains both bootstrap commands and `make governance-check`, but
contains neither:

- `bash scripts/quality/autovla_check_project_local.sh`; nor
- `scripts/quality/autovla_build_verify_project_local.sh` with the required isolated-build
  arguments.

Therefore the task prompt's statement that current CI directly invokes the canonical wrapper and
preserves the build gate does not match this worktree. The workflow is outside this worker's write
scope, so the meta test must not conceal the product/CI defect.

## Validation

Runtime Python:
`/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-production-data-plane-gr00t-runtime/runs/tmp/AUTOVLA-M6-PRODUCTION-DATA-PLANE-GR00T-RUNTIME-BRINGUP-001/envs/runtime-cpu/bin/python`
with `PYTHONPATH` set to this worktree and no dependency installation.

- Four originally failing node IDs before repair: `4 failed`.
- Four node IDs after semantic repair: `3 passed, 1 failed`; only the real CI gate defect remains.
- Full `tests/meta/test_repo_policy.py`: `26 passed, 1 failed`; same CI gate defect.
- `tests/meta/test_model_routing_governance.py`: `8 passed`.
- Focused M10 asset/config/model/training set: `77 passed` in 4.65 seconds.
- Black for changed test: pass.
- Ruff for changed test: pass.
- `py_compile` for changed test: pass.
- Strict Pyright attempt: not viable against the approved profile because
  `envs/training-deepspeed/.venv` is absent in this isolated worktree. Exact result was
  `16 errors, 2 warnings`: missing configured venv; unresolved-source warnings for PyYAML and
  setuptools; existing unresolved/unknown typing for conditional tomli, PyArrow fixture calls,
  and setuptools namespace discovery. No assertion-body diagnostic remains in the new repair.
- Manager checkpoint rerun after replacing `yaml.load`/`BaseLoader` with `yaml.safe_load`:
  focused meta `3 passed, 1 failed`, full repo-policy `26 passed, 1 failed`, routing
  `8 passed`; the sole failure remains the same explicit CI product/build gate blocker.
- `git diff --check`: pass after report creation and Manager checkpoint repair.
- Final index: empty; tracked changes are limited to the changed test plus this Owner report.

Evidence is under ignored path
`runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/quality/governance-meta-repair-w1/`.

## Complexity and efficiency

- Pyright and CI checks are linear in the parsed configuration/workflow size.
- Provenance validation is linear in source rows and their revisions/path lists.
- Wrapper scope validation is linear in wrapper lines plus a fixed, bounded scope set.
- No model execution, tensor movement, GPU allocation, distributed communication, dataset I/O,
  or baseline runtime behavior changed.

## Residual risks and required follow-up

- Blocking: an authorized workflow writer must restore direct canonical product-wrapper and clean
  build-wrapper CI steps, then rerun this worker's four focused tests and full meta suite.
- Non-blocking for this bounded repair: strict Pyright on the meta test requires the approved
  training-deepspeed environment or an authorized equivalent profile-specific environment.
- The YAML checks intentionally validate current schema-v3 semantics; future schema evolution must
  update the test together with an explicit governance migration.

## Rollback

Revert only the two files listed under Changed files. This restores the stale assertions and removes
the report; no product, baseline, asset, dataset, environment, or generated evidence state requires
rollback.
