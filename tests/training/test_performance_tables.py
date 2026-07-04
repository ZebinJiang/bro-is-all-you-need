"""训练性能表契约测试。"""

from __future__ import annotations

import csv
import io
import json

import pytest

from autovla.training.performance_tables import (
    PerformanceTable,
    render_csv_table,
    render_markdown_table,
    render_summary_csv,
    stable_json_dumps,
)


def test_performance_table_should_serialize_stably() -> None:
    """验证表格 JSON、CSV 和 Markdown 都是结构化输出。"""
    table = PerformanceTable(
        name="throughput_summary",
        title="Throughput Summary",
        columns=("metric", "value", "unit", "status"),
        rows=(
            {
                "metric": "samples_per_second_mean",
                "value": 533.333333,
                "unit": "samples/s",
                "status": "PASS",
            },
        ),
    )

    payload = table.to_json_dict()
    markdown = render_markdown_table(table)
    csv_payload = render_csv_table(table)

    assert json.loads(stable_json_dumps(payload))["name"] == "throughput_summary"
    assert "| metric | value | unit | status |" in markdown
    assert "samples_per_second_mean" in csv_payload


def test_summary_csv_should_flatten_multiple_tables() -> None:
    """验证 summary CSV 可作为 PR/报告表格数据源。"""
    table = PerformanceTable(
        name="regression_gate",
        title="Regression/Gate",
        columns=("metric", "value", "unit", "status"),
        rows=({"metric": "latency_positive", "value": 7.5, "unit": "ms", "status": "PASS"},),
    )

    rows = list(csv.DictReader(io.StringIO(render_summary_csv((table,)))))

    assert rows == [
        {
            "metric": "latency_positive",
            "row": "1",
            "status": "PASS",
            "table": "regression_gate",
            "unit": "ms",
            "value": "7.5",
        }
    ]


def test_performance_table_should_reject_missing_columns() -> None:
    """验证表格行必须包含所有公开列。"""
    with pytest.raises(ValueError, match="missing columns"):
        PerformanceTable(
            name="bad",
            title="Bad",
            columns=("metric", "value"),
            rows=({"metric": "x"},),
        )
