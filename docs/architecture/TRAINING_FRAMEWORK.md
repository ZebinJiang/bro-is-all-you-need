# AutoVLA Training Framework

## M8 Active Architecture

Production training is GPU-only on the tracked A100 profile. The active
strategies are `single_gpu`, `distributed_data_parallel`, and `deepspeed` with
ZeRO stage 1, 2, or 3. DDP and DeepSpeed use NCCL and BF16. CPU/NVMe offload,
FSDP/FSDP2, CPU model runtime, and a universal environment are not active
surfaces.

`autovla.cli.train` composes one typed path:

```text
layered ExperimentConfig -> TrainingStrategy -> TrainingTopology
  -> Data-owned PartitionContext -> DataModule -> PreparedTrainingSession
  -> TrainingEngine -> checkpoint and telemetry
```

The engine has no strategy-name branch. It projects topology facts into the
Data-owned type; data backends do not import Training or DeepSpeed and do not
select behavior by strategy. Backend choice remains explicit and the decision
is `NO_BACKEND_WINNER`.

The deterministic global batch formula is:

```text
data.loader.batch_size * training.gradient_accumulation_steps
  * training.distributed.world_size
```

DeepSpeed emits the same value as `train_batch_size` from its typed config.

## Dependencies And Status

DeepSpeed `0.19.2` exists only in `training-deepspeed`. Asset acquisition uses
the separate manual `asset-acquisition` profile. Training imports do not depend
on `huggingface_hub` and use existing local files only. Both runtime projects
have collected `uv.lock` files. Their lock SHA256/environment fingerprints are
`41f807307ba96a00313b4e7af1bb584db5df42dfbe877eca09082dab60f5d662` /
`5df3999ddac39595f698abee3c70451e337fb7fbd10fcd04a59eeec7274c81cb`
for `model-gr00t-n1d6`, and
`bdf9307e768bd3d78488900580f98971b6c22180a8bb6a2eb84b9fb6435f8ceb` /
`73ad2dc4a08abf27fe4cbb7568c4326cb558a1a22745ed62fb55feb65adb2a0d`
for `training-deepspeed`.

M8 is an architecture Draft. Job `3163` found a sparse-override ordering defect
that was repaired. Job `3167` received one A100 and verified configuration plus
the official local asset, then stopped at the unsupported official `[T,D]`
relative-action-statistics boundary before CUDA model/tensor allocation. It did
not reach forward, loss, backward, optimizer step, metrics, or checkpoint. No
successful single-GPU, DDP, DeepSpeed, checkpoint parity, throughput, model
quality, or deployment result is claimed; the remaining matrix is deferred.
