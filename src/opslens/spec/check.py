"""Spec validation: the safety and correctness rules that stand between a request and a deployable mod.

Errors block rendering and deploy; warnings are shown at review. Rules (codes in brackets):
  - the detect query passes the SQL guard and reads only catalogued tables            [sql]
  - it lists its columns (no SELECT *), so every {placeholder} can be checked         [sql-star]
  - every action names a catalogued pipeline and supplies exactly its params          [pipeline, arg-unknown, arg-missing]
  - literal args match the param's type and enum                                      [arg-type, arg-enum]
  - every {column} / {var.x} placeholder resolves                                     [placeholder]
  - a pipeline that *changes* state must be gated behind approval unless auto_apply is set [ungated-write, auto-apply]
    (additive writes such as creating a ticket, alert or message may run ungated; max_items bounds them)
  - no secret-looking literals in args                                                [inline-secret]
  - schedules are not tighter than 5 minutes                                          [schedule]
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlglot import exp

from ..catalog import pipelines as pcat
from ..catalog import tables as tcat
from ..sql import guard
from .model import PLACEHOLDER, Spec, placeholders

SECRETISH = re.compile(r"(token|password|passwd|secret|api_?key|apikey|credential)", re.IGNORECASE)
SIMPLE_TYPES = {"string", "number", "bool", "list(string)", "map(string)"}
MIN_SCHEDULE_SECONDS = 300


@dataclass
class Issue:
    level: str  # error | warning
    code: str
    message: str
    where: str = ""

    def __str__(self) -> str:
        return f"{self.level}[{self.code}]{' ' + self.where if self.where else ''}: {self.message}"


def projection(sql: str) -> list[str] | None:
    """Output column names of a SELECT (first branch of a UNION); None if it uses `*`."""
    _, stmt = guard.parse_select(sql)
    node = stmt
    while isinstance(node, exp.SetOperation):
        node = node.this
    if isinstance(node, exp.Subquery):
        node = node.this
    if not isinstance(node, exp.Select):
        return None
    names = []
    for e in node.expressions:
        if isinstance(e, exp.Star) or (isinstance(e, exp.Column) and isinstance(e.this, exp.Star)):
            return None
        names.append(e.alias_or_name)
    return names


def schedule_seconds(s: str) -> int | None:
    m = re.fullmatch(r"(\d+)\s*([smh])", s.strip())
    if m:
        return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2)]
    return {"hourly": 3600, "daily": 86400, "weekly": 604800}.get(s.strip())


def schedule_ok(s: str) -> bool:
    s = s.strip()
    return schedule_seconds(s) is not None or len(s.split()) == 5  # named/interval, or a 5-field cron


def validate(spec: Spec, tc: tcat.TableCatalog | None = None, pc: pcat.PipelineCatalog | None = None) -> list[Issue]:
    tc, pc = tc or tcat.load(), pc or pcat.load()
    issues: list[Issue] = []

    def err(code: str, msg: str, where: str = "") -> None:
        issues.append(Issue("error", code, msg, where))

    def warn(code: str, msg: str, where: str = "") -> None:
        issues.append(Issue("warning", code, msg, where))

    # ---- detect query
    columns: list[str] = []
    try:
        guard.check_tables(spec.detect.sql, tc.names())
        cols = projection(spec.detect.sql)
        if cols is None:
            err("sql-star", "list the columns you need instead of SELECT * (placeholders can only be checked against "
                "named columns)", "detect.sql")
        else:
            columns = cols
        if "EOQ" in spec.detect.sql:
            err("sql", "the query may not contain the heredoc marker EOQ", "detect.sql")
        if re.search(r"\blimit\b", spec.detect.sql, re.IGNORECASE):
            warn("sql", f"the renderer already caps results at detect.max_items ({spec.detect.max_items}); "
                 "an inner LIMIT is applied first", "detect.sql")
    except guard.UnsafeSQL as e:
        err("sql", str(e), "detect.sql")

    # ---- trigger
    if spec.trigger.kind == "schedule":
        if not schedule_ok(spec.trigger.schedule):
            err("schedule", f"'{spec.trigger.schedule}' is not hourly/daily/weekly, an interval like 15m, or a cron",
                "trigger.schedule")
        elif (sec := schedule_seconds(spec.trigger.schedule)) is not None and sec < MIN_SCHEDULE_SECONDS:
            err("schedule", "schedules tighter than 5 minutes are refused (runaway-loop protection)", "trigger.schedule")

    # ---- actions
    seen_names: dict[str, int] = {}
    for i, a in enumerate(spec.actions, 1):
        where = f"actions[{i}] {a.pipeline}"
        p = pc.get(a.pipeline)
        if p is None:
            sim = pc.similar(a.pipeline)
            err("pipeline", f"unknown pipeline '{a.pipeline}'" + (f"; did you mean {', '.join(sim)}?" if sim else ""), where)
            continue
        seen_names[p.short] = seen_names.get(p.short, 0) + 1
        by_name = {x.name: x for x in p.params}
        for k, v in a.args.items():
            literal = PLACEHOLDER.sub("", str(v)).strip() if isinstance(v, str) else v
            if SECRETISH.search(k) and literal not in ("", None) and not placeholders(v):  # checked first, for any key
                err("inline-secret", f"'{k}' looks like a secret; keep credentials in a Flowpipe connection, never in a spec",
                    where)
            prm = by_name.get(k)
            if prm is None:
                err("arg-unknown", f"'{k}' is not a param of {p.name} (params: {', '.join(by_name)})", where)
                continue
            if prm.type not in SIMPLE_TYPES:
                err("arg-type", f"param '{k}' has type {prm.type}, which generated specs cannot set", where)
                continue
            for ph in placeholders(v):
                if ph.startswith("var."):
                    if ph[4:] not in spec.variables:
                        err("placeholder", f"{{{ph}}} is not declared in variables", where)
                elif ph not in columns and columns:
                    err("placeholder", f"{{{ph}}} is not a column of the detect query (columns: {', '.join(columns)})", where)
            if prm.enum and not placeholders(v) and v not in prm.enum:
                err("arg-enum", f"'{k}' must be one of {prm.enum}, got {v!r}", where)
            if prm.type == "map(string)" and not all("=" in kv for kv in str(v).split(",") if kv.strip()):
                err("arg-type", f"'{k}' must be comma-separated key=value pairs, got {v!r}", where)
            if prm.type == "number" and not placeholders(v):
                try:
                    float(v)
                except (TypeError, ValueError):
                    err("arg-type", f"'{k}' must be a number, got {v!r}", where)
            if prm.type == "bool" and not placeholders(v) and str(v).lower() not in ("true", "false"):
                err("arg-type", f"'{k}' must be true or false, got {v!r}", where)
        for x in p.required_params():
            if x.name not in a.args and not x.type.startswith("connection.") and x.type != "notifier":
                err("arg-missing", f"required param '{x.name}' ({x.type}) of {p.name} is not set", where)
        if p.effect == "change" and not a.gated:
            if spec.auto_apply:
                warn("auto-apply", f"{p.name} changes state and runs with NO approval (auto_apply is on)", where)
            else:
                err("ungated-write", f"{p.name} changes state: set gated: true so it runs only after approval "
                    "(or auto_apply: true, which is flagged at review)", where)
        elif p.effect == "notify" and not a.gated:
            pass  # additive (ticket / alert / message): allowed ungated; max_items bounds how many per run
        if a.gated and p.risk == "read":
            warn("gated-read", f"{p.name} only reads; gating it only delays it", where)
    for short, n in seen_names.items():
        if n > 1:
            warn("duplicate", f"{short} is used {n} times; steps are named after the pipeline plus an index", "actions")
    if not spec.gated_actions() and not spec.auto_apply and any(
            (pc.get(a.pipeline) and pc.get(a.pipeline).risk == "write") for a in spec.actions):
        pass  # already reported per action
    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]
