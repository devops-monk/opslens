"""One search over both catalogs: the read side (Steampipe tables) and the write side (Flowpipe pipelines).

A real requirement has two halves: *what to look at* and *what to do about it*. `find` splits the text into clauses,
asks the table catalog about the data clauses and the pipeline catalog about each action clause separately, so
"unattached ebs volumes then open a jira ticket and post to teams" returns the volume tables AND jira AND teams
actions instead of letting the first words win. No AI, no network, no credentials.
"""

from __future__ import annotations

import re
from typing import Any

from . import pipelines, tables

_SPLIT = re.compile(
    r"\s*(?:[,;]|->|=>|\bthen\b|\bafter that\b|\bafterwards\b|\band also\b|"
    r"\band\b(?=\s+(?:open|create|send|post|notify|page|file|raise|tag|delete|close|resolve|snapshot|stop|assign|"
    r"comment|message|alert|email|escalate|update|add|remove)\b))\s*", re.IGNORECASE)
_ACTION = re.compile(r"^\W*(?:and\s+)?(?:please\s+)?(open|create|send|post|notify|page|file|raise|tag|delete|close|"
                     r"resolve|snapshot|stop|assign|comment|message|alert|email|escalate|update|add|remove|"
                     r"transition|invite|ask|approve|if)\b", re.IGNORECASE)


def clauses(text: str) -> list[str]:
    return [c.strip() for c in _SPLIT.split(text or "") if c and c.strip()]


def is_action(clause: str) -> bool:
    return bool(_ACTION.match(clause))


def find(text: str, k: int = 5) -> dict[str, Any]:
    """{'data': [clause], 'tables': [...], 'actions': [{'clause', 'pipelines': [...]}]}"""
    cl = clauses(text) or [text]
    data = [c for c in cl if not is_action(c)] or cl[:1]
    acts = [c for c in cl if is_action(c)]
    pc, tc = pipelines.load(), tables.load()
    return {
        "data": data,
        "tables": tc.find(" ".join(data), k=k),
        "actions": [{"clause": c, "pipelines": pc.find(c, k=max(2, k // 2 + 1))} for c in (acts or [text])],
    }


def suggest_next(text: str) -> list[str]:
    """Commands to run after a search (the no-AI path): the best table and best action, described."""
    res = find(text, k=1)
    cmds = []
    if res["tables"]:
        cmds.append(f"opslens describe table {res['tables'][0]['table']}")
    for a in res["actions"]:
        if a["pipelines"]:
            cmds.append(f"opslens describe pipeline {a['pipelines'][0]['pipeline']}")
    return cmds
