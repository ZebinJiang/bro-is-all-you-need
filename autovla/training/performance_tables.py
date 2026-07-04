"""训练 benchmark 结构化性能表契约。"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

JsonScalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class PerformanceTable:
    """表示一个可序列化为 JSON、CSV 和 Markdown 的性能表。"""

    name: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, JsonScalar], ...]

    def __post_init__(self) -> None:
        """校验表名、列名和行字段保持稳定。"""
        if not self.name.strip():
            raise ValueError("table name must not be empty")
        if not self.title.strip():
            raise ValueError("table title must not be empty")
        if not self.columns:
            raise ValueError("table columns must not be empty")
        for column in self.columns:
            if not column.strip():
                raise ValueError("table column must not be empty")
        for row in self.rows:
            missing = [column for column in self.columns if column not in row]
            if missing:
                raise ValueError(f"table {self.name} row is missing columns: {missing}")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "columns": list(self.columns),
            "name": self.name,
            "rows": [{column: row[column] for column in self.columns} for row in self.rows],
            "title": self.title,
        }


def stable_json_dumps(payload: Mapping[str, object] | Sequence[object]) -> str:
    """序列化稳定 JSON 文本, 供报告产物和测试比较。"""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_markdown_table(table: PerformanceTable) -> str:
    """将单个性能表渲染为 Markdown 表格。"""
    header = "| " + " | ".join(table.columns) + " |"
    separator = "| " + " | ".join("---" for _ in table.columns) + " |"
    lines = [f"## {table.title}", "", header, separator]
    for row in table.rows:
        values = [str(row[column]) for column in table.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def render_markdown_report(tables: Iterable[PerformanceTable]) -> str:
    """渲染包含多个性能表的 Markdown 报告。"""
    rendered = [render_markdown_table(table).rstrip() for table in tables]
    return "\n\n".join(rendered) + "\n"


def render_csv_table(table: PerformanceTable) -> str:
    """将单个性能表渲染为 CSV。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(table.columns), lineterminator="\n")
    writer.writeheader()
    for row in table.rows:
        writer.writerow({column: row[column] for column in table.columns})
    return buffer.getvalue()


def render_summary_csv(tables: Iterable[PerformanceTable]) -> str:
    """将所有性能表扁平化为通用 summary CSV。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["table", "row", "metric", "value", "unit", "status"],
        lineterminator="\n",
    )
    writer.writeheader()
    for table in tables:
        for index, row in enumerate(table.rows, start=1):
            metric = str(row.get("metric", row.get("name", table.name)))
            writer.writerow(
                {
                    "metric": metric,
                    "row": index,
                    "status": row.get("status", ""),
                    "table": table.name,
                    "unit": row.get("unit", ""),
                    "value": row.get("value", row.get("status", "")),
                }
            )
    return buffer.getvalue()
