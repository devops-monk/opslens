"""Read-only SQL execution: the live Steampipe service, or the bundled demo database.

Every query passes the guard first. Live connections additionally run with default_transaction_read_only=on, a
statement timeout and a row cap, so a wrong guard still cannot change anything or run away.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Any

from ..config import SteampipeConfig
from . import guard


class SteampipeError(RuntimeError):
    pass


@dataclass
class Result:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool = False
    source: str = "steampipe"

    def as_dicts(self) -> list[dict[str, Any]]:
        return self.rows


# ------------------------------------------------------------------ connection info


def service_status(binary: str = "steampipe") -> dict[str, str] | None:
    """Parse `steampipe service status --show-password`; None when the service is not running."""
    if not shutil.which(binary):
        return None
    r = subprocess.run([binary, "service", "status", "--show-password"], check=False, capture_output=True, text=True, timeout=30)
    text = r.stdout + r.stderr
    if "not running" in text.lower() or r.returncode != 0:
        return None
    info: dict[str, str] = {}
    for key, pat in (("host", r"Host\(s\):\s*(\S+)"), ("port", r"Port:\s*(\d+)"), ("database", r"Database:\s*(\S+)"),
                     ("user", r"User:\s*(\S+)"), ("password", r"Password:\s*(\S+)")):
        if m := re.search(pat, text, re.IGNORECASE):
            info[key] = m.group(1).rstrip(",")
    return info or None


def start_service(binary: str = "steampipe", *, restart: bool = False) -> bool:
    """Start (or restart) the data service with opslens's stored connections in its environment."""
    if not shutil.which(binary):
        return False
    from ..connections import child_env

    r = subprocess.run([binary, "service", "restart" if restart else "start"], check=False, capture_output=True, text=True,
                       timeout=180, env=child_env())
    return r.returncode == 0


def connection_string(cfg: SteampipeConfig) -> str:
    if cfg.dsn:
        return cfg.dsn
    password = cfg.password
    host, port = cfg.host, cfg.port
    if not password:
        st = service_status()
        if not st and cfg.auto_start and start_service():
            st = service_status()
        if not st:
            raise SteampipeError("Steampipe is not running. Start it with `steampipe service start`, or try the "
                                 "bundled sample data with `--source demo`.")
        password = st.get("password", "")
        port = int(st.get("port", port))
    return f"host={host} port={port} dbname={cfg.database} user={cfg.user} password={password} connect_timeout=10"


def live_columns(cfg: SteampipeConfig, plugins: set[str]) -> dict[str, list[tuple[str, str]]]:
    """table -> [(column, pg type)] from information_schema (no API calls). Tables are deduplicated across connections."""
    import psycopg

    out: dict[str, list[tuple[str, str]]] = {}
    with psycopg.connect(connection_string(cfg)) as conn, conn.cursor() as cur:
        cur.execute("select table_name, column_name, data_type from information_schema.columns "
                    "where table_schema not in ('information_schema','pg_catalog','steampipe_internal','steampipe_command') "
                    "order by table_name, ordinal_position")
        for table, col, typ in cur.fetchall():
            if table.split("_")[0] in plugins and not any(c == col for c, _ in out.get(table, [])):
                out.setdefault(table, []).append((col, typ))
    return out


# ------------------------------------------------------------------ execution


def run_live(sql: str, cfg: SteampipeConfig, *, allowed: set[str] | frozenset[str] | None = None,
             max_rows: int | None = None) -> Result:
    import psycopg
    from psycopg.rows import dict_row

    text = guard.check_tables(sql, allowed, "postgres") if allowed is not None else guard.check_select(sql)
    limit = max_rows or cfg.max_rows
    try:
        with psycopg.connect(connection_string(cfg), row_factory=dict_row, autocommit=False,
                             options=f"-c default_transaction_read_only=on "
                                     f"-c statement_timeout={cfg.statement_timeout_s * 1000}") as conn:
            with conn.cursor() as cur:
                cur.execute(text)
                cols = [d.name for d in cur.description] if cur.description else []
                rows = cur.fetchmany(limit + 1)
            conn.rollback()
    except psycopg.Error as e:
        raise SteampipeError(str(e).strip().splitlines()[0]) from e
    return Result(cols, rows[:limit], truncated=len(rows) > limit)


def run_demo(sql: str, *, allowed: set[str] | frozenset[str] | None = None, max_rows: int = 1000) -> Result:
    import sqlglot

    from ..demo import connect

    # Demo data lives in SQLite, but queries are written (and guarded) as Postgres, exactly like live ones.
    text = guard.check_tables(sql, allowed) if allowed is not None else guard.check_select(sql)
    try:
        lite = sqlglot.transpile(guard.parseable(text), read="postgres", write="sqlite")[0]
    except sqlglot.errors.SqlglotError as e:
        raise SteampipeError(f"cannot run this query on the demo data: {str(e).splitlines()[0]}") from e
    conn = connect()
    try:
        try:
            cur = conn.execute(lite)
        except sqlite3.Error as e:
            raise SteampipeError(f"{e} (the demo data is a small SQLite copy; try `--source live` for this query)") from e
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1)
    finally:
        conn.close()
    return Result(cols, [dict(r) for r in rows[:max_rows]], truncated=len(rows) > max_rows, source="demo")
