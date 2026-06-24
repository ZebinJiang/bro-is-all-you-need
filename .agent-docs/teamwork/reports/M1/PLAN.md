# M1 PLAN: Core Contract + Typed Config

| Field | Value |
| --- | --- |
| Milestone | M1 |
| Stage | PLAN |
| Date | 2026-06-18 |
| Manager | Codex |
| Recommended next stage | approve_execute |

## 1. Confirmed Claude Decisions

1. **Extra tests approved**: M1 ships `tests/core/test_action.py` and `tests/core/test_registry.py` in addition to the blueprint's `tests/core/test_raw_sample.py` and `tests/config/test_loader.py`. F1.2 (ActionChunk) and F1.4 (Registry) need direct TDD coverage.

2. **Runtime deps approved**: add `numpy` and `omegaconf` to `[project].dependencies` in `pyproject.toml`. Do NOT add torch, pyyaml, hydra, accelerate, deepspeed, transformers, or any runtime/training/Slurm dependency. Do NOT change existing `[dev]` deps.

3. **OmegaConf bridge filename approved**: `genesisvla/config/loader/legacy_omegaconf.py`. Defer `migrate_starvla.py` until a real StarVLA migration milestone.

4. **No code-input copying**: FluxVLA and dexbotic archives are reference-only. M1 copies ZERO source from them. No file-header attribution issues arise because nothing is copied. The mmengine-derived registry and OpenVLA-derived runner from FluxVLA, and dexbotic's BaseExp/transforms, are explicitly NOT imported.

5. **Worker coverage ledger approved**:
   - DISCUSS: no worker (Manager read-only inspection done).
   - PLAN: Manager drafts; no implementation.
   - EXECUTE: **1× `coding_integration_engineer`, serial, write-capable, whitelist only.**
   - VERIFY: **1× `code_reviewer`, read-only, independent review** (plus Claude-run `make genesis-check` external evidence).
   - REVIEW: Manager synthesis + independent code_reviewer findings + final `make genesis-check` + path-boundary evidence + publication readiness.

6. **Serial-only contracts** (no parallelism): all of `genesisvla/core/types/*`, `genesisvla/core/protocols/*`, `genesisvla/core/registry/*`, `genesisvla/config/schema/*`, `genesisvla/config/loader/*`, `pyrightconfig.genesisvla.json`, `.pre-commit-config.yaml`, `Makefile`, `pyproject.toml`, `.github/workflows/genesisvla.yml`, `tests/meta/test_repo_policy.py`.

7. **Design decisions confirmed**: numpy-backed arrays (no torch in M1 code or tests); frozen+slots dataclasses; `RunnerBackend` enum = {local, accelerate, ddp, fsdp, deepspeed}; generic eager per-domain `Registry[T]` with Duplicate/Unknown errors; Chinese docstrings per DISCUSS Topic I.

8. **Publication gate awareness**: M1 is NOT complete after local REVIEW. After REVIEW acceptance, a separate publication step (scans + dev/* commit + push + PR URL) is required. The PLAN must include a "Publication Plan" section describing this, but EXECUTE itself does NOT push/PR (that happens in the publication gate after Claude accepts REVIEW).

## 2. In Scope Vs Out Of Scope

### 2.1 Write Whitelist For M1 EXECUTE

Create:

```text
genesisvla/core/types/__init__.py
genesisvla/core/types/sample.py
genesisvla/core/types/action.py
genesisvla/core/types/modality.py
genesisvla/core/types/framework.py
genesisvla/core/protocols/__init__.py
genesisvla/core/protocols/framework.py
genesisvla/core/protocols/runner.py
genesisvla/core/protocols/policy.py
genesisvla/core/registry/__init__.py
genesisvla/core/registry/registry.py
genesisvla/core/registry/errors.py
genesisvla/core/compat/__init__.py
genesisvla/core/compat/legacy_sample.py
genesisvla/config/schema/__init__.py
genesisvla/config/schema/base.py
genesisvla/config/schema/model.py
genesisvla/config/schema/data.py
genesisvla/config/schema/runner.py
genesisvla/config/schema/experiment.py
genesisvla/config/loader/__init__.py
genesisvla/config/loader/load_yaml.py
genesisvla/config/loader/merge_cli.py
genesisvla/config/loader/validate.py
genesisvla/config/loader/export.py
genesisvla/config/loader/legacy_omegaconf.py
genesisvla/config/presets/local_debug.yaml
tests/core/__init__.py
tests/core/test_raw_sample.py
tests/core/test_action.py
tests/core/test_registry.py
tests/config/__init__.py
tests/config/test_loader.py
```

Modify:

```text
Makefile
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
pyproject.toml
tests/meta/test_repo_policy.py
```

### 2.2 Read-Only / Blacklist

M1 EXECUTE must not modify:

```text
starVLA/
code-input/
datasets/
runs/
configs/slurm/
pyrightconfig.json
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/coding_standard.md
docs/genesisvla/testing_standard.md
.agent-docs/asset_manifest.md
.agent-docs/code_input_integration.md
.agent-docs/git_workflow.md
```

M1 EXECUTE must not create:

```text
genesisvla/core/types/device.py
genesisvla/core/types/checkpoint.py
genesisvla/core/protocols/dataset.py
genesisvla/core/protocols/transform.py
genesisvla/core/protocols/processor.py
genesisvla/core/protocols/accelerator.py
genesisvla/core/registry/factories.py
genesisvla/core/compat/legacy_config.py
genesisvla/core/compat/legacy_starvla_imports.py
genesisvla/config/schema/deployment.py
genesisvla/config/schema/acceleration.py
genesisvla/config/loader/migrate_starvla.py
genesisvla/config/presets/single_gpu_smoke.yaml
genesisvla/config/presets/fsdp_8gpu.yaml
genesisvla/config/presets/deepspeed_zero2.yaml
genesisvla/config/presets/serve_local.yaml
```

M1 must not add dependencies for:

```text
torch
pyyaml
hydra
accelerate
deepspeed
transformers
Slurm/runtime training libraries
```

M1 must not change:

```text
[tool.black]
[tool.ruff]
existing Makefile check target
existing Makefile autoformat target
existing Makefile clean target
existing Makefile help target
```

## 3. Worker Coverage Ledger

| Stage | Worker type | Count | Mode | Read/write | Scope | Skip reason / evidence |
| --- | --- | ---: | --- | --- | --- | --- |
| DISCUSS | none | 0 | n/a | read-only Manager | Manager inspected repo, M0 artifacts, FluxVLA and dexbotic archives. | Exploration worker skipped because design questions were answered with direct read-only evidence in DISCUSS. |
| PLAN | none | 0 | n/a | report-only Manager | Produce this implementation plan under `.agent-docs/teamwork/reports/M1/PLAN.md`. | Implementation workers are not allowed in PLAN. |
| EXECUTE | `coding_integration_engineer` | 1 | serial | write-capable, whitelist only | Create M1 code/tests/config-gate updates exactly from this plan. | Required; M1 changes source, tests, configs, and quality gates. |
| VERIFY | `code_reviewer` | 1 | serial | read-only | Independently review M1 code/tests/configs/gates for correctness, no torch, no code-input copying, Chinese docstrings, frozen/slots, path safety, and complexity. | Slurm validation skipped because M1 has no Slurm/runtime behavior. Claude also runs external `make genesis-check` evidence due Codex sandbox Black limitation from M0. |
| REVIEW | none new unless Claude requests | 0 | n/a | Manager synthesis | Manager summarizes EXECUTE evidence, code_reviewer findings, final gate output, path-boundary state, and publication readiness. | REVIEW is not a fix stage. Defects reopen PLAN or scoped EXECUTE. |

### 3.1 Approved EXECUTE Worker Plan

```text
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M1 artifacts, run TDD red-green, run local validation, and return changed files, command outputs, risks, rollback notes, and complexity notes.
Writable paths: exactly the whitelist in Section 2.1.
Read-only paths: all others, including starVLA/, code-input/, datasets/, runs/, configs/slurm/, secrets, pyrightconfig.json, and existing GenesisVLA docs.
Stop condition: all in-scope artifacts exist, red/green TDD evidence captured, pytest tests/core tests/config passes, pytest tests/meta/test_repo_policy.py passes, pyright passes, and make genesis-check is attempted with evidence.
Worker must not: launch additional workers, modify out-of-scope files, copy code from code-input, add torch or other forbidden deps, run Slurm, push, create PRs, set passes=true, or mark M1 complete.
```

### 3.2 Approved VERIFY Worker Plan

```text
Worker type: code_reviewer
Count: 1
Mode: serial
Read-only: entire repository.
Scope: review M1 changes after EXECUTE for contract coherence, test adequacy, pyright strictness, no torch, no code-input copying, license cleanliness, Chinese docstrings, frozen+slots dataclasses, registry semantics, config validation behavior, and quality-gate routing.
Stop condition: return findings ordered by severity, residual risks, and an accept/request-fixes/block recommendation.
Worker must not: edit files, run Slurm, push, create PRs, set passes=true, or mark M1 complete.
```

## 4. TDD Red-Green Sequence

EXECUTE must capture red output before implementation and green output after implementation.

### T1: Create Tests First

Create these tests before creating implementation modules:

```text
tests/core/__init__.py
tests/core/test_raw_sample.py
tests/core/test_action.py
tests/core/test_registry.py
tests/config/__init__.py
tests/config/test_loader.py
```

Test functions and assertions:

`tests/core/test_raw_sample.py`

- `test_should_create_raw_sample_from_legacy_dict`
  - builds a legacy mapping with `images`, `instruction`, `actions`, `state`, `robot_tag`, and
    `metadata`;
  - calls `genesisvla.core.compat.legacy_sample.from_legacy_dict`;
  - asserts the result is `RawSample`;
  - asserts language, image keys, action shape, state shape, robot tag, and metadata survive.
- `test_should_validate_required_modalities`
  - builds a `RawSample` with only `"front"` image;
  - calls `validate_required_modalities(sample, ("front", "wrist"))`;
  - asserts `ValueError` contains `"wrist"`.
- `test_should_reject_invalid_action_shape`
  - builds a legacy mapping with one-dimensional action values;
  - calls `from_legacy_dict`;
  - asserts `ValueError` mentions action shape.
- `test_should_preserve_robot_tag_metadata`
  - builds a legacy mapping with `robot_tag="libero"` and metadata `{"episode_id": "ep-001"}`;
  - asserts `sample.robot_tag == "libero"` and metadata is preserved.

`tests/core/test_action.py`

- `test_should_validate_action_chunk_shape`
  - creates `ActionChunk(values=np.zeros((2, 7)), mask=None, horizon=2, action_dim=7,
    normalized=True)`;
  - asserts `horizon`, `action_dim`, and `values.shape`.
- `test_should_reject_invalid_action_mask_shape`
  - creates `values` with shape `(2, 7)` and `mask` with shape `(2, 6)`;
  - asserts `ActionChunk` raises `ValueError`.
- `test_should_create_action_space`
  - creates `ActionSpace(horizon=2, action_dim=7, normalized=True, names=("x", "y"))`;
  - asserts stored fields and tuple conversion for names.

`tests/core/test_registry.py`

- `test_should_register_and_get_item`
  - creates `Registry[type[object]]("frameworks")`;
  - registers a local dummy class under `"dummy"`;
  - asserts `get("dummy")` returns the class and `names()` contains `"dummy"`.
- `test_should_reject_duplicate_registry_key`
  - registers a key twice without `overwrite=True`;
  - asserts `DuplicateRegistrationError`.
- `test_should_raise_clear_error_for_missing_registry_key`
  - calls `get("missing")`;
  - asserts `UnknownRegistrationError` mentions `"missing"`.

`tests/config/test_loader.py`

- `test_should_load_yaml_into_experiment_config`
  - loads `genesisvla/config/presets/local_debug.yaml`;
  - asserts the returned object is `ExperimentConfig`;
  - asserts `runner.backend is RunnerBackend.LOCAL`.
- `test_should_apply_cli_dotlist_override`
  - loads the local preset with override `runner.backend=ddp`;
  - asserts the returned config has `RunnerBackend.DDP`.
- `test_should_emit_clear_error_on_invalid_backend`
  - loads or merges override `runner.backend=invalid`;
  - asserts `ValueError` contains `"runner.backend"` and allowed backend values.
- `test_should_export_resolved_yaml`
  - loads local preset;
  - exports resolved YAML to a pytest `tmp_path`;
  - reloads the YAML and asserts it preserves `schema_version`, `name`, and `runner.backend`.

### T2: Run Red Tests

Run before implementation:

```bash
pytest tests/core tests/config -v
```

Expected result:

```text
FAIL
```

Expected reason: imports such as `genesisvla.core.types.sample` and
`genesisvla.config.loader.load_yaml` are missing.

### T3: Implement M1 Artifacts

Implement only the files in Section 2.1 using the contracts in Sections 6-8.

### T4: Run Green Tests

Run after implementation:

```bash
pytest tests/core tests/config -v
```

Expected result:

```text
14 passed
```

### T5: Run Policy Tests

Run:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected:

```text
4 passed
```

### T6: Run Full Gate

Run:

```bash
make genesis-check
```

Expected:

```text
black, ruff, pyright, and pytest commands exit 0
```

Note: M0 established that Codex's process sandbox may hang on Black directory checks. The worker
should still attempt and record evidence. Claude external verification can provide authoritative
`make genesis-check` evidence during VERIFY.

## 5. Implementation Tasks

### Task 1: TDD Test Files

Target files:

```text
tests/core/__init__.py
tests/core/test_raw_sample.py
tests/core/test_action.py
tests/core/test_registry.py
tests/config/__init__.py
tests/config/test_loader.py
```

Steps:

1. Create `tests/core/__init__.py` and `tests/config/__init__.py` with Chinese module docstrings.
2. Add the test functions listed in Section 4.
3. Use numpy only; do not import torch.
4. Use pytest `raises` assertions for invalid shape, missing modality, duplicate registry key,
   unknown registry key, and invalid backend.

Check:

```bash
pytest tests/core tests/config -v
```

Expected result before implementation:

```text
FAIL because implementation modules do not exist yet
```

### Task 2: Core Types

Target files:

```text
genesisvla/core/types/__init__.py
genesisvla/core/types/sample.py
genesisvla/core/types/action.py
genesisvla/core/types/modality.py
genesisvla/core/types/framework.py
```

Steps:

1. Create package exports in `__init__.py`.
2. Implement numpy-backed aliases and dataclasses from Section 6.
3. Validate required modalities in `modality.py`.
4. Validate action shapes in `ActionChunk.__post_init__`.
5. Use Chinese module/class/function docstrings.
6. Keep imports standard library plus numpy only.

Check:

```bash
pytest tests/core/test_raw_sample.py tests/core/test_action.py -v
```

Expected result after Task 2 and Task 4:

```text
raw sample and action tests pass
```

### Task 3: Protocols

Target files:

```text
genesisvla/core/protocols/__init__.py
genesisvla/core/protocols/framework.py
genesisvla/core/protocols/runner.py
genesisvla/core/protocols/policy.py
```

Steps:

1. Implement only `FrameworkProtocol`, `RunnerProtocol`, and `PolicyProtocol`.
2. Use `typing.Protocol`.
3. Import M1 types from `genesisvla.core.types`.
4. Do not import torch or StarVLA.
5. Use Chinese docstrings on modules and public protocols.

Check:

```bash
pyright -p pyrightconfig.genesisvla.json
```

Expected result after all implementation:

```text
0 errors
```

### Task 4: Compat Legacy Sample Adapter

Target files:

```text
genesisvla/core/compat/__init__.py
genesisvla/core/compat/legacy_sample.py
```

Steps:

1. Implement `from_legacy_dict` from Section 6.6.
2. Support direct `images` mapping and flattened `observation.images.*` keys.
3. Support `language`, `instruction`, or `task` as language source.
4. Support `actions` or `action` as action source.
5. Support `state`, `proprio`, or `observation.state` as state source.
6. Preserve `robot_tag` and `metadata`.
7. Convert action/state/image payloads to numpy arrays where needed.
8. Reject non-2D action arrays with a clear `ValueError`.

Check:

```bash
pytest tests/core/test_raw_sample.py -v
```

Expected:

```text
4 passed
```

### Task 5: Registry

Target files:

```text
genesisvla/core/registry/__init__.py
genesisvla/core/registry/registry.py
genesisvla/core/registry/errors.py
```

Steps:

1. Implement errors from Section 6.4.
2. Implement generic `Registry[T]` from Section 6.4.
3. Keep registry eager and per-instance.
4. Do not implement decorators, lazy imports, factories, parent scopes, or global registry roots.
5. Use Chinese module/class/function docstrings.

Check:

```bash
pytest tests/core/test_registry.py -v
```

Expected:

```text
3 passed
```

### Task 6: Config Schema

Target files:

```text
genesisvla/config/schema/__init__.py
genesisvla/config/schema/base.py
genesisvla/config/schema/model.py
genesisvla/config/schema/data.py
genesisvla/config/schema/runner.py
genesisvla/config/schema/experiment.py
```

Steps:

1. Implement field lists from Section 7.
2. Use `@dataclass(frozen=True, slots=True)` for every config dataclass.
3. Implement `RunnerBackend` in `runner.py`.
4. Provide `RunnerBackend.from_value(value: str | RunnerBackend) -> RunnerBackend` or equivalent
   deterministic conversion.
5. Do not build models, datasets, or runners.
6. Use Chinese docstrings.

Check:

```bash
pytest tests/config/test_loader.py::test_should_emit_clear_error_on_invalid_backend -v
```

Expected after loader implementation:

```text
PASS
```

### Task 7: Config Loader And Preset

Target files:

```text
genesisvla/config/loader/__init__.py
genesisvla/config/loader/load_yaml.py
genesisvla/config/loader/merge_cli.py
genesisvla/config/loader/validate.py
genesisvla/config/loader/export.py
genesisvla/config/loader/legacy_omegaconf.py
genesisvla/config/presets/local_debug.yaml
```

Steps:

1. Implement loader functions from Section 6.7.
2. Use OmegaConf only in `legacy_omegaconf.py` and loader modules that need it.
3. Convert OmegaConf containers into plain dicts before dataclass construction.
4. Apply dotlist overrides through OmegaConf.
5. Export resolved YAML through OmegaConf.
6. Add `local_debug.yaml` exactly from Section 7.6.
7. Do not implement StarVLA migration.

Check:

```bash
pytest tests/config/test_loader.py -v
```

Expected:

```text
4 passed
```

### Task 8: Governance Gate Updates

Target files:

```text
Makefile
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
pyproject.toml
tests/meta/test_repo_policy.py
```

Steps:

1. Apply exact specs from Section 8.
2. Preserve M0 Black `--workers 1`.
3. Do not modify global `[tool.black]` or `[tool.ruff]`.
4. Do not modify `make check`, `make autoformat`, `make clean`, or `make help`.
5. Do not change existing `[project.optional-dependencies].dev` entries.

Checks:

```bash
pytest tests/meta/test_repo_policy.py -v
pyright -p pyrightconfig.genesisvla.json
make genesis-check
```

Expected:

```text
4 passed
0 pyright errors
make genesis-check exits 0, or records the known Codex Black sandbox limitation for Claude external verification
```

### Task 9: Path Boundary Review

Check:

```bash
git status --short
git diff --name-only HEAD
```

Expected:

```text
Only whitelist paths from Section 2.1 are new or modified for M1, plus any pre-existing dirty paths recorded separately.
No starVLA/, code-input/, datasets/, runs/, configs/slurm/, pyrightconfig.json, checkpoints, secrets, or source archives changed.
```

## 6. Type And Contract Specifications

### 6.1 Core Array Aliases

Location: `genesisvla/core/types/action.py` and re-export from `genesisvla/core/types/__init__.py`.

```python
from typing import Any, TypeAlias

from numpy.typing import NDArray

NumericArray: TypeAlias = NDArray[Any]
ImageLike: TypeAlias = NDArray[Any]
ActionMask: TypeAlias = NDArray[Any]
```

No torch alias appears in M1.

### 6.2 F1.1 Core Sample And Framework Types

Location: `genesisvla/core/types/sample.py`

```python
@dataclass(frozen=True, slots=True)
class RawSample:
    images: Mapping[str, ImageLike]
    language: str
    actions: NumericArray | None
    state: NumericArray | None
    robot_tag: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

Validation rules:

- `images` must not be empty.
- `language` must not be empty after stripping whitespace.
- `robot_tag` must not be empty after stripping whitespace.
- `actions`, when present, must be a 2-D numpy array shaped `(horizon, action_dim)`.
- `state`, when present, must be at least 1-D.

Location: `genesisvla/core/types/sample.py`

```python
@dataclass(frozen=True, slots=True)
class BatchSample:
    samples: tuple[RawSample, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def batch_size(self) -> int: ...
```

Validation rules:

- `samples` must not be empty.

Location: `genesisvla/core/types/framework.py`

```python
LossValue: TypeAlias = float | NumericArray

@dataclass(frozen=True, slots=True)
class ModelInput:
    batch: BatchSample
    tensors: Mapping[str, NumericArray] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class FrameworkOutput:
    loss: LossValue | None
    losses: Mapping[str, LossValue]
    metrics: Mapping[str, float]
    action_pred: ActionChunk | None = None
```

Rules:

- `FrameworkOutput` must not import torch.
- `losses` values may be floats or numpy arrays in M1.
- Later model milestones may widen `LossValue` to include torch tensors.

### 6.3 F1.2 Action Types

Location: `genesisvla/core/types/action.py`

```python
@dataclass(frozen=True, slots=True)
class ActionChunk:
    values: NumericArray
    mask: ActionMask | None
    horizon: int
    action_dim: int
    normalized: bool
```

Validation rules:

- `horizon > 0`.
- `action_dim > 0`.
- `values.ndim == 2`.
- `values.shape == (horizon, action_dim)`.
- `mask`, when present, must have the same shape as `values`.

Location: `genesisvla/core/types/action.py`

```python
@dataclass(frozen=True, slots=True)
class ActionSpace:
    horizon: int
    action_dim: int
    normalized: bool
    names: tuple[str, ...] = ()
```

Validation rules:

- `horizon > 0`.
- `action_dim > 0`.
- if `names` is not empty, `len(names) <= action_dim`.

### 6.4 F1.3 Protocols

Location: `genesisvla/core/protocols/framework.py`

```python
class FrameworkProtocol(Protocol):
    def forward(self, batch: ModelInput) -> FrameworkOutput: ...
    def predict_action(self, obs: ModelInput) -> ActionChunk: ...
```

Location: `genesisvla/core/protocols/runner.py`

```python
class RunnerProtocol(Protocol):
    def setup(self) -> None: ...
    def train(self) -> Mapping[str, float]: ...
    def evaluate(self) -> Mapping[str, float]: ...
    def save_checkpoint(self, step: int) -> Path: ...
    def resume(self, path: Path) -> int: ...
```

Location: `genesisvla/core/protocols/policy.py`

```python
class PolicyProtocol(Protocol):
    def reset(self) -> None: ...
    def select_action(self, observation: ModelInput) -> ActionChunk: ...
```

Rules:

- Protocol files must not import torch.
- Protocols define method shape only; no implementation or runtime behavior.

### 6.5 F1.4 Registry

Location: `genesisvla/core/registry/errors.py`

```python
class RegistryError(Exception): ...
class DuplicateRegistrationError(RegistryError): ...
class UnknownRegistrationError(RegistryError): ...
```

Location: `genesisvla/core/registry/registry.py`

```python
T = TypeVar("T")

class Registry(Generic[T]):
    def __init__(self, name: str) -> None: ...
    @property
    def name(self) -> str: ...
    def register(self, name: str, item: T, *, overwrite: bool = False) -> None: ...
    def get(self, name: str) -> T: ...
    def names(self) -> tuple[str, ...]: ...
    def items(self) -> tuple[tuple[str, T], ...]: ...
    def __contains__(self, name: object) -> bool: ...
    def __len__(self) -> int: ...
```

Rules:

- Duplicate registration without `overwrite=True` raises `DuplicateRegistrationError`.
- Missing `get` raises `UnknownRegistrationError`.
- `names()` returns sorted names for deterministic tests.
- `items()` returns deterministic `(name, item)` tuples sorted by name.
- No decorator API in M1.
- No lazy import, parent scope, builder, or global registry roots in M1.

### 6.6 RunnerBackend Enum

Location: `genesisvla/config/schema/runner.py`

```python
class RunnerBackend(str, Enum):
    LOCAL = "local"
    ACCELERATE = "accelerate"
    DDP = "ddp"
    FSDP = "fsdp"
    DEEPSPEED = "deepspeed"

    @classmethod
    def from_value(cls, value: str | RunnerBackend) -> RunnerBackend: ...
    @classmethod
    def values(cls) -> tuple[str, ...]: ...
```

Invalid conversion must raise:

```text
ValueError("invalid runner.backend ... allowed values: local, accelerate, ddp, fsdp, deepspeed")
```

### 6.7 F1.5 Config Dataclasses

All config dataclasses use:

```python
@dataclass(frozen=True, slots=True)
```

Location: `genesisvla/config/schema/base.py`

```python
@dataclass(frozen=True, slots=True)
class BaseConfig:
    schema_version: str = "1.0"
```

Location: `genesisvla/config/schema/model.py`

```python
@dataclass(frozen=True, slots=True)
class ModelConfig(BaseConfig):
    name: str = "debug-model"
    registry_key: str = "debug-model"
```

Location: `genesisvla/config/schema/data.py`

```python
@dataclass(frozen=True, slots=True)
class DataConfig(BaseConfig):
    name: str = "local-debug-data"
    root: str = "datasets/working/local_debug"
    required_modalities: tuple[str, ...] = ("front",)
```

Location: `genesisvla/config/schema/runner.py`

```python
@dataclass(frozen=True, slots=True)
class RunnerConfig(BaseConfig):
    backend: RunnerBackend = RunnerBackend.LOCAL
    batch_size: int = 1
    max_steps: int = 1
    device: str = "cpu"
```

Location: `genesisvla/config/schema/experiment.py`

```python
@dataclass(frozen=True, slots=True)
class ExperimentConfig(BaseConfig):
    name: str = "local_debug"
    seed: int = 7
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    runner: RunnerConfig = field(default_factory=RunnerConfig)
```

Validation rules:

- `schema_version` must equal `"1.0"` in M1.
- `name`, `model.name`, `model.registry_key`, `data.name`, `data.root`, and `runner.device`
  must be non-empty strings.
- `seed >= 0`.
- `runner.batch_size > 0`.
- `runner.max_steps > 0`.
- `data.required_modalities` must be non-empty.
- `runner.backend` is normalized through `RunnerBackend.from_value`.

### 6.8 Legacy Sample Adapter

Location: `genesisvla/core/compat/legacy_sample.py`

```python
def from_legacy_dict(
    payload: Mapping[str, Any],
    *,
    required_modalities: Iterable[str] = (),
) -> RawSample: ...
```

Accepted input rules:

- Images:
  - prefer `payload["images"]` when it is a mapping;
  - otherwise collect keys with prefix `observation.images.` and use the suffix as modality name.
- Language:
  - prefer `payload["language"]`;
  - fallback to `payload["instruction"]`;
  - fallback to `payload["task"]`.
- Actions:
  - prefer `payload["actions"]`;
  - fallback to `payload["action"]`.
- State:
  - prefer `payload["state"]`;
  - fallback to `payload["proprio"]`;
  - fallback to `payload["observation.state"]`.
- Robot tag:
  - prefer `payload["robot_tag"]`;
  - fallback to `payload["metadata"]["robot_tag"]` when present;
  - otherwise use `"unknown"`.
- Metadata:
  - start with `payload["metadata"]` when it is a mapping;
  - preserve at least `robot_tag` and any `episode_id`.

Output:

- returns a `RawSample`;
- converts image, action, and state values to numpy arrays through `np.asarray`;
- validates required modalities through `validate_required_modalities`.

### 6.9 Loader Functions

Location: `genesisvla/config/loader/legacy_omegaconf.py`

```python
def load_omegaconf(path: str | Path) -> DictConfig: ...
def merge_dotlist(config: DictConfig, overrides: Sequence[str]) -> DictConfig: ...
def to_plain_container(config: DictConfig) -> dict[str, Any]: ...
```

Rules:

- This is a GenesisVLA YAML bridge only.
- It does not import StarVLA.
- It does not migrate StarVLA configs.

Location: `genesisvla/config/loader/validate.py`

```python
def validate(config: ExperimentConfig) -> ExperimentConfig: ...
```

Location: `genesisvla/config/loader/load_yaml.py`

```python
def load_yaml(
    path: str | Path,
    *,
    overrides: Sequence[str] = (),
) -> ExperimentConfig: ...
```

Location: `genesisvla/config/loader/merge_cli.py`

```python
def merge_cli(config: ExperimentConfig, overrides: Sequence[str]) -> ExperimentConfig: ...
```

Location: `genesisvla/config/loader/export.py`

```python
def to_resolved_dict(config: ExperimentConfig) -> dict[str, Any]: ...
def export_resolved_yaml(config: ExperimentConfig, path: str | Path) -> None: ...
```

Dataclass construction rule:

- Convert plain dictionaries recursively into dataclasses.
- Convert `runner.backend` strings through `RunnerBackend.from_value`.
- Use `dataclasses.replace` or equivalent reconstruction for CLI override. Do not mutate frozen
  dataclass instances.

## 7. Config Schema Field Lists And Preset

### 7.1 `BaseConfig`

```text
schema_version: str = "1.0"
```

### 7.2 `ModelConfig`

```text
schema_version: str = "1.0"
name: str = "debug-model"
registry_key: str = "debug-model"
```

### 7.3 `DataConfig`

```text
schema_version: str = "1.0"
name: str = "local-debug-data"
root: str = "datasets/working/local_debug"
required_modalities: tuple[str, ...] = ("front",)
```

### 7.4 `RunnerConfig`

```text
schema_version: str = "1.0"
backend: RunnerBackend = RunnerBackend.LOCAL
batch_size: int = 1
max_steps: int = 1
device: str = "cpu"
```

### 7.5 `ExperimentConfig`

```text
schema_version: str = "1.0"
name: str = "local_debug"
seed: int = 7
model: ModelConfig = ModelConfig()
data: DataConfig = DataConfig()
runner: RunnerConfig = RunnerConfig()
```

### 7.6 `local_debug.yaml`

Path:

```text
genesisvla/config/presets/local_debug.yaml
```

Exact content shape:

```yaml
schema_version: "1.0"
name: local_debug
seed: 7
model:
  schema_version: "1.0"
  name: debug-model
  registry_key: debug-model
data:
  schema_version: "1.0"
  name: local-debug-data
  root: datasets/working/local_debug
  required_modalities:
    - front
runner:
  schema_version: "1.0"
  backend: local
  batch_size: 1
  max_steps: 1
  device: cpu
```

Preset rules:

- The preset is a config fixture only.
- It must not read or require an actual dataset.
- It must not imply model, training, Slurm, or deployment support.

## 8. Governance Update Specs

### 8.1 `Makefile`

Modify only the `genesis-check` target body. Preserve `--workers 1`.

Expected target:

```makefile
genesis-check:
	black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config
	ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config
	pyright -p pyrightconfig.genesisvla.json
	pytest tests/meta/test_repo_policy.py tests/core tests/config -v
```

Do not modify:

```text
check
autoformat
clean
help
```

### 8.2 `pyrightconfig.genesisvla.json`

Update include list to:

```json
[
  "genesisvla",
  "genesisvla/core",
  "genesisvla/config",
  "tests/meta",
  "tests/core",
  "tests/config"
]
```

Keep:

```json
"typeCheckingMode": "strict",
"pythonVersion": "3.10"
```

Keep existing excludes, including `starVLA`, `datasets`, and `runs`.

### 8.3 `.pre-commit-config.yaml`

Update local hook filters:

```yaml
files: ^(genesisvla/|tests/(meta|core|config)/).*\.py$
```

for `genesis-black` and `genesis-ruff`.

Update `genesis-pyright` files:

```yaml
files: ^(genesisvla/|tests/(meta|core|config)/|pyrightconfig\.genesisvla\.json)
```

Update `genesis-policy-tests` files:

```yaml
files: ^(docs/genesisvla/|tests/(meta|core|config)/|genesisvla/|pyrightconfig\.genesisvla\.json|Makefile|\.github/PULL_REQUEST_TEMPLATE\.md|\.pre-commit-config\.yaml)
```

Do not add remote pre-commit hooks.

### 8.4 `.github/workflows/genesisvla.yml`

Add trigger paths:

```yaml
- "tests/core/**"
- "tests/config/**"
```

Keep existing paths for `genesisvla/**`, `tests/meta/**`, docs, pyright, Makefile, pyproject,
pre-commit, PR template, and workflow file.

Replace install step:

```yaml
- name: Install GenesisVLA gate tools
  run: python -m pip install black ruff pytest pyright
```

with:

```yaml
- name: Install GenesisVLA package and gate tools
  run: python -m pip install -e ".[dev]"
```

Keep the final command:

```yaml
run: make genesis-check
```

### 8.5 `pyproject.toml`

Update only `[project].dependencies` from:

```toml
dependencies = [
]
```

to:

```toml
dependencies = [
    "numpy",
    "omegaconf",
]
```

Do not modify `[project.optional-dependencies].dev`.

Do not modify `[tool.black]` or `[tool.ruff]`.

### 8.6 `tests/meta/test_repo_policy.py`

Update `test_should_have_make_genesis_check` required fragments to:

```python
required_fragments = (
    "black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config",
    "ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config",
    "pyright -p pyrightconfig.genesisvla.json",
    "pytest tests/meta/test_repo_policy.py tests/core tests/config -v",
)
```

Update `test_should_have_pyright_strict_config` include expectation to require:

```python
{"genesisvla", "genesisvla/core", "genesisvla/config", "tests/meta", "tests/core", "tests/config"}
```

Do not modify other policy test behavior.

## 9. Validation Plan For VERIFY

### V1: File Existence

Command:

```bash
python - <<'PY'
from pathlib import Path

paths = [
    "genesisvla/core/types/__init__.py",
    "genesisvla/core/types/sample.py",
    "genesisvla/core/types/action.py",
    "genesisvla/core/types/modality.py",
    "genesisvla/core/types/framework.py",
    "genesisvla/core/protocols/__init__.py",
    "genesisvla/core/protocols/framework.py",
    "genesisvla/core/protocols/runner.py",
    "genesisvla/core/protocols/policy.py",
    "genesisvla/core/registry/__init__.py",
    "genesisvla/core/registry/registry.py",
    "genesisvla/core/registry/errors.py",
    "genesisvla/core/compat/__init__.py",
    "genesisvla/core/compat/legacy_sample.py",
    "genesisvla/config/schema/__init__.py",
    "genesisvla/config/schema/base.py",
    "genesisvla/config/schema/model.py",
    "genesisvla/config/schema/data.py",
    "genesisvla/config/schema/runner.py",
    "genesisvla/config/schema/experiment.py",
    "genesisvla/config/loader/__init__.py",
    "genesisvla/config/loader/load_yaml.py",
    "genesisvla/config/loader/merge_cli.py",
    "genesisvla/config/loader/validate.py",
    "genesisvla/config/loader/export.py",
    "genesisvla/config/loader/legacy_omegaconf.py",
    "genesisvla/config/presets/local_debug.yaml",
    "tests/core/__init__.py",
    "tests/core/test_raw_sample.py",
    "tests/core/test_action.py",
    "tests/core/test_registry.py",
    "tests/config/__init__.py",
    "tests/config/test_loader.py",
]
missing = [path for path in paths if not Path(path).exists()]
if missing:
    print("V1 FAIL", missing)
    raise SystemExit(1)
print("V1 PASS")
PY
```

Expected:

```text
V1 PASS
```

### V2: Core And Config Tests

Command:

```bash
pytest tests/core tests/config -v
```

Expected:

```text
14 passed
```

### V3: Meta Policy Tests

Command:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Expected:

```text
4 passed
```

### V4: Full GenesisVLA Gate

Command:

```bash
make genesis-check
```

Expected:

```text
exit code 0
```

Note: Claude should run this externally or provide independent evidence if Codex sandbox Black
directory checks hit the known M0 multiprocessing timeout. The command itself must be correct and
must include `--workers 1`.

### V5: Pyright Strict

Command:

```bash
pyright -p pyrightconfig.genesisvla.json
```

Expected:

```text
0 errors, 0 warnings, 0 informations
```

### V6: Path Boundary

Commands:

```bash
git status --short
git diff --name-only HEAD
```

Expected:

```text
Only Section 2.1 whitelist paths changed for M1, plus pre-existing dirty paths explicitly noted.
No starVLA/, code-input/, datasets/, runs/, configs/slurm/, pyrightconfig.json, checkpoints, source archives, or secrets changed.
```

### V7: Independent Code Review

Worker:

```text
code_reviewer
```

Review checks:

- no torch import in M1 code or tests;
- no code copied from `code-input/FluxVLA-main.zip` or `code-input/dexbotic-main.zip`;
- no file-header attribution obligation created by copied source;
- all new Python modules have Chinese module docstrings;
- public dataclasses, protocols, enum, registry, and loader functions have Chinese docstrings;
- config dataclasses use frozen+slots;
- registry is generic, eager, per-instance, and deterministic;
- invalid action shapes, invalid masks, missing modalities, duplicate keys, missing keys, and invalid
  backend values produce clear errors;
- OmegaConf bridge does not import StarVLA or migrate StarVLA configs;
- quality gates cover `tests/core` and `tests/config`;
- implementation complexity is linear in input sizes and avoids hidden large array copies;
- no baseline contamination or StarVLA source modification.

Expected:

```text
code_reviewer recommends accept or identifies only non-blocking residual risks.
```

## 10. Publication Plan

Publication runs only after Claude accepts REVIEW. EXECUTE must not push or create a PR.

Publication steps after REVIEW acceptance:

1. Read `.agent-docs/git_workflow.md`.
2. Confirm current branch is `dev/*`:

   ```bash
   branch="$(git branch --show-current)"
   case "$branch" in
     dev/*) printf 'branch: %s\n' "$branch" ;;
     *) echo "branch must be dev/* before commit, push, or PR: $branch"; exit 1 ;;
   esac
   ```

3. Run whitespace checks:

   ```bash
   git diff --check
   git diff --cached --check
   ```

4. Run secret-pattern scans from `.agent-docs/git_workflow.md`.
5. Run blocked artifact-extension scan.
6. Run large staged-file scan.
7. Run large text-diff scan.
8. Optionally run `gitleaks detect --source . --redact` if `gitleaks` is installed.
9. Stage the M1 deliverables only.
10. Commit on the `dev/*` branch with a structured message, for example:

    ```text
    feat(genesisvla): Add M1 core contracts and typed config.
    ```

11. Push the branch to the configured remote, using the user-provided GitHub proxy if needed.
12. Open or update a PR.
13. Record the PR URL in:

    ```text
    .agent-docs/teamwork/reports/M1/REVIEW.md
    .agent-docs/teamwork/roadmap_progress.md
    .agent-docs/teamwork/workspace/task-board.md
    ```

14. Provide the PR URL to Claude and the user.

If any publication step is blocked by scans, branch state, network, credentials, permissions, or
remote state, record:

```text
ready_to_publish_blocked
```

with the exact blocker. Do not mark M1 complete without a PR URL.

## 11. Rollback Plan

Rollback before publication:

```bash
rm -rf genesisvla/core/types
rm -rf genesisvla/core/protocols
rm -rf genesisvla/core/registry
rm -rf genesisvla/core/compat
rm -rf genesisvla/config/schema
rm -rf genesisvla/config/loader
rm -rf genesisvla/config/presets
rm -rf tests/core
rm -rf tests/config
git restore -- Makefile pyrightconfig.genesisvla.json .pre-commit-config.yaml .github/workflows/genesisvla.yml pyproject.toml tests/meta/test_repo_policy.py
```

If any governance file is untracked in the current local checkout, `git restore` may not apply. In
that case, restore it from the M0 state recorded in `.agent-docs/teamwork/reports/M0/EXECUTE.md`
and `.agent-docs/teamwork/reports/M0/REVIEW.md`, then re-run:

```bash
pytest tests/meta/test_repo_policy.py -v
```

Rollback after publication:

```bash
git revert <m1-commit-sha>
```

Then run:

```bash
make genesis-check
```

and record the revert PR URL if the M1 PR was already pushed.

## 12. Risk List

- Contract overreach: creating too much target-tree surface can imply unsupported model, runner,
  deployment, checkpoint, or acceleration behavior.
- Torch dependency creep: torch imports would slow contract tests and complicate Pyright strict mode.
- Config schema bloat: mirroring StarVLA, FluxVLA, or Dexbotic runtime configs would pull model,
  deployment, and training concerns into M1.
- TDD drift: implementation may satisfy named tests while leaving ActionSpace, Registry, or
  FrameworkOutput under-specified. The extra tests and V7 review mitigate this.
- Dependency declaration gap: CI must install `numpy` and `omegaconf` through `pip install -e
  ".[dev]"`.
- Frozen dataclass shallow immutability: numpy arrays remain mutable; M1 must document owned-input
  assumptions and avoid hidden copies.
- Pyright strict friction: `numpy.typing` and OmegaConf containers require careful narrowing.
- Legacy confusion: OmegaConf bridge is not StarVLA migration.
- Code-input license/attribution risk: FluxVLA and dexbotic inform design only. Copying source would
  require separate license review and attribution. M1 copies zero source.
- Publication risk: M1 is not complete until scans, commit, push, and PR URL exist. If blocked,
  status must be `ready_to_publish_blocked`.
- Codex sandbox validation risk: `make genesis-check` may hit the known Black directory-check
  timeout in Codex. Claude external verification is required if this recurs.

## 13. Recommended Next Stage

Recommend `approve_execute`.

Approved worker plan to carry forward:

```text
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M1 artifacts, run TDD red-green and validation, capture evidence.
Writable paths: Section 2.1 whitelist only.
Read-only paths: all others.
Stop condition: tests and gates in Sections 4 and 9 are run or documented with exact blocker, worker returns changed files, commands, outputs, complexity notes, residual risks, and rollback notes.
Worker must not: modify out-of-scope paths, copy code-input source, add forbidden dependencies, launch workers, run Slurm, push, create PRs, or mark M1 complete.
```

## 14. Handoff

```text
===HANDOFF===
Completed:
- Read required M1 PLAN context, including worker coverage and publication gate rules.
- Converted approved M1 DISCUSS decisions into an executable PLAN.
- Defined in-scope and out-of-scope files, TDD sequence, worker coverage ledger, type contracts, config schema, governance updates, validation checks, publication plan, rollback plan, and risks.

Pending:
- Claude gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.

Decisions:
- EXECUTE requires 1x coding_integration_engineer, serial, whitelist only.
- VERIFY requires 1x code_reviewer plus Claude external make genesis-check evidence if needed.
- M1 uses numpy and OmegaConf only; no torch or code-input copying.
- M1 completion requires post-REVIEW publication gate and PR URL.

Files Affected:
- .agent-docs/teamwork/reports/M1/PLAN.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor.
Next actor: Claude.
===END HANDOFF===
```
