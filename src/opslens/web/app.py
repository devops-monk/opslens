"""The opslens web app (`opslens serve`): the same engine as the CLI behind a small JSON API and a single-page UI.

Two modes:
  local  (default) bound to 127.0.0.1 for one person. Full workflow: search, build, validate, preview (demo or live),
         generate with AI, save, deploy (only the spec hash you reviewed), run, approve, audit log.
  demo   safe to expose publicly: bundled sample data only, no AI, no files written, nothing deployed or run, input
         size limits and a per-client rate limit. Nothing here can reach a cloud account.

Protections: a Host-header allow-list (blocks DNS rebinding), a per-process token required on every state-changing call
(blocks cross-site requests), and the same SQL guard, validator and approval gates as the CLI.
"""

from __future__ import annotations

import json
import secrets
import time
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__, packs
from ..catalog import pipelines as pcat
from ..catalog import search
from ..catalog import tables as tcat
from ..config import Config
from ..spec import check, render
from ..spec.explain import explain
from ..spec.model import load_spec
from ..sql import client, guard
from ..validate.preview import preview

STATIC = Path(__file__).parent / "static"
MAX_YAML, MAX_SQL, MAX_ASK = 20_000, 5_000, 1_000


class Yaml(BaseModel):
    yaml: str = Field(max_length=MAX_YAML)
    source: str = "demo"


class Sql(BaseModel):
    sql: str = Field(max_length=MAX_SQL)
    source: str = "demo"


class Ask(BaseModel):
    requirement: str = Field(max_length=MAX_ASK)


class Save(BaseModel):
    yaml: str = Field(max_length=MAX_YAML)
    force: bool = False


class Approve(BaseModel):
    spec_hash: str
    enable_schedule: bool = False


class Answer(BaseModel):
    execution: str
    choice: str


def clean(obj: Any) -> Any:
    """JSON-safe copy (live rows hold datetimes, decimals, ...)."""
    return json.loads(json.dumps(obj, default=str))


class Limiter:
    def __init__(self, per_minute: int):
        self.n, self.hits = per_minute, defaultdict(deque)

    def ok(self, who: str) -> bool:
        now, q = time.monotonic(), self.hits[who]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.n:
            return False
        q.append(now)
        return True


def create_app(cfg: Config, *, mode: str = "local", workspace: Path | None = None, allow_hosts: tuple[str, ...] = (),
               trust_proxy: bool = False, rate_per_minute: int = 60, token: str | None = None) -> FastAPI:
    assert mode in ("local", "demo")
    demo = mode == "demo"
    ws = (workspace or Path(cfg.flowpipe.workspace_dir)).resolve()
    tok = token or secrets.token_urlsafe(24)
    hosts = {"localhost", "127.0.0.1", "[::1]", "testserver", *allow_hosts}
    limiter = Limiter(rate_per_minute)
    app = FastAPI(title="opslens", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard_requests(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0] if not (request.headers.get("host") or "").startswith("[") \
            else (request.headers.get("host") or "").split("]")[0] + "]"
        if host not in hosts:
            return JSONResponse({"detail": "host not allowed"}, status_code=400)
        if request.url.path.startswith("/api/"):
            who = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() if trust_proxy else "") or \
                (request.client.host if request.client else "?")
            if demo and not limiter.ok(who):
                return JSONResponse({"detail": "slow down: too many requests"}, status_code=429)
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                                                   "img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        return resp

    def mutating(request: Request) -> None:
        if not secrets.compare_digest(request.headers.get("x-opslens-token", ""), tok):
            raise HTTPException(403, "missing or wrong token (reload the page)")

    def local_only(request: Request) -> None:
        if demo:
            raise HTTPException(403, "this is the public demo: it only uses sample data. Install opslens to do this for real.")
        mutating(request)

    def parse(text: str):
        try:
            return load_spec(text)
        except (ValueError, TypeError, yaml.YAMLError) as e:  # show the reviewer what is wrong
            raise HTTPException(422, f"not a valid spec: {str(e)[:500]}") from e

    # ---------------------------------------------------------------- meta + catalog
    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        tc, pc = tcat.load(), pcat.load()
        return {"version": __version__, "mode": mode, "token": tok, "ai": (not demo and cfg.llm.provider != "none"),
                "provider": cfg.llm.provider, "tables": len(tc.tables), "pipelines": len(pc.pipelines),
                "live": not demo, "limits": {"yaml": MAX_YAML, "sql": MAX_SQL, "ask": MAX_ASK}}

    @app.get("/api/search")
    def do_search(q: str = "") -> dict[str, Any]:
        if not q.strip():
            return {"data": [], "tables": [], "actions": []}
        r = search.find(q[:MAX_ASK], k=6)
        for a in r["actions"]:
            for p in a["pipelines"]:
                p["effect"] = pcat.load().get(p["pipeline"]).effect
        return clean(r)

    @app.get("/api/table/{name}")
    def table(name: str) -> dict[str, Any]:
        tc = tcat.load()
        if not tc.get(name):
            raise HTTPException(404, f"no table {name}")
        return clean(tc.describe(name))

    @app.get("/api/pipeline/{name:path}")
    def pipeline(name: str) -> dict[str, Any]:
        pc = pcat.load()
        p = pc.get(name)
        if not p:
            raise HTTPException(404, f"no pipeline {name}")
        d = pc.describe(p.name)
        d["effect"] = p.effect
        d["usage"] = pcat.usage(p)
        return clean(d)

    # ---------------------------------------------------------------- packs
    @app.get("/api/packs")
    def list_packs() -> list[dict[str, Any]]:
        return clean(packs.list_packs())

    @app.get("/api/packs/{group}/{name}")
    def get_pack(group: str, name: str) -> dict[str, Any]:
        try:
            spec = packs.get(f"{group}/{name}")
        except KeyError as e:
            raise HTTPException(404, str(e.args[0])) from e
        return {"yaml": spec.to_yaml()}

    # ---------------------------------------------------------------- spec: validate / explain / preview
    @app.post("/api/validate")
    def validate(body: Yaml) -> dict[str, Any]:
        spec = parse(body.yaml)
        issues = check.validate(spec)
        ok = not check.errors(issues)
        return {"ok": ok, "name": spec.name, "issues": [asdict(i) for i in issues],
                "hash": render.spec_hash(spec) if ok else None, "explain": explain(spec),
                "gated": [a.pipeline for a in spec.gated_actions()]}

    @app.post("/api/preview")
    def do_preview(body: Yaml) -> dict[str, Any]:
        spec = parse(body.yaml)
        if check.errors(check.validate(spec)):
            raise HTTPException(422, "fix the validation errors first")
        source = "demo" if demo else body.source
        if source not in ("demo", "live"):
            raise HTTPException(422, "source must be demo or live")
        try:
            p = preview(spec, source, cfg.steampipe)
        except guard.UnsafeSQL as e:
            raise HTTPException(422, f"refused: {e}") from e
        except client.SteampipeError as e:
            raise HTTPException(502, str(e)) from e
        return clean({"items": p.items, "changes": p.changes, "columns": p.columns, "rows": p.rows[:50],
                      "truncated": p.truncated, "source": p.source, "actions": [asdict(a) for a in p.actions]})

    @app.post("/api/query")
    def query(body: Sql) -> dict[str, Any]:
        source = "demo" if demo else body.source
        try:
            if source == "demo":
                from ..demo import TABLES

                res = client.run_demo(body.sql, allowed=frozenset(TABLES), max_rows=200)
            else:
                res = client.run_live(body.sql, cfg.steampipe, allowed=tcat.load().names(), max_rows=200)
        except guard.UnsafeSQL as e:
            raise HTTPException(422, f"refused: {e}") from e
        except client.SteampipeError as e:
            raise HTTPException(502, str(e)) from e
        return clean({"columns": res.columns, "rows": res.rows, "truncated": res.truncated, "source": res.source})

    # ---------------------------------------------------------------- AI + save (local only)
    @app.post("/api/generate", dependencies=[Depends(local_only)])
    def generate(body: Ask) -> dict[str, Any]:
        from ..ai import planner
        from ..ai.providers import LLMError, make_provider

        try:
            plan = planner.plan(body.requirement, make_provider(cfg.llm), max_attempts=cfg.llm.max_attempts, do_redact=cfg.llm.redact)
        except (LLMError, planner.PlannerError) as e:
            raise HTTPException(422, str(e)) from e
        return {"yaml": plan.yaml, "attempts": plan.attempts, "model": plan.model, "issues": [asdict(i) for i in plan.issues]}

    @app.post("/api/mods", dependencies=[Depends(local_only)])
    def save(body: Save) -> dict[str, Any]:
        spec = parse(body.yaml)
        issues = check.validate(spec)
        if check.errors(issues):
            raise HTTPException(422, "the spec has validation errors; nothing written")
        dest = ws / spec.name
        if dest.exists() and any(dest.iterdir()) and not body.force:
            raise HTTPException(409, f"{dest.name} already exists (tick overwrite to replace it)")
        dest.mkdir(parents=True, exist_ok=True)
        for fname, text in render.render(spec).items():
            (dest / fname).write_text(text)
        return {"name": spec.name, "path": str(dest), "hash": render.spec_hash(spec)}

    # ---------------------------------------------------------------- deployed mods (local only)
    def mod_dir(name: str) -> Path:
        d = (ws / name).resolve()
        if d.parent != ws or not (d / "spec.yaml").is_file():
            raise HTTPException(404, f"no mod {name}")
        return d

    def state_of(d: Path) -> dict[str, Any] | None:
        from ..flowpipe import server

        st = server.read_state(d)
        return st if st and server.alive(st["pid"]) else None

    @app.get("/api/mods", dependencies=[Depends(local_only)])
    def mods() -> list[dict[str, Any]]:
        out = []
        for d in sorted(ws.glob("*/spec.yaml")) if ws.is_dir() else []:
            spec = load_spec(d.read_text())
            st = state_of(d.parent)
            out.append({"name": d.parent.name, "title": spec.title, "hash": render.spec_hash(spec), "deployed": bool(st),
                        "port": st["port"] if st else None, "gated": [a.pipeline for a in spec.gated_actions()],
                        "trigger": spec.trigger.kind})
        return out

    @app.post("/api/mods/{name}/deploy", dependencies=[Depends(local_only)])
    def deploy(name: str, body: Approve) -> dict[str, Any]:
        from ..flowpipe import server
        from ..flowpipe.client import Flowpipe, FlowpipeError
        from ..runs.store import Audit

        d = mod_dir(name)
        spec = load_spec((d / "spec.yaml").read_text())
        issues = check.validate(spec)
        for fname, text in render.render(spec).items():
            if not (d / fname).exists() or (d / fname).read_text() != text:
                raise HTTPException(422, f"{fname} differs from what spec.yaml renders to (drift); re-save the spec")
        if check.errors(issues):
            raise HTTPException(422, "the spec has validation errors")
        h = render.spec_hash(spec)
        if body.spec_hash != h:
            raise HTTPException(409, f"you approved {body.spec_hash!r} but the spec on disk is {h}; review it again")
        try:
            server.install_mods(d, cfg.flowpipe.binary)
            st = server.start(d, h, binary=cfg.flowpipe.binary,
                              variables={"trigger_enabled": "true"} if body.enable_schedule and spec.trigger.kind == "schedule" else None)
            Flowpipe(f"http://localhost:{st['port']}").wait_for_pipeline(f"{spec.name}.pipeline.{spec.name}", timeout_s=60)
        except FlowpipeError as e:
            raise HTTPException(502, str(e)) from e
        Audit(ws).log("deploy", spec.name, h, f"port {st['port']} via web")
        return {"port": st["port"], "hash": h}

    @app.post("/api/mods/{name}/undeploy", dependencies=[Depends(local_only)])
    def undeploy(name: str) -> dict[str, Any]:
        from ..flowpipe import server
        from ..runs.store import Audit

        d = mod_dir(name)
        if not server.stop(d):
            raise HTTPException(409, "not deployed")
        Audit(ws).log("undeploy", name)
        return {"ok": True}

    def fp_for(name: str):
        from ..flowpipe.client import Flowpipe

        d = mod_dir(name)
        st = state_of(d)
        if not st:
            raise HTTPException(409, "not deployed")
        return d, st, Flowpipe(f"http://localhost:{st['port']}")

    @app.post("/api/mods/{name}/run", dependencies=[Depends(local_only)])
    def run(name: str) -> dict[str, Any]:
        from ..flowpipe.client import FlowpipeError
        from ..runs.store import Audit

        _, st, fp = fp_for(name)
        try:
            eid = fp.run(f"{name}.pipeline.{name}")
            Audit(ws).log("run", name, st["spec_hash"], f"{eid} via web")
            s = fp.wait(eid, timeout_s=90)
        except FlowpipeError as e:
            raise HTTPException(502, str(e)) from e
        return clean(asdict(s))

    @app.get("/api/mods/{name}/runs/{eid}", dependencies=[Depends(local_only)])
    def run_state(name: str, eid: str) -> dict[str, Any]:
        from ..flowpipe.client import FlowpipeError

        _, _, fp = fp_for(name)
        try:
            return clean(asdict(fp.state(eid)))
        except FlowpipeError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/mods/{name}/approve", dependencies=[Depends(local_only)])
    def approve(name: str, body: Answer) -> dict[str, Any]:
        from ..flowpipe.client import FlowpipeError
        from ..runs.store import Audit

        if body.choice not in ("approve", "skip"):
            raise HTTPException(422, "choice must be approve or skip")
        _, st, fp = fp_for(name)
        try:
            s = fp.state(body.execution)
            if s.status != "waiting" or not s.approval_url or not s.waiting_on:
                raise HTTPException(409, f"{body.execution} is not waiting for approval (status: {s.status})")
            fp.answer(s.approval_url, s.waiting_on, body.choice)
            Audit(ws).log("approve", name, st["spec_hash"], f"{body.execution}: {body.choice} via web")
            s = fp.wait(body.execution, timeout_s=120, until_waiting=False)
        except FlowpipeError as e:
            raise HTTPException(502, str(e)) from e
        return clean(asdict(s))

    @app.get("/api/mods/{name}/audit", dependencies=[Depends(local_only)])
    def audit(name: str) -> list[dict[str, Any]]:
        from ..runs.store import Audit

        mod_dir(name)
        return clean(Audit(ws).events(name, 50))

    # ---------------------------------------------------------------- UI
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
