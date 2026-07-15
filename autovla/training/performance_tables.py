"""兼容导出 Core 层稳定结构化报告对象。"""

from autovla.core.reporting import (
    JsonScalar,
    PerformanceTable,
    render_csv_table,
    render_markdown_report,
    render_markdown_table,
    render_summary_csv,
    stable_json_dumps,
)

__all__ = [
    "JsonScalar",
    "PerformanceTable",
    "render_csv_table",
    "render_markdown_report",
    "render_markdown_table",
    "render_summary_csv",
    "stable_json_dumps",
]
