"""A small handwritten client for the Flowpipe server's REST API (its OpenAPI endpoint is broken in 1.2.4).

Endpoints used (verified in Phase 0): GET /pipeline, GET /pipeline/{name}, POST /pipeline/{name}/command,
GET /process, GET /process/{id}, GET /process/{id}/execution, GET /process/{id}/log/process.json.

Run status: Flowpipe reports a run waiting on an `input` (approval) step as plain `started`. `wait_state()` tells
"waiting for approval" apart from "running" by looking for an unanswered form in the process event log.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

FORM = re.compile(r"/form/([a-z0-9]+)/([a-z0-9]+)")


class FlowpipeError(RuntimeError):
    pass


@dataclass
class RunState:
    execution_id: str
    status: str  # started | running | waiting | finished | failed | cancelled
    outputs: dict[str, Any]
    approval_url: str | None = None
    error: str | None = None
    waiting_on: str | None = None  # the name of the input step waiting for an answer

    @property
    def done(self) -> bool:
        return self.status in ("finished", "failed", "cancelled")


class Flowpipe:
    def __init__(self, url: str = "http://localhost:7103", transport: httpx.BaseTransport | None = None, timeout: float = 30):
        self.base = url.rstrip("/") + "/api/latest"
        self.http = httpx.Client(timeout=timeout, transport=transport)

    def _get(self, path: str) -> Any:
        try:
            r = self.http.get(self.base + path)
        except httpx.HTTPError as e:
            raise FlowpipeError(f"cannot reach the Flowpipe server at {self.base}: {e}") from e
        if r.status_code >= 400:
            raise FlowpipeError(f"GET {path}: {r.status_code} {_detail(r)}")
        return r.json() if "json" in r.headers.get("content-type", "") else r.text

    def up(self) -> bool:
        try:
            self._get("/pipeline")
            return True
        except FlowpipeError:
            return False

    def pipelines(self) -> list[dict[str, Any]]:
        return self._get("/pipeline")["items"]

    def has_pipeline(self, name: str) -> bool:
        try:
            self._get(f"/pipeline/{name}")
            return True
        except FlowpipeError:
            return False

    def wait_for_pipeline(self, name: str, timeout_s: float = 90, sleep: Any = time.sleep) -> None:
        """A running server's file watcher loads new files after a delay (~30 s); running before that is a 404."""
        deadline = time.monotonic() + timeout_s
        while not self.has_pipeline(name):
            if time.monotonic() > deadline:
                raise FlowpipeError(f"pipeline {name} did not appear on the server within {int(timeout_s)}s")
            sleep(2)

    def run(self, pipeline: str, args: dict[str, Any] | None = None) -> str:
        try:
            r = self.http.post(f"{self.base}/pipeline/{pipeline}/command", json={"command": "run", "args": args or {}})
        except httpx.HTTPError as e:
            raise FlowpipeError(f"cannot reach the Flowpipe server at {self.base}: {e}") from e
        if r.status_code >= 400:
            raise FlowpipeError(f"run {pipeline}: {r.status_code} {_detail(r)}")
        return r.json()["flowpipe"]["execution_id"]

    def state(self, execution_id: str) -> RunState:
        try:
            proc = self._get(f"/process/{execution_id}")
        except FlowpipeError as e:
            if "404" in str(e):  # the run is accepted but not registered yet (a brief window right after `run`)
                return RunState(execution_id, "started", {})
            raise
        status = proc.get("status", "started")
        ex = self._get(f"/process/{execution_id}/execution")
        outputs: dict[str, Any] = {}
        error = None
        waiting_on = None
        for pe in (ex.get("pipeline_executions") or {}).values():
            outputs.update(pe.get("pipeline_output") or {})
            for err in pe.get("errors") or []:
                error = error or (err.get("error") or {}).get("detail") or str(err)[:200]
            if status == "started":
                waiting_on = waiting_on or waiting_input_step(pe.get("step_status") or {})
        url = None
        if status == "started" and waiting_on:
            status, url = "waiting", self.form_url(execution_id)
        return RunState(execution_id, status, outputs, url, error, waiting_on)

    def form_url(self, execution_id: str) -> str | None:
        """The approval form of the run (the last one in its event log)."""
        log = self._get(f"/process/{execution_id}/log/process.json")
        forms = FORM.findall(log if isinstance(log, str) else str(log))
        return f"{self.base.rsplit('/api', 1)[0]}/form/{forms[-1][0]}/{forms[-1][1]}" if forms else None

    def answer(self, form_url: str, step: str, value: str) -> None:
        """Submit an approval form (what the Slack/Teams/browser form does). The body key is the input step's name."""
        path = form_url.split("/form/", 1)[1]
        r = self.http.post(f"{self.base}/form/{path}/submit", json={step: value})
        if r.status_code >= 400:
            raise FlowpipeError(f"answering the approval failed: {r.status_code} {_detail(r)}")

    def wait(self, execution_id: str, *, timeout_s: float = 600, until_waiting: bool = True, sleep: Any = time.sleep) -> RunState:
        deadline = time.monotonic() + timeout_s
        while True:
            st = self.state(execution_id)
            if st.done or (until_waiting and st.status == "waiting"):
                return st
            if time.monotonic() > deadline:
                return st
            sleep(1)


def waiting_input_step(step_status: dict[str, Any]) -> str | None:
    """Name of an `input` step that is queued but not started or finished (an unanswered approval), else None."""
    for key, by_index in step_status.items():
        if not key.startswith("input."):
            continue
        for x in by_index.values():
            if x.get("queued") and not x.get("started") and not x.get("finished") and not x.get("failed"):
                return key.split(".", 1)[1]
    return None


def _detail(r: httpx.Response) -> str:
    try:
        return r.json().get("detail", r.text)
    except ValueError:
        return r.text[:200]
