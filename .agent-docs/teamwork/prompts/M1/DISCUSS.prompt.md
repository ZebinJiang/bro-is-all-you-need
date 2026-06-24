# M1 DISCUSS — GenesisVLA Core Contract + Typed Config

## Your Role

You are the **Codex Manager**.
Milestone: **M1 — Core Contract + Typed Config**.
Stage: **DISCUSS**.

M0 was governance/quality-gate setup. M1 is the first real **code-shape** milestone: typed contracts, protocols, registry, and config schema. These are the contract layer that every later milestone depends on.

You are **read-only** for source code during DISCUSS. You may write to:
- `.agent-docs/teamwork/reports/M1/DISCUSS.md`
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/workspace/task-board.md`
- `runs/tmp/code-input-inspection/M1/` only if temporary archive inspection output is required

Do NOT write source code during DISCUSS.

---

## Required Reading

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/GenesisVLA_Blueprint_Roadmap.html` — sections: Interfaces (6.1-6.3), M1 Features + TDD, Code Standards
5. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
6. `.agent-docs/teamwork/roadmap_progress.md`
7. `.agent-docs/code_input_integration.md`
8. `.agent-docs/asset_manifest.md`
9. `docs/genesisvla/rfc_000_architecture.md` (M0 RFC — read what was published)
10. `docs/genesisvla/coding_standard.md` (M0 coding rules)
11. `docs/genesisvla/testing_standard.md` (M0 testing rules)
12. `pyrightconfig.genesisvla.json`
13. `pyproject.toml`
14. `tests/meta/test_repo_policy.py` (so you can match its testing style)

---

## Registered Code-Input Assets To Use

The user has staged two source archives under `code-input/`, and they are registered in `.agent-docs/asset_manifest.md`:

- `code-input/FluxVLA-main.zip`
- `code-input/dexbotic-main.zip`

Use them as read-only reference sources during M1 DISCUSS. They are intended to inform GenesisVLA design, not to be copied into the project during DISCUSS.

Required use in M1 DISCUSS:

- Inspect FluxVLA for runner lifecycle, deployment/inference patterns, acceleration hooks, registry/config organization, and checkpoint lifecycle ideas.
- Inspect Dexbotic for typed/dataclass config ideas, transform pipeline organization, backend enum/config patterns, and maintainability lessons.
- Compare those findings against the GenesisVLA blueprint and current StarVLA layout.
- Record which ideas should influence M1 and which must be deferred.
- Record any license/source-attribution risk before recommending future integration.

Allowed inspection methods:

- `unzip -l` to inventory archive paths.
- `unzip -p` or equivalent read-only archive inspection for specific files.
- If extraction is necessary, extract only to `runs/tmp/code-input-inspection/M1/` and record the extracted paths in the DISCUSS report.

Do not mutate `code-input/`. Do not integrate copied code in DISCUSS. Future integration must go through Claude-approved PLAN/EXECUTE worker coverage and the Code-Input Integration Workflow.

---

## M1 Blueprint Scope

From blueprint section 8 (M1):

**Features:**
- F1.1 RawSample / BatchSample / ModelInput / FrameworkOutput
- F1.2 ActionChunk / ActionMask / ActionSpace
- F1.3 FrameworkProtocol / RunnerProtocol / PolicyProtocol
- F1.4 Typed registry
- F1.5 dataclass config schema
- F1.6 OmegaConf legacy bridge
- F1.7 resolved config export

**TDD (from blueprint):**
```
tests/core/test_raw_sample.py
- should_create_raw_sample_from_legacy_dict
- should_validate_required_modalities
- should_reject_invalid_action_shape
- should_preserve_robot_tag_metadata

tests/config/test_loader.py
- should_load_yaml_into_experiment_config
- should_apply_cli_dotlist_override
- should_emit_clear_error_on_invalid_backend
- should_export_resolved_yaml
```

**Core type sketches (blueprint section 6.1):**
```python
@dataclass(frozen=True)
class RawSample:
    images: dict[str, ImageLike]
    language: str
    actions: np.ndarray | None
    state: np.ndarray | None
    robot_tag: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ActionChunk:
    values: np.ndarray | torch.Tensor
    mask: np.ndarray | torch.Tensor | None
    horizon: int
    action_dim: int
    normalized: bool

@dataclass(frozen=True)
class FrameworkOutput:
    loss: torch.Tensor | None
    losses: Mapping[str, torch.Tensor]
    metrics: Mapping[str, float]
    action_pred: ActionChunk | None = None
```

---

## Stage Objective

Discuss and resolve M1 design questions so Claude can approve a PLAN. M1 has real code-shape decisions that bind later milestones — be thorough.

## M1+ Worker Coverage Requirement

M1 is the first milestone covered by the minimum worker coverage policy.

During DISCUSS you remain read-only for source code and do not launch implementation workers unless Claude explicitly dispatches an exploration worker plan. Your DISCUSS report must prepare the next PLAN to include a worker coverage ledger:

- whether PLAN needs a read-only exploration worker, or why Codex Manager discussion is enough;
- which write-capable worker type should own M1 EXECUTE implementation (`coding_integration_engineer` or `coding_heavy_engineer`);
- which independent read-only worker should own M1 VERIFY (`code_reviewer` and/or `slurm_validation_engineer` if relevant), or what Claude external evidence would replace it;
- what independent review evidence M1 REVIEW must include;
- which files/contracts must remain serial because they touch shared config, type contracts, registry behavior, or quality gates.

Do not propose Manager-only EXECUTE for M1 implementation. If a later VERIFY or REVIEW finds defects, recommend returning to PLAN or scoped EXECUTE instead of allowing inline Manager fixes.

## M1 Publication Requirement

The user requires every completed GenesisVLA milestone to be pushed and to provide a PR link.

M1 DISCUSS does not publish anything, but your DISCUSS report must remind Claude that M1 is not complete after local REVIEW alone. M1 completion requires:

- required git scans from `.agent-docs/git_workflow.md`;
- milestone deliverables committed on a `dev/*` branch;
- branch pushed to the configured remote;
- PR opened or updated;
- PR URL recorded in the M1 REVIEW/progress records and provided to Claude/user.

If push or PR creation is blocked, the milestone status is `ready_to_publish_blocked`, not complete.

---

## Discussion Topics

### Topic A: ImageLike / Tensor Type Strategy

The blueprint sketches use `np.ndarray | torch.Tensor` directly. This creates two issues:

- **Hard dependency on torch**: importing torch is heavy and slow; pyright strict mode on torch is painful.
- **Numpy is OK**: `numpy` is much lighter and already in the existing repo.

Options to discuss:
1. Use `np.ndarray | torch.Tensor` directly (matches blueprint, heavy torch dep).
2. Define `ImageLike = TypeAlias = np.ndarray` for M1 and add torch tensor support later (when actual model code lands).
3. Use `Protocol`-based duck typing (`HasShape`, `HasDtype`, `__array__`) so neither numpy nor torch is a hard dep.
4. Use `numpy.typing.ArrayLike` (loose) for now, narrow later.

Investigate: which option fits M1's "contract layer only" scope without prematurely binding to torch?

Also discuss: are tests allowed to import torch, or should M1 tests use numpy only?

### Topic B: Module Layout Inside `genesisvla/core/`

Blueprint target tree shows:
```
genesisvla/core/
  types/
    sample.py
    action.py
    modality.py
    device.py
    checkpoint.py
  protocols/
    dataset.py
    transform.py
    processor.py
    framework.py
    runner.py
    policy.py
    accelerator.py
  registry/
    registry.py
    factories.py
    errors.py
  compat/
    legacy_sample.py
    legacy_config.py
    legacy_starvla_imports.py
```

But M1 only delivers F1.1-F1.4 (types + protocols + registry). Discuss:
- For M1, which subdirectories must exist now vs. deferred to later milestones (M2-M7)?
- For F1.3 (Protocols), the blueprint lists 3 protocols (Framework/Runner/Policy). The target tree shows 7 protocol files. Recommend exactly which 3 protocol files M1 creates and what stays as stubs/empty.
- For F1.4 (Typed registry), do we need `registry.py`, `factories.py`, AND `errors.py`, or is `registry.py` + `errors.py` sufficient for M1?
- Should `compat/legacy_sample.py` live in M1 (because F1.1 has "should_create_raw_sample_from_legacy_dict") or only in M2?

### Topic C: Config Schema (F1.5) — How Much Schema for M1?

Blueprint target tree shows:
```
genesisvla/config/
  schema/
    base.py
    model.py
    data.py
    runner.py
    deployment.py
    acceleration.py
    experiment.py
  loader/
    load_yaml.py
    merge_cli.py
    validate.py
    export.py
    migrate_starvla.py
  presets/
    local_debug.yaml
    single_gpu_smoke.yaml
    fsdp_8gpu.yaml
    deepspeed_zero2.yaml
    serve_local.yaml
```

The TDD `tests/config/test_loader.py` only requires:
- load YAML into experiment config
- apply CLI dotlist override
- error on invalid backend
- export resolved YAML

Discuss for M1:
- Which schema files are minimum viable for the TDD to pass? Probably `base.py`, `experiment.py`, and one of {model, data, runner} as a stub.
- Which loader files? `load_yaml.py`, `merge_cli.py`, `validate.py`, `export.py` are likely needed; `migrate_starvla.py` is F1.6 (OmegaConf legacy bridge).
- Which presets? Recommend M1 ships ONE preset (`local_debug.yaml`) so the export round-trip TDD has a real fixture.
- Should `ExperimentConfig` field shape be a `@dataclass` or `@dataclass(frozen=True)`? Frozen has implications for CLI override (need to use `dataclasses.replace`).

### Topic D: OmegaConf Bridge (F1.6) — Scope

Blueprint says "OmegaConf legacy bridge" but does not specify what "legacy" means. Options:
1. Bridge between OmegaConf YAML format and GenesisVLA dataclass config (same project).
2. Bridge from existing StarVLA OmegaConf configs to GenesisVLA dataclass config (migration).
3. Both.

For M1, recommend the narrowest meaningful scope. Investigate: do existing StarVLA configs use OmegaConf? If yes, what's the shape (look at `examples/` or `configs/`)?

Also discuss: does `omegaconf` need to be added to `pyproject.toml [dev]`? Or `[runtime]` / new `[core]` group? The TDD only requires reading YAML — that can use stdlib `tomllib`/`yaml`. OmegaConf adds dotlist override + structured config.

Decision needed: does M1 take a hard dep on `omegaconf`, or use stdlib + custom dotlist parser?

### Topic E: Typed Registry (F1.4) — Generic vs Domain

Blueprint section 6 doesn't give a registry signature. Discuss:
1. Should `Registry[T]` be a generic `dict[str, type[T]]` with `register/get/list`?
2. Should it support multiple namespaces (framework registry, action_head registry, etc.) or one global?
3. Should it be lazy (defer construction until `get`) or eager?
4. How does it interact with config loading — does config carry a registry key string like `framework: "gr00t-native"` that the registry resolves to a class?

Recommend a minimal signature for M1.

### Topic F: TDD Test Layout

Blueprint specifies `tests/core/test_raw_sample.py` and `tests/config/test_loader.py`. Currently:
- `tests/meta/` exists (from M0)
- `tests/core/` and `tests/config/` do NOT exist

Discuss:
- Create `tests/core/__init__.py`, `tests/config/__init__.py` in M1.
- Must M1 update `pyrightconfig.genesisvla.json` to include `tests/core` and `tests/config`?
- Must M1 update `.pre-commit-config.yaml` path filter to include the new test dirs?
- Must M1 update the M0 `genesis-check` Makefile target to also check `tests/core tests/config`?

These are governance updates — they should be part of M1 PLAN whitelist.

### Topic G: Backend Enum / Allowed Values

The TDD has `should_emit_clear_error_on_invalid_backend`. What is "backend" in this context?
- Training backend (accelerate / ddp / fsdp / deepspeed)? Likely yes — matches blueprint Dexbotic-influence "train backend enum".
- If yes, define the enum for M1 (which values are valid).

### Topic H: Dependencies and Tooling

For M1, what new Python deps land in `pyproject.toml`?
- `numpy` (almost certainly needed)
- `omegaconf` (depends on Topic D decision)
- `pyyaml` (alternative to omegaconf for plain YAML)

Should these go in `[runtime]`, `[core]`, or top-level `dependencies`? `pyproject.toml` currently has no `[runtime]`. Discuss whether M1 introduces a new dep group or uses existing.

### Topic I: Chinese Docstring Density

M0 set the rule: "新或修改 code 中文 docstring/comments". M1 is the first real code dump. Discuss the practical interpretation:
- Public dataclasses: full Chinese docstring with field-level explanation?
- Public Protocols: docstring per method?
- Private helpers: comment only, or full docstring?
- Field-level shape/dtype hints (e.g., `images: dict[str, ImageLike]` — explain shape in docstring)?

Codex Manager should propose a concrete style for M1 that matches `coding_standard.md`.

### Topic J: Frozen vs Mutable Dataclasses

Blueprint sketches use `@dataclass(frozen=True)`. Frozen has implications:
- Hashable by default (good for cache keys)
- Cannot be modified after construction (good for safety)
- CLI override needs `dataclasses.replace(...)` (slightly more verbose)
- Sub-dataclasses must also be frozen for proper hashing

Recommend a uniform rule for M1.

### Topic K: Out of Scope

What MUST M1 NOT do?
- No model implementation, no runners, no actual training loops.
- No StarVLA source edits.
- No new Slurm/runtime scripts.
- No checkpoints, datasets, or model paths.

Confirm and add anything else that DISCUSS reveals as risky.

---

## Investigation Commands (read-only)

```bash
# Existing StarVLA config style
find . -name "*.yaml" -path "*config*" -not -path "./.git/*" 2>/dev/null | head -10
find starVLA -name "*.py" -path "*/config*" 2>/dev/null | head -10
grep -l "omegaconf" pyproject.toml starVLA/ -r 2>/dev/null | head -5

# Existing types or dataclasses in StarVLA
grep -rln "dataclass" starVLA/ 2>/dev/null | head -10

# pyproject.toml current shape
sed -n '/\[project/,/^\[/p' pyproject.toml | head -50

# Existing tests / pyright scope
ls tests/
cat pyrightconfig.genesisvla.json

# M0 docs published
ls docs/genesisvla/
head -30 docs/genesisvla/rfc_000_architecture.md
head -30 docs/genesisvla/coding_standard.md

# Registered code-input source references
unzip -l code-input/FluxVLA-main.zip | head -80
unzip -l code-input/dexbotic-main.zip | head -80
unzip -l code-input/FluxVLA-main.zip | grep -Ei "(runner|config|registry|checkpoint|deploy|infer|triton|fsdp)" | head -80
unzip -l code-input/dexbotic-main.zip | grep -Ei "(config|dataclass|transform|backend|dataset|pipeline)" | head -80
```

---

## Output

Write a comprehensive DISCUSS report to:
```
.agent-docs/teamwork/reports/M1/DISCUSS.md
```

Required sections:
1. Investigation summary (what you found in the repo)
2. Code-input source findings:
   - FluxVLA findings relevant to M1
   - Dexbotic findings relevant to M1
   - ideas to use now vs. defer
   - license/source-attribution risks
3. Answers to Topics A-K, each with a recommendation
4. Open questions for Claude (anything you cannot decide)
5. Risks
6. Recommended PLAN scope:
   - exact file list M1 will create
   - exact governance updates (Makefile, pyrightconfig, pre-commit, pyproject)
   - dependencies added
   - M1 worker coverage ledger recommendation
   - M1 publication gate reminder
7. Recommended next stage action

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- ...
Decisions:
- ...
Files Affected:
- .agent-docs/teamwork/reports/M1/DISCUSS.md (written)
Next-Actor-Notes:
Returning control to Claude Supervisor.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

STOP after DISCUSS.md and HANDOFF. Do NOT write code, tests, or configs.
PLAN requires Claude's `start_plan` decision.
