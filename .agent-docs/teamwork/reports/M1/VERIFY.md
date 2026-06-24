# M1 VERIFY Report - Independent Code Review

Milestone: M1 - Core Contract + Typed Config
Stage: VERIFY
Manager: Codex Manager
Timestamp: 2026-06-18T18:41:23+08:00
Recommendation: `scoped_execute_fix`

## 1. code_reviewer Dispatch Summary

Claude approved one independent read-only VERIFY worker:

- Worker type: `code_reviewer`
- Count: 1
- Mode: serial, read-only
- Agent id: `019eda4d-1800-7692-a425-30f160128558`
- Agent nickname: Sagan
- Writable paths: none
- Scope: review all M1 source, tests, and governance files for correctness, contract coherence, and governance compliance.

The worker completed and was retired. It did not modify files, run Slurm, commit, push, open PRs, or mark M1 complete.

Reviewed targets:

- `genesisvla/core/types/*.py`
- `genesisvla/core/protocols/*.py`
- `genesisvla/core/registry/*.py`
- `genesisvla/core/compat/*.py`
- `genesisvla/config/schema/*.py`
- `genesisvla/config/loader/*.py`
- `genesisvla/config/presets/local_debug.yaml`
- `tests/core/*.py`
- `tests/config/*.py`
- `Makefile`
- `pyrightconfig.genesisvla.json`
- `.pre-commit-config.yaml`
- `.github/workflows/genesisvla.yml`
- `pyproject.toml`
- `tests/meta/test_repo_policy.py`

## 2. Findings Table

| Severity | File(s) | Finding | Manager Classification | Recommendation |
| --- | --- | --- | --- | --- |
| `clean` | `pyproject.toml` | Reviewer flagged `pytest` and `pyright` in `[project.optional-dependencies].dev` as an M1 plan violation. | False positive for M1. M0 explicitly approved and implemented adding `pytest` and `pyright` to the dev extra. M1's "do not change dev deps" means M1 must not add or remove from that already-approved list. | No fix. Preserve current dev deps. |
| `blocking-defect` | `genesisvla/core/compat/legacy_sample.py`, `tests/core/test_raw_sample.py` | `from_legacy_dict` does not preserve `robot_tag` or top-level `episode_id` into `RawSample.metadata` as M1 PLAN Section 6.8 requires. Current test locks in metadata without `robot_tag`. | Real contract defect. The legacy adapter currently copies only `payload["metadata"]`, while the approved contract says metadata must preserve at least `robot_tag` and any `episode_id`. | Return to scoped EXECUTE fix. Limit fix to `legacy_sample.py` and `test_raw_sample.py`; preserve `robot_tag` and top-level `episode_id` in metadata and update tests. |
| `non-blocking-risk` | `tests/meta/test_repo_policy.py` | Public test functions in M0 meta tests do not have Chinese docstrings. | Non-blocking. This is M0 legacy test code accepted in prior stages; M1 new core/config tests follow the docstring rule. | Optional future cleanup. Do not block M1 on this alone. |
| `non-blocking-risk` | `genesisvla/config/loader/validate.py` | `_str_value()` coerces non-string scalar values with `str()`, so `name: null` can become `"None"` and pass non-empty checks. | Non-blocking risk. Current approved TDD covers invalid backend clearly; stricter scalar validation may be useful before config complexity grows. | Consider including a narrow validation hardening test/fix in a future scoped fix if Claude wants stricter M1 config semantics. |
| `clean` | M1 code/tests | No `torch` import found; no StarVLA import or StarVLA config migration in the OmegaConf bridge; no code-input copying signal found. | Clean. | No action. |
| `clean` | M1 dataclasses and registry | Dataclasses use frozen+slots; registry is generic, eager, per-instance, and deterministic through sorted names/items. | Clean. | No action. |

## 3. Claude External Gate Evidence

Claude provided independent external validation evidence for M1 after EXECUTE-FIX-1:

- `pytest tests/core tests/config -v` -> 14 passed.
- `pytest tests/meta tests/core tests/config` -> 18 passed.
- `make genesis-check` -> exit 0 in a dependency-present environment.
- `make genesis-check` covered Black, Ruff, Pyright with 0 errors, and 18 tests.
- The Codex sandbox Black timeout and 142 Pyright diagnostics are accepted environment issues, not code defects.

Functional correctness gates are therefore established externally. VERIFY's remaining purpose was independent code review.

## 4. Contract-Coherence Assessment

The M1 contract layer is mostly coherent:

- `RawSample`, `BatchSample`, `ModelInput`, `FrameworkOutput`, `ActionChunk`, `ActionSpace`, protocols, registry, and config dataclasses fit together cleanly.
- The numpy-only choice is preserved; no M1 code or tests import torch.
- The OmegaConf bridge remains narrow and does not migrate or import StarVLA.
- Registry behavior matches the approved generic eager per-instance design.

The blocking coherence gap is in legacy sample metadata preservation: the adapter does not yet keep the provenance fields that the approved M1 plan requires later consumers to rely on.

## 5. Worker Coverage Ledger Status

| Stage | Required Worker Evidence | Status |
| --- | --- | --- |
| DISCUSS | Manager read-only inspection; no worker required. | Done in M1 DISCUSS. |
| PLAN | Manager plan; no implementation worker. | Done in M1 PLAN. |
| EXECUTE | 1x `coding_integration_engineer`, serial, write-capable. | Done; M1 artifacts implemented and EXECUTE report written. |
| EXECUTE-FIX-1 | 1x `coding_integration_engineer`, serial, scoped config fix. | Done; pytest pythonpath fix report written. |
| VERIFY | 1x `code_reviewer`, serial, read-only independent review. | Done in this report; agent retired. |
| REVIEW | Manager synthesis plus independent review evidence and final gate/path-boundary evidence. | Pending Claude gate decision. |

## 6. Residual Risks

- One blocking M1 contract defect remains: legacy sample metadata preservation does not meet the approved Section 6.8 contract.
- Config validation currently accepts some non-string scalar values after string coercion. This is not covered by current TDD and should be tightened before configs become a wider user-facing API.
- M0 legacy meta tests have no per-test Chinese docstrings. This is not an M1 functionality issue but remains a style consistency risk.
- Publication is still pending after REVIEW acceptance. M1 is not complete until the required git scans, dev branch commit, push, PR creation/update, and PR URL recording are completed.

## 7. Recommendation

Recommendation: `scoped_execute_fix`.

Rationale: functional gates are green, but the independent reviewer found one real blocking contract defect in the legacy sample adapter. VERIFY must not patch source inline. Claude should approve a narrow EXECUTE fix for:

- `genesisvla/core/compat/legacy_sample.py`
- `tests/core/test_raw_sample.py`

Expected fix scope:

- Preserve `robot_tag` in `RawSample.metadata`.
- Preserve top-level `episode_id` in `RawSample.metadata` when present.
- Keep existing metadata keys without dropping user-provided metadata.
- Update `test_should_preserve_robot_tag_metadata` to assert the approved metadata contract.
- Re-run `pytest tests/core/test_raw_sample.py -v`, `pytest tests/core tests/config -v`, and the relevant full gate evidence.
