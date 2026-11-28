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
pack_app = typer.Typer(help="Curated automations that work with no AI.", no_args_is_help=True)
app.add_typer(pack_app, name="pack")


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


# ------------------------------------------------------------------ packs, render, validate, preview


def _load_spec_arg(path: Path) -> tuple[Any, Path | None]:
    """A spec file, or a generated mod directory (which holds spec.yaml). Returns (spec, mod_dir or None)."""
    from .spec.model import load_spec

    p = path / "spec.yaml" if path.is_dir() else path
    if not p.is_file():
        raise err(f"no spec found at {path} (expected a spec YAML or a generated mod directory)", 2)
    try:
        return load_spec(p.read_text()), (path if path.is_dir() else None)
    except (ValueError, TypeError) as e:
        raise err(f"{p}: invalid spec: {str(e).splitlines()[0] if len(str(e)) < 300 else str(e)[:300]}", 2) from e


def _write_mod(files: dict[str, str], out: Path, force: bool) -> None:
    if out.exists() and any(out.iterdir()) and not force:
        raise err(f"{out} is not empty (use --force to overwrite)")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out / name).write_text(text)


def _print_issues(issues: list[Any]) -> None:
    for i in issues:
        color = "red" if i.level == "error" else "yellow"
        console.print(f"[{color}]{i.level}[/{color}] [dim]{i.code}[/dim] {i.where + ': ' if i.where else ''}{i.message}")


@pack_app.command("list")
def pack_list(fmt: FormatOpt = Format.table) -> None:
    """The packs that ship with opslens."""
    from . import packs

    emit(packs.list_packs(), fmt, columns=["pack", "title", "trigger", "actions", "variables"])


@pack_app.command("show")
def pack_show(name: Annotated[str, typer.Argument(help="e.g. finops-cleanup/unattached-volumes")],
              var: Annotated[list[str] | None, typer.Option("--var", help="name=value (repeatable).")] = None) -> None:
    """Print a pack's spec (what you would be installing)."""
    from . import packs

    try:
        spec = packs.get(name, dict(v.split("=", 1) for v in var or []))
    except KeyError as e:
        raise err(str(e.args[0])) from e
    console.print(Syntax(spec.to_yaml(), "yaml", theme="ansi_dark"))


@pack_app.command("install")
def pack_install(name: Annotated[str, typer.Argument(help="e.g. finops-cleanup/unattached-volumes")],
                 var: Annotated[list[str] | None, typer.Option("--var", help="name=value (repeatable).")] = None,
                 out: Annotated[Path | None, typer.Option("--out", "-o", help="Parent directory (default flowpipe.workspace_dir).")] = None,
                 force: Annotated[bool, typer.Option("--force")] = False,
                 config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Render a pack into a Flowpipe mod: opslens pack install finops-cleanup/unattached-volumes --var jira_project=INFRA."""
    from . import packs
    from .spec import check, render

    cfg, _ = load(config, set_)
    try:
        spec = packs.get(name, dict(v.split("=", 1) for v in var or []))
    except (KeyError, ValueError) as e:
        raise err(str(e.args[0])) from e
    issues = check.validate(spec)
    _print_issues(issues)
    if check.errors(issues):
        raise err("the pack does not validate; nothing written", 1)
    dest = (out or Path(cfg.flowpipe.workspace_dir)) / spec.name
    _write_mod(render.render(spec), dest, force)
    console.print(f"Wrote [bold]{dest}[/bold]  (spec hash {render.spec_hash(spec)})")
    console.print(f"next: [{BRAND}]opslens validate {dest}[/{BRAND}] then [{BRAND}]opslens preview {dest} --source demo[/{BRAND}]")


@app.command("render")
def render_cmd(spec_file: Annotated[Path, typer.Argument(help="A spec YAML.")],
               out: Annotated[Path, typer.Option("--out", "-o", help="Directory to write the mod into.")] = Path("generated"),
               force: Annotated[bool, typer.Option("--force")] = False) -> None:
    """Validate a spec and render it into a Flowpipe mod (<out>/<spec name>/)."""
    from .spec import check, render

    spec, _ = _load_spec_arg(spec_file)
    issues = check.validate(spec)
    _print_issues(issues)
    if check.errors(issues):
        raise err("the spec does not validate; nothing written", 1)
    dest = out / spec.name
    _write_mod(render.render(spec), dest, force)
    console.print(f"Wrote [bold]{dest}[/bold]  (spec hash {render.spec_hash(spec)})")


@app.command()
def validate(path: Annotated[Path, typer.Argument(help="A spec YAML or a generated mod directory.")],
             load_check: Annotated[bool, typer.Option("--load/--no-load", help="Also load the mod with Flowpipe's own parser.")] = True,
             config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Check a spec against the catalogs and safety rules, that generated files still match it, and that Flowpipe loads it."""
    import tempfile

    from .spec import check, render
    from .validate.load import load_check as flowpipe_load

    cfg, _ = load(config, set_)
    spec, mod_dir = _load_spec_arg(path)
    issues = check.validate(spec)
    files = None
    if not check.errors(issues):
        files = render.render(spec)
        if mod_dir:  # hand edits would make the reviewed spec and the deployed HCL diverge
            for name, text in files.items():
                f = mod_dir / name
                if not f.exists():
                    issues.append(check.Issue("error", "drift", f"{name} is missing; re-render with `opslens render`"))
                elif f.read_text() != text:
                    issues.append(check.Issue("error", "drift", f"{name} differs from what spec.yaml renders to (edited by "
                                              "hand?). Change spec.yaml and re-render instead"))
        if load_check and not check.errors(issues):
            with tempfile.TemporaryDirectory() as tmp:
                target = mod_dir or Path(tmp)
                if not mod_dir:
                    for name, text in files.items():
                        (Path(tmp) / name).write_text(text)
                issues += flowpipe_load(target, cfg.flowpipe.binary)
    _print_issues(issues)
    n_err = len(check.errors(issues))
    console.print(f"[bold]{spec.name}[/bold]: " + (f"[red]{n_err} error(s)[/red]" if n_err else "[green]valid[/green]")
                  + f"   spec hash {render.spec_hash(spec)}")
    raise typer.Exit(1 if n_err else 0)


@app.command("preview")
def preview_cmd(path: Annotated[Path, typer.Argument(help="A spec YAML or a generated mod directory.")],
                source: Annotated[Source, typer.Option("--source")] = Source.live,
                sample: Annotated[int, typer.Option("--sample", help="Rows shown per action.")] = 3,
                fmt: FormatOpt = Format.table, config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """What a run would do right now: items found, and each action's arguments. Reads only; changes nothing."""
    from .spec import check
    from .validate.preview import preview

    cfg, _ = load(config, set_)
    spec, _dir = _load_spec_arg(path)
    errs = check.errors(check.validate(spec))
    if errs:
        _print_issues(errs)
        raise err("fix the spec first (`opslens validate`)", 1)
    try:
        pv = preview(spec, source.value, cfg.steampipe)
    except guard.UnsafeSQL as e:
        raise err(f"refused: {e}", 3) from e
    except client.SteampipeError as e:
        raise err(str(e)) from e
    if fmt is Format.json:
        sys.stdout.write(json.dumps({"items": pv.items, "truncated": pv.truncated, "rows": pv.rows,
                                     "actions": [a.__dict__ for a in pv.actions]}, indent=2, default=str) + "\n")
        return
    console.print(Panel(f"[bold]{pv.items}[/bold] item(s) found from {pv.source}"
                        + (f"  [yellow](capped at {spec.detect.max_items})[/yellow]" if pv.truncated else ""),
                        title=f"preview: {spec.title}", border_style=BRAND))
    emit(pv.rows[:sample], Format.table, columns=pv.columns, note=f"first {min(sample, pv.items)} of {pv.items} row(s)")
    for a in pv.actions:
        tag = {"read": "[green]read[/green]", "notify": "[cyan]notify[/cyan]", "change": "[red]CHANGE[/red]"}.get(a.effect, a.effect)
        gate = "after approval" if a.gated else "automatically"
        console.print(f"\n[bold]{a.index}. {a.pipeline}[/bold]  {tag}  runs {gate}  x {len(a.calls)}")
        for c in a.calls[:sample]:
            console.print("   " + ", ".join(f"{k}={v!r}" for k, v in c.items()))
    console.print(f"\n[bold]{pv.changes}[/bold] state change(s) would be requested; "
                  "[bold]0[/bold] have been made (this was a preview).")


# ------------------------------------------------------------------ deploy, run, approve, runs


def _deployed(path: Path) -> tuple[Any, dict[str, Any], Any]:
    from .flowpipe import server
    from .flowpipe.client import Flowpipe

    spec, mod_dir = _load_spec_arg(path)
    if mod_dir is None:
        raise err("pass the generated mod directory (from `opslens pack install` or `render`)", 2)
    st = server.read_state(mod_dir)
    if not st or not server.is_running(st):
        raise err(f"{mod_dir} is not deployed (`opslens deploy {mod_dir}`)")
    return spec, st, Flowpipe(f"http://localhost:{st['port']}")


@app.command()
def deploy(path: Annotated[Path, typer.Argument(help="A generated mod directory.")],
           approve: Annotated[str | None, typer.Option("--approve", help="The spec hash you reviewed.")] = None,
           enable_schedule: Annotated[bool, typer.Option("--enable-schedule", help="Turn the schedule trigger on.")] = False,
           config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Start a Flowpipe server for a generated mod. You must approve the exact spec hash you reviewed."""
    from .flowpipe import server
    from .flowpipe.client import FlowpipeError
    from .runs.store import Audit
    from .spec import check, render
    from .validate.preview import preview as run_preview  # noqa: F401  (kept for symmetry with `preview`)

    cfg, _ = load(config, set_)
    spec, mod_dir = _load_spec_arg(path)
    if mod_dir is None:
        raise err("pass the generated mod directory (from `opslens pack install` or `render`)", 2)
    issues = check.validate(spec)
    for name, text in render.render(spec).items() if not check.errors(issues) else []:
        if not (mod_dir / name).exists() or (mod_dir / name).read_text() != text:
            issues.append(check.Issue("error", "drift", f"{name} differs from what spec.yaml renders to; re-render"))
    if issues:
        _print_issues(issues)
    if check.errors(issues):
        raise err("not deploying: fix the errors above", 1)
    h = render.spec_hash(spec)
    gated = [a.pipeline for a in spec.gated_actions()]
    if approve != h:
        console.print(Panel(
            f"[bold]{spec.title}[/bold]\nspec hash: [bold]{h}[/bold]\n"
            f"runs: {spec.trigger.kind}" + (f" ({spec.trigger.schedule}, off until --enable-schedule)" if spec.trigger.kind == "schedule" else "")
            + f"\nmax {spec.detect.max_items} items per run\n"
            + ("approval required before: " + ", ".join(gated) if gated else "no approval gate (no state-changing actions)")
            + ("\n[red]auto_apply is ON: state changes run without approval[/red]" if spec.auto_apply else ""),
            title="review before deploying", border_style="yellow"))
        raise err(f"review the spec (`opslens preview {mod_dir} --source demo`), then re-run with --approve {h}", 2)
    try:
        server.install_mods(mod_dir, cfg.flowpipe.binary)
        st = server.start(mod_dir, h, binary=cfg.flowpipe.binary,
                          variables={"trigger_enabled": "true"} if enable_schedule and spec.trigger.kind == "schedule" else None)
        from .flowpipe.client import Flowpipe

        Flowpipe(f"http://localhost:{st['port']}").wait_for_pipeline(f"{spec.name}.pipeline.{spec.name}", timeout_s=60)
    except FlowpipeError as e:
        raise err(str(e)) from e
    Audit(mod_dir.resolve().parent).log("deploy", spec.name, h, f"port {st['port']}" + (", schedule on" if enable_schedule else ""))
    console.print(f"Deployed [bold]{spec.name}[/bold] on port {st['port']} (pid {st['pid']}). "
                  f"Run it: [{BRAND}]opslens run {mod_dir}[/{BRAND}]")


@app.command()
def undeploy(path: Annotated[Path, typer.Argument()]) -> None:
    """Stop the Flowpipe server for a generated mod."""
    from .flowpipe import server
    from .runs.store import Audit

    spec, mod_dir = _load_spec_arg(path)
    if mod_dir is None or not server.stop(mod_dir):
        raise err("not deployed")
    Audit(mod_dir.resolve().parent).log("undeploy", spec.name)
    console.print(f"Stopped [bold]{spec.name}[/bold].")


@app.command("run")
def run_cmd(path: Annotated[Path, typer.Argument(help="A deployed mod directory.")],
            timeout: Annotated[int, typer.Option("--timeout", help="Seconds to wait.")] = 120) -> None:
    """Run a deployed pipeline now. Stops and prints the approval link if it is waiting for approval."""
    from .flowpipe.client import FlowpipeError
    from .runs.store import Audit

    spec, st, fp = _deployed(path)
    name = f"{spec.name}.pipeline.{spec.name}"
    try:
        eid = fp.run(name)
        Audit(path.resolve().parent).log("run", spec.name, st["spec_hash"], eid)
        state = fp.wait(eid, timeout_s=timeout)
    except FlowpipeError as e:
        raise err(str(e)) from e
    console.print(f"{state.execution_id}: [bold]{state.status}[/bold]  outputs: {state.outputs or '-'}")
    if state.status == "waiting":
        console.print(f"[yellow]Waiting for approval.[/yellow] Answer in your notifier, open {state.approval_url}, "
                      f"or: [{BRAND}]opslens approve {path} {eid} --choice approve|skip[/{BRAND}]")
    if state.status == "failed":
        raise err(state.error or "the run failed (see `flowpipe process show`)", 1)


@app.command()
def approve(path: Annotated[Path, typer.Argument(help="A deployed mod directory.")],
            execution: Annotated[str, typer.Argument(help="The execution id from `opslens run`.")],
            choice: Annotated[str, typer.Option("--choice", help="approve or skip.")] = "approve",
            timeout: Annotated[int, typer.Option("--timeout")] = 300) -> None:
    """Answer a waiting approval from the terminal (the same answer the Slack/Teams/browser form submits)."""
    from .flowpipe.client import FlowpipeError
    from .runs.store import Audit

    if choice not in ("approve", "skip"):
        raise err("--choice must be approve or skip", 2)
    spec, st, fp = _deployed(path)
    try:
        state = fp.state(execution)
        if state.status != "waiting" or not state.approval_url or not state.waiting_on:
            raise err(f"{execution} is not waiting for approval (status: {state.status})")
        fp.answer(state.approval_url, state.waiting_on, choice)
        Audit(path.resolve().parent).log("approve", spec.name, st["spec_hash"], f"{execution}: {choice}")
        state = fp.wait(execution, timeout_s=timeout, until_waiting=False)
    except FlowpipeError as e:
        raise err(str(e)) from e
    console.print(f"{execution}: [bold]{state.status}[/bold]  outputs: {state.outputs or '-'}")


@app.command()
def runs(path: Annotated[Path, typer.Argument(help="A generated mod directory.")], limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
         fmt: FormatOpt = Format.table) -> None:
    """The audit log for a mod: deploys (with the approved spec hash), runs, approvals."""
    from .runs.store import Audit

    spec, mod_dir = _load_spec_arg(path)
    emit(Audit((mod_dir or path).resolve().parent).events(spec.name, limit), fmt,
         columns=["at", "actor", "kind", "spec_hash", "detail"])


@app.command()
def generate(requirement: Annotated[str, typer.Argument(help="What you want, in plain English.")],
             out: Annotated[Path | None, typer.Option("--out", "-o", help="Parent directory (default flowpipe.workspace_dir).")] = None,
             force: Annotated[bool, typer.Option("--force")] = False,
             dry_run: Annotated[bool, typer.Option("--dry-run", help="Show the spec; write nothing.")] = False,
             show_context: Annotated[bool, typer.Option("--show-context", help="Print what would be sent to the model, then stop.")] = False,
             config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """AI: turn a requirement into a validated spec and a Flowpipe mod. Needs `llm.provider` (see `opslens params`)."""
    from .ai import planner
    from .ai.providers import LLMError, make_provider
    from .spec import render
    from .spec.explain import explain as explain_spec

    cfg, _ = load(config, set_)
    sent = planner.redact(requirement) if cfg.llm.redact else requirement
    if show_context:
        console.print("-- system prompt --", style="dim")
        console.print(planner.system_prompt(), markup=False)
        console.print("-- user message --", style="dim")
        console.print(f"{planner.context_for(sent)}\n\n## Requirement\n{sent}", markup=False)
        return
    try:
        provider = make_provider(cfg.llm)
        with console.status(f"Planning with {provider.name} ({provider.model})..."):
            plan = planner.plan(requirement, provider, max_attempts=cfg.llm.max_attempts, do_redact=cfg.llm.redact)
    except (LLMError, planner.PlannerError) as e:
        raise err(str(e)) from e
    _print_issues(plan.issues)
    console.print(Panel(plan.yaml, title=f"spec from {plan.model} ({plan.attempts} attempt{'s' * (plan.attempts > 1)})",
                        border_style=BRAND))
    for line in explain_spec(plan.spec):
        console.print(f"  {line}")
    if dry_run:
        return
    dest = (out or Path(cfg.flowpipe.workspace_dir)) / plan.spec.name
    _write_mod(render.render(plan.spec), dest, force)
    console.print(f"Wrote [bold]{dest}[/bold]  (spec hash {render.spec_hash(plan.spec)}). [yellow]AI-written: read it before you trust it.[/yellow]")
    console.print(f"next: [{BRAND}]opslens preview {dest} --source demo[/{BRAND}]")


@app.command()
def explain(path: Annotated[Path, typer.Argument(help="A spec YAML or generated mod directory.")]) -> None:
    """Explain a spec in plain English (no AI): what it queries, what runs by itself, what waits for approval."""
    from .spec.explain import explain as explain_spec

    spec, _ = _load_spec_arg(path)
    for line in explain_spec(spec):
        console.print(f"- {line}")


@app.command()
def serve(host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
          port: Annotated[int, typer.Option("--port")] = 8077,
          mode: Annotated[str, typer.Option("--mode", help="local: one person, loopback only. team: hosted for a team, needs --auth. demo: sample data only, safe to expose.")] = "local",
          workspace: Annotated[Path | None, typer.Option("--workspace", help="Where mods are saved (default flowpipe.workspace_dir).")] = None,
          allow_host: Annotated[list[str] | None, typer.Option("--allow-host", help="Extra Host header to accept (repeatable). Required in team mode.")] = None,
          trust_proxy: Annotated[bool, typer.Option("--trust-proxy", help="Use X-Forwarded-For for rate limiting (behind nginx).")] = False,
          auth: Annotated[str | None, typer.Option("--auth", help="team mode: password (shared password from OPSLENS_TEAM_PASSWORD) or proxy (an identity proxy; secret in OPSLENS_PROXY_SECRET).")] = None,
          auth_header: Annotated[str, typer.Option("--auth-header", help="--auth proxy: the header carrying the signed-in user.")] = "X-Forwarded-Email",
          secure_cookies: Annotated[bool, typer.Option("--secure-cookies/--no-secure-cookies", help="team mode: mark the session cookie Secure (HTTPS only). Turn off only to try it over plain http.")] = True,
          config: ConfigOpt = None, set_: SetOpt = None) -> None:
    """Run the web app. local = one person on loopback; team = hosted for a team (needs --auth); demo = public, sample data only."""
    import os

    if mode not in ("local", "demo", "team"):
        raise err("--mode must be local, team or demo", 2)
    if mode == "local" and host not in ("127.0.0.1", "localhost", "::1"):
        raise err("local mode can deploy and run pipelines and has no sign-in, so it only binds to loopback. "
                  "To host it for a team use --mode team (needs --auth); to share it publicly use --mode demo (sample data, read-only).", 2)
    password, proxy_secret = os.environ.get("OPSLENS_TEAM_PASSWORD"), os.environ.get("OPSLENS_PROXY_SECRET")
    if mode != "team" and auth:
        raise err("--auth only applies to --mode team", 2)
    try:
        import uvicorn

        from .web.app import create_app, team_settings_problems
    except ImportError as e:
        raise err("the web app needs extra packages: pip install 'opslens[web]'") from e
    if mode == "team":
        problems = team_settings_problems(auth=auth, password=password, proxy_secret=proxy_secret, allow_hosts=tuple(allow_host or ()))
        if problems:
            raise err("team mode will not start without sign-in:\n  - " + "\n  - ".join(problems), 2)
    cfg, _ = load(config, set_)
    web = create_app(cfg, mode=mode, workspace=workspace, allow_hosts=tuple(allow_host or ()), trust_proxy=trust_proxy,
                     auth=auth, password=password, proxy_secret=proxy_secret, auth_header=auth_header, secure_cookies=secure_cookies,
                     session_secret=os.environ.get("OPSLENS_SESSION_SECRET") or None)
    console.print(f"opslens app ({mode}{f', auth {auth}' if mode == 'team' else ''}) on [bold]http://{host}:{port}[/bold]")
    uvicorn.run(web, host=host, port=port, log_level="warning", proxy_headers=trust_proxy, forwarded_allow_ips="*" if trust_proxy else None)


def _entry() -> Any:  # pragma: no cover
    return app()


if __name__ == "__main__":  # pragma: no cover
    app()
