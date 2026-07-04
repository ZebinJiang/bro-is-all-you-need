# Why Not Wholesale Upstream Repos

## StarVLA

Use modular family decomposition and pluggable backbone/action-head/trainer/dataset ideas. Do not adopt wholesale because AutoVLA needs governed training infrastructure, lightweight registry lookup, env fail-closed gates, and telemetry-first contracts.

## Dexbotic

Use registry/factory organization, layered config, and dataset/model/action-head separation ideas. Do not adopt wholesale because its broad toolbox and experiment scripts should not become the AutoVLA training spine.

## FluxVLA

Use standardized interfaces, module decoupling, and deployability-aware naming. Do not adopt wholesale because the full data-to-real-device deployment loop is outside this task.

## VLA Foundry

Use training-stack decomposition, WebDataset/FSDP2/dataset mixing, batch balancing, and telemetry ideas. Do not adopt wholesale because AutoVLA must keep backend, family, and runtime choices pluggable.

## GR00T

Use family metadata, action chunk schema, modality/embodiment boundaries, and future runtime gate ideas. Do not adopt wholesale because code license and model-weight license differ, and metadata lookup must not load runtime or checkpoint assets.

## OpenPI / π

Use roadmap metadata, adapter boundary ideas, normalization-stat policy, and action-head considerations. Do not adopt wholesale because JAX/Flax runtime must not leak into AutoVLA core.

## LeRobot

Use dataset conventions and episode/sample format ideas. Do not adopt wholesale because LeRobot trainer is not the AutoVLA training spine and model-family contracts must remain independent.

## WebDataset

Use high-throughput shard IO and streaming backend patterns. Do not adopt as the only core because not every family/backend should force a tar-shard design and backend selection must remain telemetry driven.

## Qwen / Qwen-VL

Use sample-format discipline and preprocessing structure. Do not adopt wholesale because chat/LLM formatting does not directly define robotics action schema or action-head semantics.
