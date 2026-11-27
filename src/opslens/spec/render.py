"""Render a validated spec into a Flowpipe mod (HCL). Deterministic: the same spec always yields the same files.

Layout (a top-level mod, because only top-level triggers fire in Flowpipe):

    mod.fp         the mod and `require` blocks for the library mods the actions use
    pipelines.fp   variables, the detect SQL, and one pipeline: detect -> summary -> ungated actions -> approval -> gated actions
    triggers.fp    a schedule trigger (disabled by default) when trigger.kind == schedule
    spec.yaml      the spec this was rendered from (source of truth)
    README.md      what it does and how to run it

Safety by construction: connections and notifiers are params with defaults (never inline secrets); every literal
from the spec is escaped (no HCL injection through values); the detect query is capped by max_items; gated
actions sit behind an `input` step and run only when the answer is "approve".
"""

from __future__ import annotations

import hashlib
import re

from ..catalog import pipelines as pcat
from .model import PLACEHOLDER, Spec


class RenderError(ValueError):
    pass


def hcl_str(s: str) -> str:
    """A literal as an HCL quoted string: escapes \\, ", newlines and template openers."""
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    return '"' + s.replace("${", "$${").replace("%{", "%%{") + '"'


def template(value: str, *, row: str = "each.value") -> str:
    """'Volume {volume_id} in {var.region}' -> an HCL template string with ${each.value.volume_id} / ${var.region}."""
    out, pos = [], 0
    for m in PLACEHOLDER.finditer(value):
        out.append(hcl_str(value[pos:m.start()])[1:-1])
        ref = m.group(1)
        out.append("${" + (ref if ref.startswith("var.") else f"{row}.{ref}") + "}")
        pos = m.end()
    out.append(hcl_str(value[pos:])[1:-1])
    return '"' + "".join(out) + '"'


def arg_expr(value: str | float | bool, ptype: str) -> str:
    only_ph = PLACEHOLDER.fullmatch(value) if isinstance(value, str) else None
    ref = None
    if only_ph:
        r = only_ph.group(1)
        ref = r if r.startswith("var.") else f"each.value.{r}"
    if ptype == "number":
        return ref or str(value)
    if ptype == "bool":
        return ref or str(value).lower()
    if ptype == "list(string)":
        if ref:
            return f"[{ref}]"
        return "[" + ", ".join(template(p.strip()) for p in str(value).split(",") if p.strip()) + "]"
    if ptype == "string":
        return template(str(value))
    raise RenderError(f"cannot render a value for param type {ptype}")


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line else line for line in text.splitlines())


def step_name(i: int, short: str) -> str:
    return f"act_{i}_{re.sub(r'[^a-z0-9_]', '_', short)}"


def spec_hash(spec: Spec) -> str:
    """Stable content hash of the spec: what a reviewer approves, and what deploy refuses to drift from."""
    return hashlib.sha256(spec.to_yaml().encode()).hexdigest()[:16]


def mod_repo(mod: str) -> str:
    return f"github.com/turbot/flowpipe-mod-{mod.replace('_', '-')}"


def render(spec: Spec, pc: pcat.PipelineCatalog | None = None) -> dict[str, str]:
    pc = pc or pcat.load()
    resolved = []
    for a in spec.actions:
        p = pc.get(a.pipeline)
        if p is None:
            raise RenderError(f"unknown pipeline {a.pipeline} (run validate first)")
        resolved.append((a, p))
    mods = sorted({p.mod for _, p in resolved})

    mod_fp = [f'mod "{spec.name}" {{', f"  title = {hcl_str(spec.title)}"]
    if spec.description:
        mod_fp.append(f"  description = {hcl_str(spec.description)}")
    mod_fp.append("")
    mod_fp.append("  require {")
    mod_fp.append('    flowpipe {\n      min_version = "1.0.0"\n    }')
    for m in mods:
        mod_fp.append(f'    mod "{mod_repo(m)}" {{\n      version = "latest"\n    }}')
    mod_fp += ["  }", "}", ""]

    variables = {**{k: v for k, v in spec.variables.items()}}
    pf: list[str] = []
    for name, v in variables.items():
        typ = "bool" if isinstance(v.default, bool) else "number" if isinstance(v.default, (int, float)) else "string"
        default = str(v.default).lower() if isinstance(v.default, bool) else (
            str(v.default) if typ == "number" else hcl_str(str(v.default)))
        pf += [f'variable "{name}" {{', f"  type        = {typ}", f"  default     = {default}",
               f"  description = {hcl_str(v.description or name)}", "}", ""]
    if spec.trigger.kind == "schedule":
        pf += ['variable "trigger_enabled" {', "  type        = bool", "  default     = false",
               '  description = "Turn the schedule on. Off by default: review a run first."', "}", "",
               'variable "trigger_schedule" {', "  type        = string", f"  default     = {hcl_str(spec.trigger.schedule)}",
               '  description = "How often the detection runs."', "}", ""]
    sql = spec.detect.sql.strip().rstrip(";").strip()
    pf += ["locals {", "  detect_sql = <<-EOQ",
           _indent(f"select * from (\n{_indent(sql, 2)}\n) as detected\nlimit {spec.detect.max_items}", 4),
           "  EOQ", "}", ""]

    rows = "step.query.detect.rows"
    found = f"length({rows}) > 0"
    pf += [f'pipeline "{spec.name}" {{', f"  title       = {hcl_str(spec.title)}"]
    if spec.description:
        pf.append(f"  description = {hcl_str(spec.description)}")
    pf += ["",
           '  param "database" {', "    type        = connection.steampipe",
           '    description = "Steampipe connection the detection runs on."',
           "    default     = connection.steampipe.default", "  }", "",
           '  param "notifier" {', "    type        = notifier",
           '    description = "Where summaries and approval requests go."', "    default     = notifier.default", "  }", "",
           '  step "query" "detect" {', "    database = param.database", "    sql      = local.detect_sql", "  }", ""]
    if spec.notify:
        pf += ['  step "message" "summary" {', f"    if       = {found}", "    notifier = param.notifier",
               f'    text     = "{spec.title.replace(chr(34), chr(39))}: ${{length({rows})}} item(s) found"'.replace("$$", "$"),
               "  }", ""]

    def action_step(i: int, a, p, gate: bool) -> list[str]:
        by_name = {x.name: x for x in p.params}
        lines = [f'  step "pipeline" "{step_name(i, p.short)}" {{']
        if a.title:
            lines.append(f"    title    = {hcl_str(a.title)}")
        cond = "step.input.approve.value == \"approve\"" if gate else found
        lines += [f"    for_each = {rows}", f"    if       = {cond}", f"    pipeline = {p.mod}.pipeline.{p.short}",
                  "    args = {"]
        width = max((len(k) for k in a.args), default=0)
        for k in sorted(a.args):
            lines.append(f"      {k.ljust(width)} = {arg_expr(a.args[k], by_name[k].type)}")
        lines += ["    }", "  }", ""]
        return lines

    for i, (a, p) in enumerate(resolved, 1):
        if not a.gated:
            pf += action_step(i, a, p, False)
    if spec.gated_actions():
        n = ", ".join(sorted({p.short for a, p in resolved if a.gated}))
        pf += ['  step "input" "approve" {', f"    if       = {found}", '    type     = "button"', "    notifier = param.notifier",
               f"    prompt   = {hcl_str(spec.approval.prompt + ' (' + n + ')')}",
               '    option "approve" {\n      label = "Approve"\n      style = "ok"\n    }',
               '    option "skip" {\n      label = "Skip"\n      style = "info"\n    }', "  }", ""]
        for i, (a, p) in enumerate(resolved, 1):
            if a.gated:
                pf += action_step(i, a, p, True)
    pf += ['  output "found" {', f"    value = length({rows})", "  }", "}", ""]

    files = {"mod.fp": "\n".join(mod_fp), "pipelines.fp": "\n".join(pf)}
    if spec.trigger.kind == "schedule":
        files["triggers.fp"] = "\n".join([
            f'trigger "schedule" "{spec.name}_schedule" {{', f"  title    = {hcl_str(spec.title + ' (schedule)')}",
            "  enabled  = var.trigger_enabled", "  schedule = var.trigger_schedule",
            f"  pipeline = pipeline.{spec.name}", "}", ""])
    files["spec.yaml"] = spec.to_yaml()
    files["README.md"] = readme(spec, resolved)
    return files


def readme(spec: Spec, resolved: list) -> str:
    lines = [f"# {spec.title}", "", spec.description or "", ""]
    if spec.request:
        lines += ["**Request:**", f"> {spec.request}", ""]
    gen = ("Generated by [opslens](https://github.com/devops-monk/opslens). The source of truth is `spec.yaml`; "
           f"spec hash `{spec_hash(spec)}`.")
    lines += [gen, "", "## What it does", "",
              f"1. Runs a read-only query (max {spec.detect.max_items} rows):", "", "```sql", spec.detect.sql.strip(), "```", ""]
    n = 2
    for a, p in resolved:
        if not a.gated:
            lines.append(f"{n}. For each row: `{p.name}` ({p.risk}).")
            n += 1
    if spec.gated_actions():
        lines.append(f"{n}. Asks for approval, then for each row:")
        for a, p in resolved:
            if a.gated:
                lines.append(f"   - `{p.name}` ({p.risk})")
    lines += ["", "## Run it", "", "```bash", "flowpipe mod install",
              f"flowpipe pipeline run {spec.name}", "```", ""]
    if spec.trigger.kind == "schedule":
        note = ("The schedule trigger is **disabled** by default. Enable it with `--var trigger_enabled=true` "
                f"(default schedule `{spec.trigger.schedule}`).")
        lines += [note, ""]
    return "\n".join(lines)
