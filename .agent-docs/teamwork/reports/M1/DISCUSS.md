# M1 DISCUSS: Core Contract + Typed Config

| Field | Value |
| --- | --- |
| Milestone | M1 |
| Stage | DISCUSS |
| Date | 2026-06-18 |
| Manager | Codex |
| Recommended next action | start_plan |

## 1. Investigation Summary

Required governance and M0 artifacts were read:

- `AGENTS.md`
- `boundaries.txt`
- `CLAUDE.md`
- `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
- `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/code_input_integration.md`
- `.agent-docs/asset_manifest.md`
- `.agent-docs/git_workflow.md`
- `docs/genesisvla/rfc_000_architecture.md`
- `docs/genesisvla/coding_standard.md`
- `docs/genesisvla/testing_standard.md`
- `pyrightconfig.genesisvla.json`
- `pyproject.toml`
- `tests/meta/test_repo_policy.py`

Repository facts from the requested read-only investigation:

- M0 is recorded as complete in `.agent-docs/teamwork/roadmap_progress.md`.
- `genesisvla/` exists only as M0 stubs:
  - `genesisvla/__init__.py`
  - `genesisvla/core/__init__.py`
  - `genesisvla/config/__init__.py`
  - `genesisvla/py.typed`
- `tests/` currently contains `README.md` and `tests/meta/`; `tests/core/` and `tests/config/`
  do not exist.
- `pyrightconfig.genesisvla.json` currently includes `genesisvla`, `genesisvla/core`,
  `genesisvla/config`, and `tests/meta`, with strict mode enabled.
- `Makefile` currently has `genesis-check` scoped to `genesisvla tests/meta`.
- `.pre-commit-config.yaml` is path-scoped to `genesisvla/` and `tests/meta/`.
- `.github/workflows/genesisvla.yml` installs only Black, Ruff, Pytest, and Pyright, then runs
  `make genesis-check`.
- `pyproject.toml` has an empty `[project].dependencies` list and M0 dev tools under
  `[project.optional-dependencies].dev`.
- StarVLA has existing YAML configs under `starVLA/config/...`, including nested training configs
  with `framework`, `datasets`, and `trainer` sections.
- StarVLA imports and uses OmegaConf heavily in training, dataloader, model, and framework helper
  paths.
- Existing StarVLA config use is legacy behavior and should remain read-only in M1.

Requested archive inspection was completed with `unzip -l` and `unzip -p`. No extraction was
required, so no files were written under `runs/tmp/code-input-inspection/M1/`.

Registered staged code-input assets:

- `code-input/FluxVLA-main.zip`
  - Registered sha256: `aa01ddbd17c33cae95753d3d391f50d94498f5717363cfba1b0a9ed5f793e48d`
  - Allowed use: planning/reference only
  - Mutation allowed: no
- `code-input/dexbotic-main.zip`
  - Registered sha256: `a5750eadae596bd0bd413ebe51c3e68bd5b589b140d39d3f3e62266427a4dc30`
  - Allowed use: planning/reference only
  - Mutation allowed: no

Blueprint facts relevant to M1:

- M1 features are F1.1 through F1.7: core samples, action contracts, three protocols,
  typed registry, dataclass config schema, OmegaConf bridge, and resolved config export.
- Blueprint M1 TDD names:
  - `tests/core/test_raw_sample.py`
  - `tests/config/test_loader.py`
- The target tree is larger than M1 and includes future checkpoint, device, accelerator,
  deployment, and StarVLA migration modules that should not all be created now.
- The blueprint standards require Black, Ruff, Pyright strict, Google-style docstrings,
  100-char line length, no wildcard imports, no library `print`, no implicit `.cuda()`,
  resolved config export, schema version, and migration support for breaking config changes.

## 2. Code-Input Source Findings

### 2.1 FluxVLA Findings Relevant To M1

Inspected representative archive files:

- `FluxVLA-main/README.md`
- `FluxVLA-main/LICENSE`
- `FluxVLA-main/CITATION.cff`
- `FluxVLA-main/fluxvla/engines/utils/registry.py`
- `FluxVLA-main/fluxvla/engines/utils/root.py`
- `FluxVLA-main/fluxvla/engines/utils/builder.py`
- `FluxVLA-main/fluxvla/engines/utils/checkpoint_utils.py`
- `FluxVLA-main/fluxvla/engines/runners/base_train_runner.py`
- `FluxVLA-main/fluxvla/engines/runners/fsdp_train_runner.py`
- `FluxVLA-main/fluxvla/engines/runners/base_inference_runner.py`
- `FluxVLA-main/fluxvla/engines/runners/serving/serve.py`
- `FluxVLA-main/fluxvla/engines/runners/serving/zmq_server.py`
- `FluxVLA-main/configs/pi05/pi05_paligemma_aloha_remote_inference.py`
- `FluxVLA-main/configs/pi05/pi05_paligemma_aloha_rtc_kernel_inference.py`
- `FluxVLA-main/configs/gr00t/gr00t_eagle_3b_libero_10_full_finetune.py`

Observed ideas:

- FluxVLA has a strong full-stack lifecycle orientation: config-driven train, eval, inference,
  remote serving, checkpoint resume, and acceleration are treated as one engineering loop.
- Its runner lifecycle is useful as a future reference: setup, train/evaluate, checkpoint save,
  resume, mixed precision, distributed strategy, and inference phases are explicit concepts.
- It uses registry roots for many domains: tokenizers, transforms, datasets, backbones, heads,
  VLA models, runners, collators, metrics, processors, and operators.
- It supports config-driven module construction through an mmengine-derived registry and builder.
- Its checkpoint lifecycle includes full model state, optimizer state, tokenizer/config sidecars,
  dataset statistics, and shared tensor recovery.
- Its deployment/inference layer separates local and remote inference, uses named server endpoints,
  and captures serializer/compression/profiling choices in config.
- Its acceleration hooks include RTC guidance, CUDA/Triton-oriented inference configs, and explicit
  accelerated inference docs.

M1-relevant lessons:

- Keep `RunnerProtocol` lifecycle method names stable now because later runner implementations will
  need setup/train/evaluate/save/resume semantics.
- Keep registry minimal now, but design it to allow later domain-specific registry instances.
- Keep config objects capable of carrying registry key strings without instantiating concrete
  models in M1.
- Treat checkpoint, deployment, remote inference, RTC, Triton, and distributed strategy details as
  future-contract pressure, not M1 implementation.

What not to import into M1:

- Do not copy FluxVLA's mmengine registry. It is powerful but too heavy and brings scope, lazy
  imports, parent registries, default scopes, builders, and third-party attribution into a contract
  milestone.
- Do not copy FluxVLA runner code. It imports torch/distributed/safetensors and implements real
  training behavior, which is out of scope.
- Do not copy remote serving or ZMQ code. Deployment is not M1.
- Do not copy acceleration code or configs. Acceleration is later milestone scope.

### 2.2 Dexbotic Findings Relevant To M1

Inspected representative archive files:

- `dexbotic-main/README.md`
- `dexbotic-main/LICENSE`
- `dexbotic-main/pyproject.toml`
- `dexbotic-main/.pre-commit-config.yaml`
- `dexbotic-main/dexbotic/exp/backend_resolver.py`
- `dexbotic-main/dexbotic/exp/base_exp.py`
- `dexbotic-main/dexbotic/config/rl/libero_10_ppo_dexbotic_pi0.yaml`
- `dexbotic-main/dexbotic/config/rl/training_backend/fsdp.yaml`
- `dexbotic-main/dexbotic/data/dataset/transform/common.py`
- `dexbotic-main/dexbotic/data/dataset/transform/default_transform.py`

Observed ideas:

- Dexbotic uses dataclasses for many config groups such as optimizer, trainer, model, tokenizer,
  and action processing.
- Dexbotic has explicit backend configuration/resolution concepts for FSDP/FSDP2/DDP/DeepSpeed.
- Its backend resolver normalizes version-specific FSDP fields and records warnings.
- Its YAML configs are layered and include backend-specific config fragments.
- Its transform pipeline composes small callable transforms in sequence.
- Transform code shows a useful data-shape lesson: convert raw nested episode data to numpy early
  when data contracts need predictable shape handling.

M1-relevant lessons:

- Borrow the idea of dataclass config sections, but keep M1 dataclasses behavior-free.
- Borrow the idea of clear backend allowed values and explicit error messages.
- Borrow the idea of a transform pipeline for future M2, but do not create transform modules in M1.
- Borrow the lesson that config schema should separate model/data/runner/action concerns, but keep
  M1's field set minimal.

What not to import into M1:

- Do not copy `BaseExp` or dataclass methods that build models, optimizers, tokenizers, datasets,
  or transform pipelines.
- Do not import accelerate, torch, transformers, deepspeed, hydra, megfile, EasyDict, or RL runtime
  dependencies for M1.
- Do not copy transform implementation code. Transform pipeline implementation belongs in M2.

### 2.3 Ideas To Use Now Vs. Defer

Use in M1:

- Generic typed registry with duplicate/missing-key errors.
- Runner backend enum as a contract: `local`, `accelerate`, `ddp`, `fsdp`, `deepspeed`.
- Dataclass config sections: model, data, runner, experiment.
- Resolved config export.
- OmegaConf bridge for GenesisVLA YAML plus dotlist overrides.
- Numpy-first core sample/action validation.
- Protocol method names that anticipate later lifecycle work.

Defer:

- mmengine-style scoped registry and builder.
- Lazy factory construction.
- Domain registry globals for real model families.
- StarVLA config migration.
- FluxVLA remote inference, deployment server, serializer, and endpoint routing.
- FluxVLA checkpoint manager semantics.
- FSDP/DDP/DeepSpeed runtime resolution.
- Transform pipeline implementation.
- Torch tensor support in core value objects.
- CUDA/Triton/RTC acceleration hooks.

### 2.4 License And Source-Attribution Risks

- FluxVLA archive includes Apache License 2.0 and source headers. Some files explicitly state
  upstream origin, for example an mmengine-derived registry and an OpenVLA-derived FSDP runner.
  Any future code copying requires attribution and license review for both FluxVLA and its stated
  upstream source.
- Dexbotic archive includes an MIT license file, while its `pyproject.toml` classifier says
  "Apache Software License". This mismatch should be resolved before copying any source.
- M1 DISCUSS uses both archives only as reference material. No code is copied and no staged input is
  mutated.
- Future PLAN/EXECUTE must treat any copied third-party code as external code requiring file-header
  attribution, license status, purpose, risk, and Claude-approved worker scope.

## 3. Topic A: ImageLike / Tensor Type Strategy

Recommendation: M1 should use numpy-backed public aliases and tests, with no torch import.

M1 is a contract-layer milestone, not a model-runtime milestone. Importing torch in core contracts
would make basic config/type tests pay a heavy import cost and would make Pyright strict mode harder
before model code exists. FluxVLA and Dexbotic both confirm that torch belongs in runtime/model or
runner code, not in the first lightweight contract layer.

M1 contract:

- Add `numpy` as a runtime dependency.
- Use `numpy.typing.NDArray[Any]` for stored arrays.
- Define local aliases such as `ImageLike`, `NumericArray`, and `ActionMask`.
- Keep torch out of M1 code and tests.
- Design aliases so later milestones can widen them to `np.ndarray | torch.Tensor` or a structural
  tensor protocol once real model framework code exists.

Tests should use numpy only.

Why not Protocol-only array strategy now:

- It avoids torch dependency, but is too loose for shape/dtype validation unless M1 immediately
  coerces to numpy.
- It can hide invalid inputs behind duck-typed `shape` attributes.

Why not `numpy.typing.ArrayLike` for stored values:

- It is appropriate for function inputs, but too loose for immutable contract objects that later
  layers will rely on.

## 4. Topic B: Module Layout Inside `genesisvla/core/`

Recommendation: create only the M1-owned subset of the target tree.

Create in M1:

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
```

Defer from M1:

- `genesisvla/core/types/device.py`
- `genesisvla/core/types/checkpoint.py`
- `genesisvla/core/protocols/dataset.py`
- `genesisvla/core/protocols/transform.py`
- `genesisvla/core/protocols/processor.py`
- `genesisvla/core/protocols/accelerator.py`
- `genesisvla/core/registry/factories.py`
- `genesisvla/core/compat/legacy_config.py`
- `genesisvla/core/compat/legacy_starvla_imports.py`

The three protocol files for M1 should be exactly:

- `framework.py`: `FrameworkProtocol`
- `runner.py`: `RunnerProtocol`
- `policy.py`: `PolicyProtocol`

Do not create empty stubs for the other protocol files. Empty target-tree placeholders create a
false support signal and add import surface without tests.

For registry, `registry.py` plus `errors.py` is sufficient. `factories.py` is deferred until a
milestone needs lazy construction or object factories.

`compat/legacy_sample.py` belongs in M1 because the TDD explicitly requires
`should_create_raw_sample_from_legacy_dict`.

## 5. Topic C: Config Schema Scope

Recommendation: keep M1 config schema small but real.

Create in M1:

```text
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
```

Minimum schema shape:

- `BaseConfig`: common `schema_version`.
- `ModelConfig`: minimal model identity fields such as `name` and `registry_key`.
- `DataConfig`: minimal data identity fields such as `name`, `root`, and required modalities.
- `RunnerConfig`: `backend`, batch size, max steps, device string.
- `ExperimentConfig`: top-level `schema_version`, `name`, `seed`, `model`, `data`, and `runner`.

Use frozen dataclasses for all schema classes. CLI dotlist override should return a new config
object rather than mutating an existing one.

Ship one preset only: `local_debug.yaml`. It gives loader/export tests a real fixture without
claiming training, Slurm, model, dataset, or deployment support.

Defer:

- `deployment.py`
- `acceleration.py`
- `single_gpu_smoke.yaml`
- `fsdp_8gpu.yaml`
- `deepspeed_zero2.yaml`
- `serve_local.yaml`
- full StarVLA migration.

## 6. Topic D: OmegaConf Bridge Scope

Recommendation: M1 should implement the narrow bridge only.

M1 should support:

- loading a YAML file through OmegaConf;
- applying OmegaConf-style CLI dotlist overrides;
- resolving the OmegaConf container;
- converting the resolved container into GenesisVLA dataclasses;
- exporting the resolved GenesisVLA config back to YAML.

M1 should not migrate existing StarVLA training configs into full GenesisVLA configs. Existing
StarVLA configs and FluxVLA/Dexbotic examples have broad nested framework, dataset, trainer,
deployment, and backend structures. Mapping those shapes is a separate migration task and would
exceed M1's contract scope.

Dependency recommendation:

- Add `omegaconf` to `[project].dependencies`.
- Do not add `pyyaml` separately unless implementation proves OmegaConf is insufficient.
- Do not add torch.

File naming recommendation:

- Use `genesisvla/config/loader/legacy_omegaconf.py` for M1.
- Defer the target-tree `migrate_starvla.py` name until actual StarVLA config migration is scoped.

## 7. Topic E: Typed Registry

Recommendation: implement a generic, eager, per-domain registry.

Minimal M1 API:

```text
Registry[T]
  - register(name: str, item: T, *, overwrite: bool = False) -> None
  - get(name: str) -> T
  - names() -> tuple[str, ...]
  - items() -> tuple[tuple[str, T], ...]
  - __contains__(name: object) -> bool
```

Error types:

- `RegistryError`
- `DuplicateRegistrationError`
- `UnknownRegistrationError`

Design choices:

- Use generic `Registry[T]`.
- Do not use one global mutable registry.
- Let later layers own domain instances such as framework registry or action-head registry.
- Keep registration eager. Lazy import/factory behavior is deferred to a later milestone.
- Config may carry string keys such as `model.registry_key`, but M1 should not instantiate real
  frameworks.

FluxVLA demonstrates why GenesisVLA eventually needs domain registries, but its mmengine-derived
scoped registry is too heavy for M1. Dexbotic's factory-oriented architecture reinforces the same
direction without requiring M1 to implement factories.

Recommended TDD addition beyond the blueprint: add `tests/core/test_registry.py` so F1.4 has direct
coverage.

## 8. Topic F: TDD Test Layout

Recommendation: create the blueprint tests plus small extra tests for F1.2 and F1.4.

Create:

```text
tests/core/__init__.py
tests/core/test_raw_sample.py
tests/core/test_action.py
tests/core/test_registry.py
tests/config/__init__.py
tests/config/test_loader.py
```

Blueprint-required tests:

- `test_should_create_raw_sample_from_legacy_dict`
- `test_should_validate_required_modalities`
- `test_should_reject_invalid_action_shape`
- `test_should_preserve_robot_tag_metadata`
- `test_should_load_yaml_into_experiment_config`
- `test_should_apply_cli_dotlist_override`
- `test_should_emit_clear_error_on_invalid_backend`
- `test_should_export_resolved_yaml`

Recommended extra tests:

- `test_should_validate_action_chunk_shape`
- `test_should_reject_duplicate_registry_key`
- `test_should_raise_clear_error_for_missing_registry_key`

Governance updates required:

- Update `pyrightconfig.genesisvla.json` to include `tests/core` and `tests/config`.
- Update `.pre-commit-config.yaml` path filters to include `tests/core` and `tests/config`.
- Update `Makefile genesis-check` to run Black, Ruff, Pyright, and Pytest on the new test dirs.
- Update `tests/meta/test_repo_policy.py` because it asserts exact `genesis-check` fragments.
- Update `.github/workflows/genesisvla.yml` paths and install command so runtime dependencies are
  available in CI.

## 9. Topic G: Backend Enum / Allowed Values

Recommendation: define backend as runner/training backend, not model backend.

M1 should define a Python 3.10-compatible string enum:

```text
RunnerBackend:
  - local
  - accelerate
  - ddp
  - fsdp
  - deepspeed
```

The local preset should use `local`.

`should_emit_clear_error_on_invalid_backend` should prove that an invalid backend raises a clear
config validation error naming the field and allowed values.

Do not implement any runner backend behavior in M1. Dexbotic's backend resolver shows useful later
behavior such as version detection, FSDP normalization, and warnings, but those require runtime
dependencies and should be deferred.

## 10. Topic H: Dependencies and Tooling

Recommendation: add only runtime dependencies required by M1 code.

Add to `[project].dependencies`:

```text
numpy
omegaconf
```

Do not add:

- torch
- pyyaml
- hydra
- accelerate
- deepspeed
- transformers
- runtime training libraries
- Slurm or distributed dependencies

Because CI currently installs only gate tools, M1 should update
`.github/workflows/genesisvla.yml` to install the package with dev extras, for example:

```text
python -m pip install -e ".[dev]"
```

This lets `make genesis-check` import `numpy` and `omegaconf` in CI without duplicating dependency
lists.

## 11. Topic I: Chinese Docstring Density

Recommendation: apply the M0 coding standard concretely.

M1 code should use:

- Chinese module docstring in every new Python file.
- Chinese class docstring for every public dataclass, protocol, enum, and registry class.
- Chinese function or method docstring for every public function or public method.
- Field-level explanation in class docstrings for public dataclasses, including expected shape and
  dtype where relevant.
- Short Chinese inline comments only for non-obvious validation paths.
- Private helpers may use a short Chinese docstring when they encode schema or coercion logic.

Avoid comments that only restate the line of code.

## 12. Topic J: Frozen vs Mutable Dataclasses

Recommendation: use frozen, slotted dataclasses for M1 value and config objects.

Use:

```text
@dataclass(frozen=True, slots=True)
```

Rationale:

- Contract values should not be mutated after construction.
- CLI override can use replacement/reconstruction instead of mutation.
- Later cache keys and reproducibility records benefit from immutable config objects.
- `slots=True` keeps these objects compact and avoids accidental dynamic attributes.

Important caveat:

- Frozen dataclasses do not deeply freeze numpy arrays or mappings. M1 should document that arrays
  are treated as owned inputs and should not be mutated by consumers. Avoid defensive copying of
  large arrays by default because that would create hidden data movement.

## 13. Topic K: Out of Scope

M1 must not:

- implement models, backbones, processors, action heads, policy runtime, or training loops;
- instantiate real StarVLA, FluxVLA, Dexbotic, or GenesisVLA model families;
- modify `starVLA/`;
- mutate or integrate files from `code-input/`;
- migrate real StarVLA configs;
- add Slurm scripts or submit Slurm jobs;
- add datasets, checkpoints, model paths, run outputs, or robot endpoints;
- add torch as a dependency;
- create deployment, acceleration, checkpoint, or device modules beyond the M1 contract need;
- create global registries that imply supported model families;
- push, create PRs, mark milestone completion, or set `passes: true` during DISCUSS/PLAN/EXECUTE
  gates.

## 14. Worker Coverage Ledger Recommendation

M1 PLAN should include a worker coverage ledger.

Recommended M1 DISCUSS worker posture:

- No read-only exploration worker is required for DISCUSS. Codex Manager inspection is sufficient
  because the stage is read-only, the source archives are registered reference assets, and the
  required design questions are now answered with direct archive evidence.

Recommended M1 EXECUTE worker:

- Worker type: `coding_integration_engineer`
- Count: 1
- Mode: serial
- Rationale: M1 touches shared type contracts, config schema, registry behavior, quality gate files,
  and tests. These are shared contracts and must not be parallelized.

Recommended M1 VERIFY worker:

- Independent read-only worker type: `code_reviewer`
- Scope: review core contracts, registry, config loader, tests, dependency edits, quality gate
  routing, code-input contamination risk, and license/attribution risk.
- Slurm validation worker is not relevant for M1 because no cluster behavior is in scope.

Recommended M1 REVIEW evidence:

- Manager synthesis of EXECUTE and VERIFY evidence.
- Independent code reviewer findings or explicit Claude external review evidence.
- Final `make genesis-check` evidence.
- Path-boundary evidence proving no `starVLA/`, `code-input/`, datasets, runs, checkpoints, Slurm
  configs, or source archives were modified.
- Publication readiness or publication blocker evidence.

Serial-only contracts:

- `genesisvla/core/types/*`
- `genesisvla/core/protocols/*`
- `genesisvla/core/registry/*`
- `genesisvla/config/schema/*`
- `genesisvla/config/loader/*`
- `pyrightconfig.genesisvla.json`
- `.pre-commit-config.yaml`
- `Makefile`
- `pyproject.toml`
- `.github/workflows/genesisvla.yml`
- `tests/meta/test_repo_policy.py`

If VERIFY or REVIEW finds defects, recommend returning to PLAN or a scoped EXECUTE stage. Do not
allow Manager-only implementation fixes for M1 code/config/test behavior.

## 15. Publication Gate Reminder

M1 is not complete after local REVIEW alone.

Per `.agent-docs/git_workflow.md`, completed GenesisVLA milestones require:

- required git scans;
- deliverables committed on a `dev/*` branch;
- branch pushed to the configured remote;
- PR opened or updated;
- PR URL recorded in M1 REVIEW/progress records and provided to Claude/user.

If commit, push, or PR creation is blocked by scans, network, credentials, permissions, or remote
state, the milestone status must be `ready_to_publish_blocked`, not complete.

## 16. Open Questions For Claude

1. Should M1 include the recommended extra tests `tests/core/test_action.py` and
   `tests/core/test_registry.py` so F1.2 and F1.4 have direct TDD coverage beyond the blueprint's
   two named test files?
2. Does Claude approve adding `numpy` and `omegaconf` to top-level `[project].dependencies` as M1
   runtime dependencies?
3. Does Claude approve `genesisvla/config/loader/legacy_omegaconf.py` as the narrow M1 bridge file
   name, while deferring the target-tree `migrate_starvla.py` until actual StarVLA config migration?
4. Does Claude approve one serial `coding_integration_engineer` for M1 EXECUTE and one independent
   read-only `code_reviewer` for M1 VERIFY?

These are not blockers if Claude accepts the recommendations during PLAN kickoff.

## 17. Risks

- Contract overreach: creating too much of the target tree can imply support for model, runner,
  deployment, checkpoint, or acceleration behavior that M1 does not validate.
- Torch dependency creep: importing torch in core contracts would slow basic checks and complicate
  strict typing before model code exists.
- Config schema bloat: mirroring StarVLA, FluxVLA, or Dexbotic runtime YAML in M1 would pull model,
  deployment, and training concerns into the config milestone.
- Weak TDD coverage: the blueprint tests cover RawSample and loader behavior, but not registry or
  ActionChunk directly unless extra tests are approved.
- Dependency declaration gap: CI will fail if M1 code imports `numpy` or `omegaconf` but CI still
  installs only Black, Ruff, Pytest, and Pyright.
- Frozen dataclass shallow immutability: numpy arrays remain mutable even when the dataclass is
  frozen. M1 should document this and avoid hidden copies.
- Pyright strict friction: `numpy.typing` and OmegaConf containers can require careful type
  narrowing.
- Legacy confusion: StarVLA and the staged archives already use OmegaConf, but M1's bridge should
  not be interpreted as supporting full legacy config migration.
- License and attribution risk: FluxVLA and Dexbotic can inform design, but source copying requires
  separate review and attribution. FluxVLA includes upstream-derived files; Dexbotic has a license
  file/classifier mismatch.
- Publication risk: M1 is not complete until scans, commit, push, and PR URL are done or a
  `ready_to_publish_blocked` status records the blocker.

## 18. Recommended PLAN Scope

Recommended create list:

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

Recommended governance updates:

```text
Makefile
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
pyproject.toml
tests/meta/test_repo_policy.py
```

Recommended dependency additions:

```text
[project].dependencies
  - numpy
  - omegaconf
```

Recommended worker coverage ledger:

```text
DISCUSS: no worker; Manager read-only inspection sufficient.
PLAN: Manager drafts plan; no implementation.
EXECUTE: 1x coding_integration_engineer, serial, write-capable, whitelist only.
VERIFY: 1x code_reviewer, read-only, independent review; no Slurm worker.
REVIEW: Manager synthesis plus independent review evidence and publication readiness.
```

Recommended validation target after EXECUTE:

```text
pytest tests/core tests/config -v
pytest tests/meta/test_repo_policy.py -v
pyright -p pyrightconfig.genesisvla.json
make genesis-check
```

`make genesis-check` should be updated to cover:

```text
genesisvla tests/meta tests/core tests/config
```

Recommended publication gate reminder for PLAN:

```text
M1 completion requires git scans, dev/* commit, push, PR URL, and progress records.
If blocked, record ready_to_publish_blocked.
```

## 19. Recommended Next Stage Action

Recommend `start_plan`.

The PLAN should turn the recommendations above into a reviewable implementation sequence with:

- exact worker plan;
- TDD red-green order;
- complete writable whitelist;
- config schema field list;
- registry API contract;
- dependency and CI edits;
- code-input non-copying and attribution guardrails;
- worker coverage ledger;
- publication gate;
- rollback notes;
- validation commands and expected outputs.

## 20. Handoff

```text
===HANDOFF===
Completed:
- Read required governance, blueprint, M0 docs, config, pyproject, M0 policy tests, code-input policy, asset manifest, and git workflow.
- Ran the requested read-only repository investigations for StarVLA config style, OmegaConf usage, dataclasses, tests, pyright scope, M0 docs, and registered archive inventories.
- Inspected FluxVLA-main.zip and dexbotic-main.zip as read-only reference sources without extraction or mutation.
- Recorded FluxVLA and Dexbotic ideas to use now vs. defer, plus license/source-attribution risks.
- Clarified M1 recommendations for Topics A-K.
- Produced recommended M1 PLAN scope, dependencies, governance updates, worker coverage ledger, publication gate reminder, risks, and open questions.

Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- Claude decision on extra F1.2/F1.4 tests beyond the blueprint TDD list.
- Claude decision on runtime dependency additions: numpy and omegaconf.
- Claude decision on naming the narrow OmegaConf bridge file legacy_omegaconf.py.
- Claude decision on M1 worker coverage: 1x coding_integration_engineer for EXECUTE and 1x code_reviewer for VERIFY.

Decisions:
- Recommend no torch dependency or torch imports in M1.
- Recommend numpy-backed M1 arrays and numpy-only tests.
- Recommend narrow OmegaConf bridge, not StarVLA/FluxVLA/Dexbotic config migration.
- Recommend frozen, slotted dataclasses.
- Recommend strict quality-gate expansion to tests/core and tests/config.
- Recommend no code copying from code-input archives during M1.
- Recommend M1 publication gate: scans, dev/* commit, push, PR URL, or ready_to_publish_blocked.

Files Affected:
- .agent-docs/teamwork/reports/M1/DISCUSS.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor.
Next actor: Claude.
===END HANDOFF===
```
