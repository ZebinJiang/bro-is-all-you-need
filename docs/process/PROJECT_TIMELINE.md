# AutoVLA Project Timeline

This timeline summarizes mainline process decisions after M3 data-format
publication. It is intentionally concise; detailed task evidence remains under
the task-specific `runs/tmp/**` archives.

| Area | Summary | Evidence |
| --- | --- | --- |
| Governance loop v2 | Installed prompt-controlled loop governance, Owner runtime memory, fail-closed dispatch, and `thinking: "xhigh"` mapping. | PR #6 through PR #8 governance series. |
| Owner topology/runtime smoke | Owner threads were validated, and Data Owner recovery was preserved as a process-archive seed rather than root-local active truth. | `GVLA-DATA-OWNER-THREAD-RECOVERY-001`, root dirty disposition bundle. |
| AutoVLA rename | Active project identity moved from GenesisVLA wording to AutoVLA while preserving StarVLA as upstream attribution context. | Governance and README history. |
| M3 runner readiness | Local runner, config/CLI scaffold, and local smoke execution created bounded dry-run paths without real training. | PR #4, PR #5, PR #6. |
| CPU microloop | CPU-only microloop evidence was merged without GPU, Slurm, model loading, or checkpoint loading. | PR #11. |
| Slurm harness | Slurm harness governance exists for future compute routing; no compute job is launched by this archive. | M3 Slurm harness branch/report history. |
| ZJH adapter / GR00T-N1.6 readiness | GR00T/ZJH readiness is tracked as a governed future path, not an active fine-tune. | PR #13 and readiness reports. |
| DataLoader perf harness | Data format and backend evidence is decision support only until a later telemetry run selects a training path. | PR #14, PR #16. |
| Training Store experiments | PR #16 remains an open draft backend research artifact with WebDataset streaming evidence and a performance-negative comparator. | [PR #16](https://github.com/ZebinJiang/bro-is-all-you-need/pull/16). |
| Data-format decisions | PR #18, PR #19, and PR #20 installed dashboard, native timing, and data format pipeline suite records. | Data-format benchmark docs and PR merge commits. |
| Root dirty disposition | Root-local governance, report, and active coordination residue was preserved, explicitly cleared, and root was synced to PR #20 main. | `AUTOVLA-M3-ROOT-ACTIVE-STATE-DISPOSITION-AND-SYNC-001`. |

## Next Mainline Direction

The next architecture work should introduce a uv-managed environment matrix,
fine-tune config environment selectors, and module boundary docs before any
GR00T-N1.6 telemetry dry-run or training attempt.
