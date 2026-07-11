"""Table and JSON output formatting for wxcc-flow."""
import json
import re
from typing import Any, List, Tuple

from rich.console import Console
from rich.table import Table

console = Console()


def format_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def print_json(data: Any) -> None:
    print(format_json(data))


def print_table(data: List[dict], columns: List[Tuple[str, str]], limit: int = 50) -> None:
    """Print data as a Rich table.

    columns: list of (header, accessor_key) tuples.
    accessor_key supports dot notation for nested dicts.
    """
    items = data[:limit] if limit > 0 else data

    if items and not any(_resolve(items[0], acc) for _, acc in columns):
        columns = _auto_columns(items[0])

    table = Table(show_header=True, header_style="bold")
    for header, _ in columns:
        table.add_column(header)

    for item in items:
        row = []
        for _, acc in columns:
            val = _resolve(item, acc)
            row.append(str(val) if val is not None else "")
        table.add_row(*row)

    if limit > 0 and len(data) > limit:
        table.add_row(*[f"... {len(data) - limit} more" if i == 0 else "" for i in range(len(columns))])

    console.print(table)


def _resolve(obj: dict, accessor: str) -> Any:
    if not accessor:
        return obj
    parts = accessor.split(".")
    val = obj
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def _auto_columns(item: dict) -> List[Tuple[str, str]]:
    cols = []
    for key, val in item.items():
        if isinstance(val, (dict, list)):
            continue
        header = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', key)
        header = header[0].upper() + header[1:]
        cols.append((header, key))
    return cols if cols else [("Value", "")]
