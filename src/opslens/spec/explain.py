"""A plain-English reading of a spec. Deterministic, no AI: the same words a reviewer should hold in their head
before approving."""

from __future__ import annotations

from ..catalog import pipelines as pcat
from .check import projection, schedule_seconds
from .model import Spec


def explain(spec: Spec) -> list[str]:
    pc = pcat.load()
    lines = [f"{spec.title}: {spec.description}".rstrip(": ")]
    if spec.trigger.kind == "schedule":
        s = schedule_seconds(spec.trigger.schedule)
        every = f"every {s // 3600}h" if s and s % 3600 == 0 else f"every {s // 60} min" if s else spec.trigger.schedule
        lines.append(f"Runs {every} (the schedule ships switched off until you deploy with --enable-schedule), or on demand.")
    else:
        lines.append("Runs only when you start it.")
    cols = projection(spec.detect.sql)
    lines.append(f"Each run queries read-only for rows with: {', '.join(cols) if cols else 'the listed columns'} "
                 f"(at most {spec.detect.max_items} rows).")
    if spec.notify:
        lines.append("It posts a one-line summary to the notifier when it finds something.")
    free = [a for a in spec.actions if not a.gated]
    held = spec.gated_actions()
    for a in free:
        p = pc.get(a.pipeline)
        lines.append(f"For each row, immediately: {a.title or a.pipeline} ({a.pipeline}, {p.effect if p else '?'}).")
    if held:
        lines.append(f"Then it asks: \"{spec.approval.prompt}\" Only on approval, for each row: "
                     + "; ".join(f"{a.title or a.pipeline} ({a.pipeline})" for a in held) + ".")
    else:
        lines.append("It makes no state changes, so there is no approval step.")
    if spec.auto_apply:
        lines.append("WARNING: auto_apply is on; state changes run WITHOUT approval.")
    return lines
