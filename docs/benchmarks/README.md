# AutoVLA Benchmark Dashboards

- [Data Pipeline Backend Bakeoff](DATA_PIPELINE_BACKEND_BAKEOFF.md)

This directory records decision-support dashboards only. The ZJH backend bakeoff
does not authorize real training, model loading, external network use, or dataset
writes.

Current PR #18 state:

- Primary `worker_count=8` WebDataset evidence is now present in the dashboard.
- Backend selection remains `READY_FOR_USER_DECISION_BACKEND`; no winner is
  declared by the dashboard.
- Historical non-primary WebDataset evidence remains context only.
