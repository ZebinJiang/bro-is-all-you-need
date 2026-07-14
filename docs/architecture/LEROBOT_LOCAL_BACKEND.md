# LeRobot Local Backend

`lerobot_local` is a local-format integration, not a LeRobot package dependency.
It loads metadata once, groups parquet reads, enforces root containment, and
expands temporal queries within episode boundaries. Live handles are excluded
from serialization. Select it with `data.datasets[].backend: lerobot_local` and
install `data-lerobot` for the local PyArrow/Pillow route. Workers=0 bounded
evidence covers grouped reads and cache counters. PyAV media materialization,
workers=2 backend-matrix execution, and general temporal/media compatibility
remain deferred. `NO_BACKEND_WINNER` remains literal.
