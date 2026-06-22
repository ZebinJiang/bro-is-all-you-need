#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p \
  assets/input \
  code-input \
  related-assets \
  datasets/readonly datasets/working datasets/cache \
  configs/experiments configs/slurm \
  .agent-docs docs examples runs runs/tmp scripts/sandbox scripts/slurm scripts/data scripts/maintenance tests \
  .agents/instructions .agents/skills .codex/agents

touch \
  assets/input/.gitkeep code-input/.gitkeep related-assets/.gitkeep \
  datasets/readonly/.gitkeep datasets/working/.gitkeep datasets/cache/.gitkeep \
  runs/.gitkeep tests/.gitkeep

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1 "$PYTHON_BIN" -S - <<'PYCODE'
import json
from pathlib import Path

json_paths = [
    Path('configs/project.json'),
    Path('configs/slurm/default_sandbox.json'),
    Path('configs/slurm/debug_profiles.json'),
    Path('configs/experiments/example_experiment.json'),
    Path('.agent-docs/feature_list.json'),
]
for path in json_paths:
    with path.open('r', encoding='utf-8') as file_obj:
        json.load(file_obj)

print('init: required directories and JSON files are present')
PYCODE
