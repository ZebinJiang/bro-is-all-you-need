# M1 EXECUTE-FIX-2 — legacy_sample metadata contract fix

## Your Role

You are the **Codex Manager**. Milestone **M1**, stage **EXECUTE (scoped fix)**.

The M1 VERIFY independent `code_reviewer` (Sagan) found ONE blocking contract defect, which Claude
confirmed:

`genesisvla/core/compat/legacy_sample.py::from_legacy_dict` does NOT preserve `robot_tag` and
top-level `episode_id` into `RawSample.metadata` as PLAN Section 6.8 requires. The current test
`test_should_preserve_robot_tag_metadata` locks in the wrong contract (asserts metadata WITHOUT
`robot_tag`).

PLAN Section 6.8 metadata contract:
> Metadata: start with `payload["metadata"]` when it is a mapping; preserve at least `robot_tag`
> and any `episode_id`.

This is a scoped EXECUTE fix. Dispatch the approved worker.

---

## Approved Worker Plan

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: fix legacy_sample metadata contract + update its test. Two files only.
Writable paths:
- genesisvla/core/compat/legacy_sample.py
- tests/core/test_raw_sample.py
```

Everything else read-only.

## The Fix (exact contract)

In `from_legacy_dict`, after building the base `metadata` dict from `payload["metadata"]`:

1. **Preserve `robot_tag` into metadata**: set `metadata["robot_tag"] = robot_tag` (the resolved
   robot_tag value, so metadata always carries provenance). Do this even when robot_tag came from a
   fallback — metadata should reflect the final robot_tag.

2. **Preserve top-level `episode_id` into metadata**: if `payload` has a top-level `episode_id` key
   and metadata does not already have one, set `metadata["episode_id"] = payload["episode_id"]`.

3. **Do not drop existing user metadata keys.** Existing keys from `payload["metadata"]` are kept;
   only add/ensure `robot_tag` and `episode_id`.

Then update `tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata` to assert the
CORRECT contract, e.g.:

```python
sample = from_legacy_dict(
    _legacy_payload(robot_tag="libero", metadata={"episode_id": "ep-001"}),
)
assert sample.robot_tag == "libero"
assert sample.metadata["robot_tag"] == "libero"      # robot_tag preserved into metadata
assert sample.metadata["episode_id"] == "ep-001"     # existing metadata kept
```

Add at least one extra assertion covering top-level `episode_id` preservation if the test helper
supports it, OR a second small test. Keep it minimal but prove the Section 6.8 contract.

Chinese docstrings/comments on any changed code per coding_standard.md.

## Validation (Manager runs; deps-present env e.g. /tmp/vla-flywheel-m0-tools/bin)

```bash
cd /home/cz-jzb/workspace/vla-flywheel
export PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH
pytest tests/core/test_raw_sample.py -v
pytest tests/core tests/config -v          # expect 14 passed (or 15 if you added a test)
make genesis-check                          # if Codex sandbox blocks pyright/black, run steps individually + note Claude external evidence
```

## Writable paths (Manager)

- `.agent-docs/teamwork/reports/M1/EXECUTE_FIX_2.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude)
- worker writable: the 2 files above

## Report

`.agent-docs/teamwork/reports/M1/EXECUTE_FIX_2.md`:
1. The exact diff of legacy_sample.py + test_raw_sample.py
2. Before: reviewer finding restated
3. After: `pytest tests/core/test_raw_sample.py -v` + `pytest tests/core tests/config -v` evidence
4. make genesis-check result (or per-step)
5. Path boundary (only the 2 files changed)
6. Recommended next stage: VERIFY-2 (re-review the 2 files) or REVIEW

## Stop Condition

STOP after report + HANDOFF. End with `===HANDOFF=== ... Next actor: Claude. ===END HANDOFF===`.
