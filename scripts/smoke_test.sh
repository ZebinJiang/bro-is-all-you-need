#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONDONTWRITEBYTECODE=1

bash scripts/init.sh

PYTHONNOUSERSITE=1 "$PYTHON_BIN" -S - <<'PYCODE'
import json
from pathlib import Path

required = [
    'AGENTS.md',
    'boundaries.txt',
    '.agent-docs/asset_manifest.md',
    '.agent-docs/feature_list.json',
    '.agent-docs/governance_overview_zh.md',
    '.agent-docs/progress.txt',
    '.agent-docs/review.txt',
    '.agent-docs/slurm_sandbox_policy.md',
    '.agent-docs/slurm_environment_discovery.md',
    '.agent-docs/config_contracts.md',
    '.agent-docs/execution_contract.md',
    '.agent-docs/implementation_blueprint.md',
    '.agent-docs/git_workflow.md',
    '.agent-docs/dataset_policy.md',
    '.agent-docs/external_path_transfer_policy.md',
    '.agent-docs/cleanup_policy.md',
    '.agent-docs/daily_task_workflow.md',
    '.agent-docs/repository_layout_policy.md',
    '.agent-docs/code_input_integration.md',
    '.agent-docs/related_assets_workflow.md',
    '.agent-docs/sandbox_validation.md',
    '.agent-docs/agent_skills/integrate-starvla-dataset/assets/templates/data_config.py',
    '.agent-docs/agent_skills/integrate-starvla-dataset/assets/templates/modality.json',
    '.agent-docs/agent_skills/integrate-starvla-dataset/assets/templates/training_config.yaml',
    '.agent-docs/agent_skills/integrate-starvla-dataset/assets/templates/run_train.sh',
    '.agent-docs/agent_skills/integrate-starvla-dataset/assets/templates/model2bench_interface.py',
    'scripts/slurm/submit_sandbox_job.sh',
    'scripts/slurm/request_compute_debug.sh',
    'scripts/slurm/discover_slurm_environment.py',
    'scripts/slurm/template_job.sbatch',
    'scripts/data/transfer_explicit_path.sh',
    'scripts/maintenance/generate_cleanup_proposal.py',
    'scripts/maintenance/delete_from_cleanup_manifest.py',
    'examples/mock_genesisvla_task.py',
    '.agents/skills/feature-dev/SKILL.md',
    '.agents/skills/code-input-integration/SKILL.md',
    '.agents/skills/related-assets-planning/SKILL.md',
    '.agents/skills/daily-task-planning/SKILL.md',
    '.agents/skills/cleanup-proposal/SKILL.md',
    '.agents/skills/explicit-path-transfer/SKILL.md',
    '.agents/skills/slurm-environment-discovery/SKILL.md',
]
missing = [path for path in required if not Path(path).exists()]
if missing:
    raise SystemExit(f'missing required files: {missing}')

for path in [
    Path('configs/project.json'),
    Path('configs/slurm/default_sandbox.json'),
    Path('configs/slurm/debug_profiles.json'),
    Path('configs/experiments/example_experiment.json'),
    Path('.agent-docs/feature_list.json'),
]:
    with path.open('r', encoding='utf-8') as file_obj:
        json.load(file_obj)

for path in [
    Path('scripts/slurm/discover_slurm_environment.py'),
    Path('scripts/maintenance/generate_cleanup_proposal.py'),
    Path('scripts/maintenance/delete_from_cleanup_manifest.py'),
]:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
print('smoke: JSON, required files, and Python syntax validated')
PYCODE

RUN_ID="smoke-local-$(date -u +%Y%m%d%H%M%S)"
scripts/sandbox/run_local_sandbox.sh --run-id "$RUN_ID" -- \
  "$PYTHON_BIN" -S examples/mock_genesisvla_task.py \
    --config configs/experiments/example_experiment.json \
    --output "$ROOT_DIR/runs/local/$RUN_ID/outputs/mock_result.json"

test -s "$ROOT_DIR/runs/local/$RUN_ID/outputs/mock_result.json"

scripts/slurm/submit_sandbox_job.sh \
  --config configs/slurm/default_sandbox.json \
  --experiment-config configs/experiments/example_experiment.json \
  --job-script scripts/slurm/template_job.sbatch \
  --run-id genesisvla-smoke-slurm-dry-run \
  --dry-run > "$ROOT_DIR/runs/local/$RUN_ID/logs/slurm_dry_run.txt"

grep -q "DRY RUN" "$ROOT_DIR/runs/local/$RUN_ID/logs/slurm_dry_run.txt"
grep -q "sbatch" "$ROOT_DIR/runs/local/$RUN_ID/logs/slurm_dry_run.txt"
grep -q "needs_discovery=1" "$ROOT_DIR/runs/local/$RUN_ID/logs/slurm_dry_run.txt"

scripts/slurm/request_compute_debug.sh \
  --profile h800-gpu \
  --run-id genesisvla-smoke-debug-dry-run \
  --dry-run > "$ROOT_DIR/runs/local/$RUN_ID/logs/srun_debug_dry_run.txt"

grep -q "DRY RUN" "$ROOT_DIR/runs/local/$RUN_ID/logs/srun_debug_dry_run.txt"
grep -q "srun" "$ROOT_DIR/runs/local/$RUN_ID/logs/srun_debug_dry_run.txt"
grep -q "h800" "$ROOT_DIR/runs/local/$RUN_ID/logs/srun_debug_dry_run.txt"

echo "smoke: passed"
