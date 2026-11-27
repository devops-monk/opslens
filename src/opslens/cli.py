"""opslens command-line entry point (Phase 1: catalogs and the no-AI CLI)."""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__
from .catalog import pipelines as pcat
from .catalog import search as csearch
from .catalog import tables as tcat
from .common import (
    BRAND,
    ConfigOpt,
    Format,
    FormatOpt,
    SetOpt,
    console,
    emit,
    err,
    err_console,
    load,
)
from .config import param_rows, template_text
from .sql import client, guard

app = typer.Typer(
    name="opslens",
    help="Plain-English ops requirements to reviewable Flowpipe pipelines. Find the data (Steampipe tables) and the "
         "actions (Flowpipe pipelines), query read-only, and keep everything inspectable. Works without AI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
find_app = typer.Typer(help="Search the catalogs (offline, no AI).", no_args_is_help=True)
describe_app = typer.Typer(help="Show a table's or a pipeline's full interface.", no_args_is_help=True)
catalog_app = typer.Typer(help="Inspect and verify the shipped catalogs.", no_args_is_help=True)
app.add_typer(find_app, name="find")
app.add_typer(describe_app, name="describe")
app.add_typer(catalog_app, name="catalog")


def _version_cb(value: bool) -> None:
    if value:
        typer.echo(f"opslens {__version__}")
        raise typer.Exit()


@app.callback()
def main(version: Annotated[bool, typer.Option("--version", callback=_version_cb, is_eager=True,
                                                help="Show the version and exit.")] = False) -> None:
    pass


class Source(str, Enum):
    live = "live"
    demo = "demo"


# ------------------------------------------------------------------ setup


@app.command()
def init(force: Annotated[bool, typer.Option("--force", help="Overwrite an existing opslens.yaml.")] = False,
         out: Annotated[Path, typer.Option("--out", help="Where to write it.")] = Path("opslens.yaml")) -> None:
    """Write a commented opslens.yaml with every setting at its default."""
    if out.exists() and not force:
        raise err(f"{out} exists (use --force to overwrite)")
    out.write_text(template_text())
    console.print(f"Wrote [bold]{out}[/bold]. Next: [{BRAND}]opslens doctor[/{BRAND}]")


@app.command()
def doctor(offline: Annotated[bool, typer.Option("--offline", help="Skip anything that needs a running service.")] = False,
           config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Check opslens, its catalogs, Flowpipe, Steampipe and the plugins; say how to fix what is missing."""
    from .doctor import run_checks

    cfg, _ = load(config, set_)
    marks = {"ok": "[green]ok[/green]  ", "warn": "[yellow]warn[/yellow]", "fail": "[red]fail[/red]"}
    checks = run_checks(cfg, offline=offline)
    for c in checks:
        console.print(f"{marks[c.status]}  [bold]{c.name}[/bold]: {c.detail}")
        if c.fix:
            console.print(f"        fix: [{BRAND}]{c.fix}[/{BRAND}]")
    if any(c.status == "fail" for c in checks):
        raise typer.Exit(1)


@app.command()
def params(filter_: Annotated[str | None, typer.Option("--filter", help="Only keys containing this text.")] = None,
           fmt: FormatOpt = Format.table, config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """List every setting with its value, where the value came from, and its environment variable."""
    cfg, source = load(config, set_)
    rows = [r for r in param_rows(cfg, source) if not filter_ or filter_ in r["key"]]
    emit(rows, fmt, title="opslens settings", columns=["key", "value", "source", "env"])


@app.command("config")
def show_config(config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Show the merged configuration (defaults + file + env + --set) as YAML."""
    cfg, _ = load(config, set_)
    data = cfg.model_dump()
    if data["steampipe"].get("password"):
        data["steampipe"]["password"] = "***"
    sys.stdout.write(yaml.safe_dump(data, sort_keys=False))


# ------------------------------------------------------------------ find / describe


def _plugins(cfg_plugins: list[str] | None, option: list[str] | None) -> set[str] | None:
    chosen = option or cfg_plugins
    return set(chosen) if chosen else None


@find_app.command("tables")
def find_tables(words: Annotated[list[str], typer.Argument(help="What you are looking for.")],
                plugin: Annotated[list[str] | None, typer.Option("--plugin", "-p", help="Limit to a plugin (repeatable).")] = None,
                limit: Annotated[int | None, typer.Option("--limit", "-n")] = None,
                fmt: FormatOpt = Format.table, config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Steampipe tables that can answer a question: opslens find tables unattached ebs volumes."""
    cfg, _ = load(config, set_)
    hits = tcat.load().find(" ".join(words), k=limit or cfg.catalog.default_results,
                            plugins=_plugins(cfg.catalog.plugins, plugin))
    emit(hits, fmt, columns=["table", "plugin", "description", "required_filters", "note"],
         note=f"next: opslens describe table {hits[0]['table']}" if hits else "no match; try other words")


@find_app.command("pipelines")
def find_pipelines(words: Annotated[list[str], typer.Argument(help="What you want to do.")],
                   mod: Annotated[list[str] | None, typer.Option("--mod", "-m", help="Limit to a mod (repeatable).")] = None,
                   writes: Annotated[bool, typer.Option("--writes", help="Only pipelines that change state.")] = False,
                   reads: Annotated[bool, typer.Option("--reads", help="Only pipelines that only read.")] = False,
                   limit: Annotated[int | None, typer.Option("--limit", "-n")] = None,
                   fmt: FormatOpt = Format.table, config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Flowpipe pipelines that can do something: opslens find pipelines create jira issue."""
    cfg, _ = load(config, set_)
    if writes and reads:
        raise err("--writes and --reads are mutually exclusive", 2)
    hits = pcat.load().find(" ".join(words), k=limit or cfg.catalog.default_results, mods=set(mod) if mod else None,
                            risk="write" if writes else "read" if reads else None)
    emit(hits, fmt, columns=["pipeline", "risk", "description", "requires"],
         note=f"next: opslens describe pipeline {hits[0]['pipeline']}" if hits else "no match; try other words")


@app.command()
def search(words: Annotated[list[str], typer.Argument(help="A requirement in plain words.")],
           limit: Annotated[int, typer.Option("--limit", "-n")] = 5, fmt: FormatOpt = Format.table) -> None:
    """Search both catalogs at once: the data to query and the action to take."""
    text = " ".join(words)
    res = csearch.find(text, k=limit)
    if fmt is Format.json:
        sys.stdout.write(json.dumps(res, indent=2) + "\n")
        return
    console.print(f"[bold]Data[/bold] (Steampipe tables) for: [{BRAND}]{' / '.join(res['data'])}[/{BRAND}]")
    emit(res["tables"], fmt, columns=["table", "description", "required_filters"])
    for a in res["actions"]:
        console.print(f"\n[bold]Action[/bold] (Flowpipe pipelines) for: [{BRAND}]{a['clause']}[/{BRAND}]")
        emit(a["pipelines"], fmt, columns=["pipeline", "risk", "description", "requires"])
    for cmd in csearch.suggest_next(text):
        err_console.print(f"[dim]next: {cmd}[/dim]")


@describe_app.command("table")
def describe_table(name: Annotated[str, typer.Argument(help="Table name, e.g. aws_ebs_volume.")],
                   fmt: FormatOpt = Format.table, no_examples: Annotated[bool, typer.Option("--no-examples")] = False) -> None:
    """Columns, types, required filters and examples for one Steampipe table."""
    cat = tcat.load()
    t = cat.get(name)
    if t is None:
        sim = cat.similar(name)
        raise err(f"unknown table '{name}'" + (f"; did you mean {', '.join(sim)}?" if sim else
                                              "; search with `opslens find tables <words>`"))
    d = cat.describe(t.name, examples=not no_examples)
    if fmt is Format.json:
        sys.stdout.write(json.dumps(d, indent=2) + "\n")
        return
    console.print(Panel(f"{d['description']}\n[dim]plugin: {d['plugin']}   service: {d['service']}[/dim]",
                        title=f"[bold]{d['table']}[/bold]", border_style=BRAND))
    for key in ("required_filters", "fast_filters", "cost_note", "time_note", "note"):
        if d.get(key):
            console.print(f"[yellow]{key.replace('_', ' ')}:[/yellow] {d[key]}")
    emit([{"column": c["name"], "type": c["type"], "filter": ("required" if c.get("required_filter") else
                                                           "fast" if c.get("fast_filter") else ""),
           "description": c.get("description", "")} for c in d["columns"]], Format.table,
         columns=["column", "type", "filter", "description"])
    for ex in d.get("examples", []):
        console.print(f"\n[bold]{ex['title']}[/bold]")
        console.print(Syntax(ex["sql"], "sql", theme="ansi_dark"))


@describe_app.command("pipeline")
def describe_pipeline(name: Annotated[str, typer.Argument(help="e.g. jira.pipeline.create_issue or jira.create_issue.")],
                      fmt: FormatOpt = Format.table) -> None:
    """Typed params, outputs, steps, risk class and a usage snippet for one Flowpipe pipeline."""
    cat = pcat.load()
    p = cat.get(name)
    if p is None:
        sim = cat.similar(name)
        raise err(f"unknown pipeline '{name}'" + (f"; did you mean {', '.join(sim)}?" if sim else
                                                  "; search with `opslens find pipelines <words>`"))
    d = cat.describe(p.name)
    if fmt is Format.json:
        sys.stdout.write(json.dumps(d, indent=2, default=str) + "\n")
        return
    risk = "[red]write[/red]: changes state, needs an approval gate" if d["risk"] == "write" else "[green]read[/green]"
    console.print(Panel(f"{d['description'] or d['title']}\n[dim]risk: {risk}   steps: {', '.join(d['steps'])}[/dim]",
                        title=f"[bold]{d['pipeline']}[/bold]", border_style=BRAND))
    emit([{"param": x["name"], "type": x["type"], "required": "yes" if x["required"] else "",
           "default": x.get("default", ""), "enum": x.get("enum", ""), "description": x.get("description", "")}
          for x in d["params"]], Format.table, columns=["param", "type", "required", "default", "enum", "description"])
    if d["outputs"]:
        console.print("outputs: " + ", ".join(o["name"] for o in d["outputs"]))
    console.print("\n[bold]Use it in a pipeline[/bold]")
    console.print(Syntax(d["usage"], "hcl", theme="ansi_dark"))


# ------------------------------------------------------------------ query


@app.command()
def query(sql: Annotated[str | None, typer.Argument(help="One read-only SELECT. Omit to read it from --file or stdin.")] = None,
          file: Annotated[Path | None, typer.Option("--file", "-F", help="Read the SQL from a file.")] = None,
          source: Annotated[Source, typer.Option("--source", help="live: the Steampipe service. demo: bundled sample data.")] = Source.live,
          any_table: Annotated[bool, typer.Option("--any-table", help="Skip the catalog allow-list (still read-only).")] = False,
          limit: Annotated[int | None, typer.Option("--limit", "-n", help="Row cap (default steampipe.max_rows).")] = None,
          fmt: FormatOpt = Format.table, config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Run one read-only SQL query. Guarded: a single SELECT, tables from the catalog, timeout and row cap."""
    cfg, _ = load(config, set_)
    text = sql or (file.read_text() if file else (sys.stdin.read() if not sys.stdin.isatty() else ""))
    if not text.strip():
        raise err("no SQL given (pass it as an argument, with --file, or on stdin)", 2)
    allowed = None if any_table else tcat.load().names()
    if source is Source.demo and not any_table:
        from .demo import TABLES

        allowed = frozenset(TABLES)
    try:
        res = (client.run_demo(text, allowed=allowed, max_rows=limit or cfg.steampipe.max_rows) if source is Source.demo
               else client.run_live(text, cfg.steampipe, allowed=allowed, max_rows=limit))
    except guard.UnsafeSQL as e:
        raise err(f"refused: {e}", 3) from e
    except client.SteampipeError as e:
        raise err(str(e)) from e
    emit(res.rows, fmt, columns=res.columns,
         note=(f"{len(res.rows)} row(s)" + (" (truncated at the row cap; raise --limit)" if res.truncated else "")
               + f" from {res.source}"))


# ------------------------------------------------------------------ catalog


@catalog_app.command("stats")
def catalog_stats(fmt: FormatOpt = Format.table) -> None:
    """What the shipped catalogs contain."""
    emit(tcat.load().stats(), fmt, title="Steampipe tables", columns=["plugin", "version", "tables", "columns", "examples"])
    if fmt is Format.table:
        console.print()
    emit(pcat.load().stats(), fmt, title="Flowpipe pipelines", columns=["mod", "version", "pipelines", "read", "write"])


@catalog_app.command("verify")
def catalog_verify(config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Compare the catalog with the installed Steampipe plugins (information_schema, no API calls)."""
    cfg, _ = load(config, set_)
    cat = tcat.load()
    try:
        live = client.live_columns(cfg.steampipe, set(cat.plugins))
    except client.SteampipeError as e:
        raise err(str(e)) from e
    merged = cat.with_live(live)
    known = [t for t in merged.tables.values() if t.live]
    missing_tables = sorted(set(cat.tables) - {t.name for t in known})
    drift = [(t.name, t.missing_live) for t in known if t.missing_live]
    unknown = sorted(n for n in set(live) - set(cat.tables) if n.split("_")[0] in cat.plugins)
    console.print(f"{len(known)} of {len(cat.tables)} catalog tables found in the installed plugins.")
    if missing_tables:
        by_plugin: dict[str, list[str]] = {}
        for n in missing_tables:
            by_plugin.setdefault(cat.tables[n].plugin, []).append(n)
        for plugin, names in sorted(by_plugin.items()):
            console.print(f"[yellow]{plugin}:[/yellow] {len(names)} catalog table(s) not in the installed plugin "
                          f"(version differs? catalog is {cat.plugins[plugin]}): {', '.join(names[:5])}"
                          + (" ..." if len(names) > 5 else ""))
    for name, missing in drift[:25]:
        console.print(f"[yellow]column drift[/yellow] {name}: in catalog, not live: {', '.join(missing[:8])}")
    if len(drift) > 25:
        console.print(f"[yellow]... and {len(drift) - 25} more tables with column drift[/yellow]")
    if unknown:
        console.print(f"[yellow]{len(unknown)} live table(s) are not in the catalog[/yellow] "
                      f"(e.g. {', '.join(unknown[:5])}); rebuild the catalog for the installed plugin versions.")
    if not (missing_tables or drift or unknown):
        console.print("[green]catalog matches the installed plugins.[/green]")
    raise typer.Exit(1 if (missing_tables or drift or unknown) else 0)


def _entry() -> Any:  # pragma: no cover
    return app()


if __name__ == "__main__":  # pragma: no cover
    app()
