# Data Mixing and Balancing

`DatasetMixturePlan` and `BatchCompositionPolicy` are intentionally distinct.

```text
DatasetMixturePlan                 BatchCompositionPolicy
  source draw weights               batch dataset/embodiment quotas
  fixed / size / temperature        minimum / maximum contribution
  scheduled curriculum              exhaustion fallback
  replacement / finite behavior     drop-last / accumulation identity
  caps and rank-worker replay        global-batch-index consistency
  source cursors/counts              committed batch counts
```

Both contracts are immutable, JSON-safe, fingerprinted, and checkpointable.
Mixture selection hashes the plan fingerprint with step, global position, rank,
and worker. A component reaching its cap is excluded; with
`replacement=false`, declared dataset size is also an exhaustion boundary.
`stop`, `renormalize`, and `cycle` are explicit finite-source policies. Scheduled
weights require an ordered step-zero schedule containing every component.

Batch targets can be dataset- or embodiment-based. Bounds must still permit the
requested batch size. Quotas use a stable global batch index so ranks derive the
same composition. The policy records drop-last, accumulation, provenance, and
the next committed batch identity; it does not hide composition inside a
training script.

`DataTelemetryRecord` covers samples/batches by dataset and embodiment,
requested/effective weights, deviations, skip reasons, data wait, optional
decode/collate time, valid image/token/action elements, rank/reduction identity,
and source/transform fingerprints. These are architecture metrics, not a
benchmark. VLA Foundry and FluxVLA were references only; no sampler code was
copied and no backend was selected. `NO_BACKEND_WINNER`.
