# DataLoader Performance Table Scaffold

This Stage 3 scaffold adds a synthetic-only DataLoader performance table path for
future ZJH, LeRobot, WebDataset, and Robo-DM benchmark comparisons.

The current contract is intentionally narrow:

- backend: `synthetic`
- fixture: `tiny`
- output formats: JSON, CSV, Markdown
- no real dataset read
- no media decode
- no full dataset conversion
- no real training
- no GPU, Slurm, W&B, Hugging Face, endpoint, or robot action

The scaffold reuses the Stage 2 `PerformanceTable` schema and emits seven tables:
Benchmark Matrix, Throughput Summary, Stage Latency, Data/IO Summary,
Regression/Gate, Missing Telemetry, and Environment.
