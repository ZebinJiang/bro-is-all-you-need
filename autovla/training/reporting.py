"""训练性能表报告的窄导出入口。"""

from __future__ import annotations

from autovla.training.benchmark import TrainingBenchmarkResult


def benchmark_result_to_pr_table(result: TrainingBenchmarkResult) -> str:
    """生成可放入 PR body 或 Manager summary 的 Markdown 表格片段。"""
    throughput = result.tables["throughput_summary"]
    gate = result.tables["regression_gate"]
    return (
        "### Throughput Summary\n\n"
        f"{throughput.to_json_dict()}\n\n"
        "### Regression/Gate\n\n"
        f"{gate.to_json_dict()}\n"
    )
