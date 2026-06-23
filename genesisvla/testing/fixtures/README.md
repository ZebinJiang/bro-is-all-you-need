# M2 Tiny Fixtures

These fixtures are generated, deterministic, CPU-only GenesisVLA test assets.
They do not download external data and do not reuse upstream dataset files.

## Provenance

- Source: generated inside GenesisVLA.
- License: project-generated under the repository license.
- Runtime dependency: none.
- External downloads: none.
- Large binaries: none.

## Contents

- `tiny_lerobot_fixture()` returns two in-memory `RawSample` records with
  image, state, actions, language, `robot_tag`, padding, and action mask cases.
- `tiny_parquet_fixture()` returns two Parquet-like in-memory records for data
  contract tests. It does not require `pyarrow` or a real parquet backend.
- `generate_tiny_fixtures.py` can materialize JSON metadata for review under an
  explicitly provided output directory.

The fixtures are intentionally too small for model quality evaluation. They are
only acceptance evidence for M2 transform/data contract behavior.
