# Family Runtime Profiles

M11 uses isolated uv projects for `gr00t_n1d6_runtime`, `gr00t_n1d7_runtime`, `pi0_5_runtime`,
and the non-training `pi0_5_conversion` profile. Listing and inspection are metadata-only.

The N1.6 family contract requires Torch `2.7.1`. The preserved `uv.lock` resolves Torch `2.6.0`;
its SHA256 remains recorded for audit, but `runtime_lock_accepted` is false and environment
creation fails closed. An offline lock refresh was attempted but the project-local cache lacked
the pinned build dependency, so no replacement lock was fabricated. The family-specific model
extra now pins Torch `2.7.1`; the N1.6 env no longer combines it with the generic training extra.

N1.7, Pi0.5 runtime, and Pi0.5 conversion have no accepted lock and no asserted exact package
set. Their license or conversion blockers remain visible in `list`, `inspect`, and `verify`.
Pi0.5 production runtime prohibits JAX, Flax and Orbax; those packages may only belong to a later
authorized conversion environment.
