# Inference and Deployment Boundaries

`autovla.inference` owns `InferenceRequest`, `InferenceResult`,
`InferenceSession`, `PolicyBundle`, and `PolicyBundleManifest`.
`autovla.deployment` owns `DeploymentSpec`, `DeploymentHook`, `ExportManifest`,
and `RuntimeCompatibilityReport` only.

```text
canonical TrainingBatch
  -> same family processor + shared R3 TransformPlan
  -> local InferenceSession protocol
  -> same inverse action transform
  -> physical [B,H,D] InferenceResult
```

A policy-bundle manifest references family config, verified asset/checkpoint
manifest, processor/transform, capability, action-decode, device/precision,
provenance, and optional local hook identities. `PolicyBundle` stores absolute
local references; it does not copy weights or assets into Git or run outputs.
The old `autovla.deployment.policy.InferencePolicy` is an identity alias to the
canonical session protocol, not a second predictor implementation.

Deployment contracts only describe a local CUDA compatibility check and a
manifest reference. Target names containing server, robot, endpoint, remote,
or ROS semantics fail closed. There is no server, evaluator, robot/device loop,
transport, remote service, action-emitting client, real inference execution,
weight copy, or asset copy in M9.

FluxVLA and StarVLA informed module separation and naming only. No serving or
operator code was copied, and runtime compatibility remains deferred.
