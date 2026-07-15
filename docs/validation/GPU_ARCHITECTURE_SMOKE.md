# GPU Architecture Smoke

The bounded M8 validation uses YAML/JSON/TOML parse,
focused topology/config/Slurm/package/policy tests, changed-file static checks,
active-surface scans, `git diff --check`, index state, and artifact protection.

The A100 request is rendered with:

```bash
bash scripts/slurm/request_m8_a100_architecture_smoke.sh \
  --target same_node_zero3 --run-id m8-zero3-review
```

Without `--submit`, the wrapper prints the exact existing project-submit
wrapper command and performs no write or scheduler action. Every target uses
partition `a100`, output under `runs/slurm`, canonical local model assets,
offline Hugging Face/Transformers settings, and two bounded training steps.

The request contract declares 8 CPUs per GPU and 64 GiB per GPU using a
per-node Slurm memory request. Native single-GPU/DDP targets require the
project-managed `envs/model-gr00t-n1d6/.venv/bin/python`; ZeRO targets require
`envs/training-deepspeed/.venv/bin/python`. The former composes native training,
GR00T N1D6, and WebDataset; the latter adds DeepSpeed. A missing interpreter is
an actionable Wave 8 preflight failure and never falls back to bare or system
Python. Neither project is a universal model-zoo environment.
Render-only mode never checks or creates that environment. With `--submit`,
the request wrapper resolves the exact worktree interpreter and fails before
calling the project submission wrapper when it is absent, so no known-invalid
allocation reaches `sbatch`.

At runtime the job first verifies the pinned local GR00T asset offline, then
writes `outputs/runtime-launch.json` and `outputs/runtime-result.json`. These
versioned records carry source SHA, topology, selected profile/interpreter,
installed package versions, verified asset identity, exact command and exit
status, plus governed checkpoint/metrics/log paths. Checkpoints stay under
`outputs/checkpoints`, metrics under `logs/metrics.jsonl`, and all paths are
children of `SANDBOX_RUN_DIR`. Distributed launch uses block placement and
kill-on-rank-failure.

The package-version record includes AutoVLA, NumPy, OmegaConf, Torch,
Transformers, safetensors, Hugging Face Hub, WebDataset, and DeepSpeed. This
completes the declared environment fingerprint inputs without treating a
missing package as installed; absent distributions are recorded as
`not-installed`.

Jobs `3163` and `3167` were submitted as bounded single-GPU attempts. Job `3163`
exposed a sparse-YAML override ordering defect and did not prove runtime; the
defect was repaired before the bounded rerun. Job `3167` received one A100,
validated configuration and the official local asset, then stopped at
`UnsupportedOfficialRelativeStatisticsError`: official relative-action
statistics are shaped `[T,D]`, while the accepted processor path is currently
one-dimensional. The stop occurred before CUDA model/tensor allocation,
forward, loss, backward, optimizer step, metrics, or checkpoint.

The two runtime `uv.lock` files and bounded environment fingerprints were
collected, as recorded in `envs/PROFILE_MATRIX.md`. They establish dependency
identity, not runtime success. No single-GPU, DDP, DeepSpeed ZeRO 1/2/3,
checkpoint, parity, performance, model-quality, or long-training completion is
claimed. The remaining runtime matrix is deferred, and `NO_BACKEND_WINNER`
remains unchanged.
