# M2 Tiny Fixtures

These fixtures are generated, deterministic, CPU-only GenesisVLA test assets.
They do not download external data and do not reuse upstream dataset files.

## Provenance

- Source: generated inside GenesisVLA.
- License: project-generated under the repository license.
- Runtime dependency: PyArrow only inside fixture helpers/tests for generated
  parquet evidence.
- External downloads: none.
- Large binaries: none.

## Contents

- `tiny_lerobot_fixture(root)` writes a generated LeRobot v3-like directory
  under the caller-provided path and reloads two `RawSample` records with image,
  state, actions, language, `robot_tag`, padding, action masks, and source
  provenance. The target format is LeRobotDataset v3.0 at upstream revision
  `1396b9fab7aecddd10006c33c47a487ffdcb54b4` / tag `v0.5.1`.
- `tiny_parquet_fixture(path)` writes a generated standalone parquet file with
  state/action/action_mask fixed-size-list columns and reloads the same
  two-sample RawSample adapter representation.
- `load_tiny_lerobot_fixture(root)` and `load_tiny_parquet_fixture(path)` verify
  schema, row counts, null policy, metadata/data relationships, and deterministic
  reload behavior.
- `generate_tiny_fixtures.py` can materialize generated fixture files and JSON
  metadata for review under an explicitly provided output directory.

The fixtures are intentionally too small for model quality evaluation. They are
only acceptance evidence for M2 transform/data contract behavior.
