"""Bundled sample data so every read-only command works with no cloud account and no credentials."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .data import TABLES


def connect() -> sqlite3.Connection:
    """A fresh in-memory SQLite database holding the demo tables. JSON columns are stored as JSON text."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for name, rows in TABLES.items():
        cols = list(rows[0])
        conn.execute(f'create table "{name}" ({", ".join(f"{c}" for c in cols)})')
        conn.executemany(f'insert into "{name}" values ({", ".join("?" * len(cols))})',
                         [tuple(_cell(r[c]) for c in cols) for r in rows])
    conn.commit()
    return conn


def _cell(v: Any) -> Any:
    return json.dumps(v) if isinstance(v, (dict, list)) else v
