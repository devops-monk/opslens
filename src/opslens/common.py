"""Shared CLI plumbing: console, config options, and one emit() for table / json / csv output."""

from __future__ import annotations

import csv
import io
import json
import sys
from enum import Enum
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from .config import Config, ConfigError, load_config

console = Console()
err_console = Console(stderr=True)
BRAND = "cyan"


class Format(str, Enum):
    table = "table"
    json = "json"
    csv = "csv"


ConfigOpt = Annotated[str | None, typer.Option("--config", "-c", help="Path to opslens.yaml.")]
SetOpt = Annotated[list[str] | None, typer.Option("--set", help="Override a setting: --set steampipe.port=9194 (repeatable).")]
FormatOpt = Annotated[Format, typer.Option("--format", "-f", help="Output format.")]


def err(msg: str, code: int = 1) -> typer.Exit:
    err_console.print(f"[red]error:[/red] {msg}")
    return typer.Exit(code)


def load(config: str | None, sets: list[str] | None) -> tuple[Config, dict[str, str]]:
    try:
        cfg, source = load_config(config, sets)
    except ConfigError as e:
        raise err(str(e), 2) from e
    from . import connections

    connections.activate(cfg.connections)
    return cfg, source


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)


def emit(rows: list[dict[str, Any]], fmt: Format, *, title: str | None = None, columns: list[str] | None = None,
         note: str | None = None) -> None:
    """Render rows as a rich table, JSON, or CSV. Data goes to stdout, notes to stderr (so pipes stay clean)."""
    cols = columns or (list(rows[0]) if rows else [])
    if fmt is Format.json:
        sys.stdout.write(json.dumps(rows, indent=2, default=str) + "\n")
    elif fmt is Format.csv:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow([_cell(r.get(c)) for c in cols])
        sys.stdout.write(buf.getvalue())
    else:
        t = Table(title=title, header_style=f"bold {BRAND}", show_lines=False)
        for c in cols:
            t.add_column(c, overflow="fold")
        for r in rows:
            t.add_row(*[_cell(r.get(c)) for c in cols])
        console.print(t if rows else "[dim]no rows[/dim]")
    if note:
        err_console.print(f"[dim]{note}[/dim]")
