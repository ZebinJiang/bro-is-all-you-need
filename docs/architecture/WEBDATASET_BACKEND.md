# WebDataset Backend

The `webdataset` route integrates WebDataset `1.0.2` for local tar streaming.
AutoVLA partitions shard identities once and disables upstream node/worker
splitters. Production code never restarts a stream for integer random access.
URL-like shards and network fallback are rejected. Runtime evidence remains
bounded to finite workers=0 traversal and backend cursor/handler tests; the
post-repair workers=2 backend matrix was not rerun. Select this route with
`data.datasets[].backend: webdataset` and install `data-webdataset` when the
public package is required. No throughput or production claim follows.
`NO_BACKEND_WINNER` remains in force.
