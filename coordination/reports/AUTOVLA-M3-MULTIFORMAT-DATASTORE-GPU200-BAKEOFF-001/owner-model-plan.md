# Owner Model Plan

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## Evidence Reviewed

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-packets/model-plan.md`
- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`
- `autovla/models/contracts.py`
- `autovla/models/family.py`
- `autovla/models/registry.py`
- `autovla/models/MODULE.md`
- `autovla/models/gr00t/metadata.py`
- `autovla/models/gr00t/batch_adapter.py`
- `autovla/models/gr00t_n1d6/adapter.py`
- `autovla/models/gr00t_n1d6/MODULE.md`
- `autovla/training/local_runner.py`
- `autovla/training/checkpointing.py`
- `autovla/training/run_manifest.py`
- `autovla/training/baseline_metrics.py`

## Model Boundary Assessment

Current Model-side contracts support planning approval for a bounded GPU200 telemetry tranche, because the reviewed GR00T surfaces remain metadata-only and fail closed:

- `autovla/models/gr00t_n1d6/adapter.py` declares `support_status="unavailable_missing_assets"` and leaves `checkpoint_uri`, `checkpoint_checksum`, and governed runtime assets unset by default.
- `ModelZooEntry.require_runtime_assets()` in `autovla/models/contracts.py` raises `ModelAssetsUnavailableError` unless governed source/checkpoint metadata is complete.
- `ModelFamilySpec` in `autovla/models/family.py` enforces `no_weight_load=True`, `no_tokenizer_load=True`, `no_network=True`, and `no_checkpoint_download=True`.
- `Gr00tN1D6DryRunBatchAdapter` in `autovla/models/gr00t/batch_adapter.py` converts batch metadata only and explicitly avoids importing GR00T, `torch`, `transformers`, tokenizer runtime, or checkpoint runtime.

This means the current baseline is safe for a planning gate as long as the bakeoff keeps GR00T handling on the metadata/manifest side and does not treat a 200-step bounded telemetry run as proof of real model support.

## Local Checkpoint And Model-Path Governance

The acceptable planning shape is:

- local-only path references are allowed as governed metadata;
- checkpoint/source provenance stays explicit and offline;
- no implicit checkpoint discovery, cache probing, remote fallback, or download occurs;
- no login-node tokenizer/processor/model construction occurs;
- compute-node telemetry remains bounded to the authorized 200-step run and still does not overclaim model compatibility.

Model considers the following local-only/offline actions acceptable within this planning boundary:

- recording a local checkpoint or source path as opaque metadata in a governed config or ignored evidence artifact;
- validating that a required local path was explicitly supplied by the task/user rather than auto-discovered;
- reading JSON manifest-style metadata that describes a local checkpoint/source asset without reading model weights;
- carrying `model_registry_key="gr00t-n1d6"` through config, manifest, and telemetry summaries as metadata only.

The following remain outside the approved boundary for this plan:

- loading checkpoint weights;
- constructing or reading a tokenizer or processor runtime;
- importing upstream GR00T runtime as part of metadata lookup or telemetry planning;
- auto-probing local caches or alternate directories to find a model path;
- claiming that a successful 200-step telemetry run proves GR00T checkpoint compatibility, model correctness, or fine-tune readiness.

## READY_FOR_USER_DECISION_MODEL_CHECKPOINT Trigger

Escalate to `READY_FOR_USER_DECISION_MODEL_CHECKPOINT` if any implementation step requires one or more of the following:

- a real GR00T checkpoint compatibility claim beyond metadata-only/local-manifest evidence;
- reading or validating actual checkpoint weight contents rather than governed metadata;
- tokenizer or processor file reads that go beyond passive path/provenance recording;
- model source/runtime import that is not already covered by the metadata-only skeleton;
- ambiguous checkpoint provenance, incomplete local asset governance, missing license/model-card status, or unclear user authorization for which local checkpoint should be treated as the bounded telemetry candidate;
- any fallback from local-only/offline behavior toward Hugging Face, network resolution, or download.

## 200-Step Telemetry Claim Boundary

The 200-step GPU200 run may support only these claims:

- the candidate datastore plus bounded GR00T telemetry path was runnable under the governed test envelope;
- the run produced bounded telemetry for throughput, timing, and missing-signal analysis;
- the evidence is suitable for datastore comparison and next-step planning.

The 200-step run must not be described as:

- model compatibility validation;
- checkpoint compatibility validation;
- tokenizer/processor validation;
- training readiness;
- fine-tune readiness;
- deployment or inference readiness.

README/docs/report language should keep this as bounded decision-support telemetry only.

## Recommendation

Model approves planning to proceed under the existing fail-closed skeleton and offline-local governance assumptions. The implementation should preserve these rules:

- keep GR00T registry lookup and adapter imports metadata-only;
- keep checkpoint handling on explicit local metadata/manifests unless a later checkpoint decision is raised;
- keep tokenizer/processor/model runtime out of the bakeoff path;
- keep telemetry outputs framed as bounded datastore evidence, not model support evidence.

## DevSpace MCP Compliance

- DevSpace MCP used: no

## Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

APPROVE
