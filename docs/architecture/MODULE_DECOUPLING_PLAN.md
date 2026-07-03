# Module Decoupling Plan

AutoVLA modules should accumulate explicit `MODULE.md` contracts so future
agents can extend behavior without blending data, model, training, and runtime
concerns.

## First-class Modules

- `autovla.dataloader`
- `autovla.training`
- `autovla.models`
- `autovla.config`
- `autovla.evaluation`
- `autovla.deployment`
- `scripts/env`
- `configs/env`
- `configs/finetune`

## Rules

- Document public contracts before broadening behavior.
- Keep model-specific logic behind model adapters and env profiles.
- Keep data-format logic behind backend/profile boundaries.
- Prefer additive adapters over protected baseline edits.
- Do not claim fine-tune or model-runtime readiness without exact env profile,
  asset, and validation evidence.
