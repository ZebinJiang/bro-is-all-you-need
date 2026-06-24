# Summary

Publishes GenesisVLA M1 local acceptance for core contracts and typed config.

- M1-F1: RawSample, BatchSample, ModelInput, FrameworkOutput, ActionChunk, ActionMask, and ActionSpace.
- M1-F2: FrameworkProtocol, RunnerProtocol, and PolicyProtocol.
- M1-F3: typed registry, dataclass config schema, OmegaConf legacy bridge, and resolved config export.
- M1-T: Codex-only Manager / persistent Owner thread governance and bootstrap evidence.

# Quality Evidence

- Project-local wrapper: `bash scripts/quality/genesis_check_project_local.sh`.
- Expected gate result for publication: py_compile PASS, pytest PASS, Black PASS, Ruff PASS, and Pyright PASS.
- Quality pre-commit review is recorded under `coordination/reports/GVLA-M1-PUBLISH-001B/owner-quality-precommit.md`.

# Publication Scope

Governance assets are intentionally included by explicit user decision, including `.agent-docs/**`, `.agents/**`, Teamwork history, governance policies, support scripts/configs, the GenesisVLA blueprint roadmap HTML, skill overlays, and the smoke example when scans pass.

# DevSpace MCP Compliance

DevSpace MCP is not used as project-internal Manager, Owner, or subagent workflow evidence. References to DevSpace MCP in the repository are prohibition or compliance text only.

# Merge

No merge is requested by this publication task.
