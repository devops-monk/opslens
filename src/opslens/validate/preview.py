"""Preview: what would this run do *right now*? Reads only; nothing is created, changed or sent.

Runs the detect query (read-only, guarded, capped), then resolves every action's arguments for each row exactly as the
rendered pipeline would, and labels each action read / notify / change and gated or not. This is the "blast radius"
a reviewer approves: how many items, which actions, with which values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..catalog import pipelines as pcat
from ..catalog import tables as tcat
from ..config import SteampipeConfig
from ..spec.model import PLACEHOLDER, Spec
from ..sql import client


@dataclass
class PlannedAction:
    index: int
    pipeline: str
    effect: str
    gated: bool
    title: str
    calls: list[dict[str, Any]] = field(default_factory=list)  # resolved args, one per row


@dataclass
class Preview:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    source: str
    actions: list[PlannedAction]

    @property
    def items(self) -> int:
        return len(self.rows)

    @property
    def changes(self) -> int:
        return sum(len(a.calls) for a in self.actions if a.effect == "change")


def resolve(value: Any, row: dict[str, Any], variables: dict[str, Any]) -> Any:
    if not isinstance(value, str):
        return value

    def sub(m: Any) -> str:
        ref = m.group(1)
        if ref.startswith("var."):
            return str(variables.get(ref[4:], ""))
        v = row.get(ref)
        return "" if v is None else str(v)

    return PLACEHOLDER.sub(sub, value)


def preview(spec: Spec, source: str, cfg: SteampipeConfig, pc: pcat.PipelineCatalog | None = None) -> Preview:
    pc = pc or pcat.load()
    tc = tcat.load()
    sql = spec.detect.sql.strip().rstrip(";")
    capped = f"select * from (\n{sql}\n) as detected limit {spec.detect.max_items}"
    allowed = tc.names()
    if source == "demo":
        from ..demo import TABLES

        res = client.run_demo(capped, allowed=frozenset(TABLES), max_rows=spec.detect.max_items)
    else:
        res = client.run_live(capped, cfg, allowed=allowed, max_rows=spec.detect.max_items)
    variables = {k: v.default for k, v in spec.variables.items()}
    actions = []
    for i, a in enumerate(spec.actions, 1):
        p = pc.get(a.pipeline)
        effect = p.effect if p else "unknown"
        calls = [{k: resolve(v, row, variables) for k, v in a.args.items()} for row in res.rows]
        actions.append(PlannedAction(i, p.name if p else a.pipeline, effect, a.gated, a.title, calls))
    return Preview(res.columns, res.rows, res.truncated, res.source, actions)
