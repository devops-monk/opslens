"""Append-only audit log (SQLite): who approved which spec hash, when it was deployed, and every run started.

One file per workspace (<workspace>/.opslens/audit.db). Rows are never updated or deleted by opslens.
"""

from __future__ import annotations

import getpass
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
create table if not exists events (
  id integer primary key autoincrement,
  at real not null,
  actor text not null,
  kind text not null,          -- deploy | undeploy | run
  mod text not null,
  spec_hash text,
  detail text
)
"""


class Audit:
    def __init__(self, workspace: Path):
        d = workspace / ".opslens"
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / "audit.db"
        with self._conn() as c:
            c.execute(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def log(self, kind: str, mod: str, spec_hash: str | None = None, detail: str = "", actor: str | None = None) -> None:
        with self._conn() as c:
            c.execute("insert into events (at, actor, kind, mod, spec_hash, detail) values (?,?,?,?,?,?)",
                      (time.time(), actor or getpass.getuser(), kind, mod, spec_hash, detail))

    def events(self, mod: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        q, args = "select * from events", []
        if mod:
            q, args = q + " where mod = ?", [mod]
        with self._conn() as c:
            rows = c.execute(q + " order by id desc limit ?", [*args, limit]).fetchall()
        return [dict(r) | {"at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["at"]))} for r in rows]
