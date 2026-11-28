"""Start, stop and find the Flowpipe server for one generated mod.

Flowpipe fires triggers only for the top-level mod it was started in, so each deployed mod gets its own server
(its own port and data dir) under <workspace>/.opslens/. State is a small JSON file: pid, port, spec hash.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .client import Flowpipe, FlowpipeError


def state_dir(mod_dir: Path) -> Path:
    d = mod_dir.resolve().parent / ".opslens" / mod_dir.name
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_state(mod_dir: Path) -> dict[str, Any] | None:
    f = state_dir(mod_dir) / "server.json"
    return json.loads(f.read_text()) if f.exists() else None


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def is_running(st: dict[str, Any] | None) -> bool:
    """The recorded server is really ours: the pid is alive AND Flowpipe answers on its port.

    A pid alone is not enough: after a container or machine restart the number can belong to an unrelated process.
    """
    return bool(st) and alive(st["pid"]) and Flowpipe(f"http://localhost:{st['port']}").up()


def free_port(start: int = 7103) -> int:
    import socket

    for p in range(start, start + 200):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise FlowpipeError("no free port found for the Flowpipe server")


def install_mods(mod_dir: Path, binary: str = "flowpipe") -> None:
    if 'mod "github.com' not in (mod_dir / "mod.fp").read_text():
        return
    r = subprocess.run([binary, "mod", "install"], cwd=mod_dir, check=False, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise FlowpipeError(f"flowpipe mod install failed: {(r.stderr or r.stdout).strip()[-300:]}")


def start(mod_dir: Path, spec_hash: str, *, binary: str = "flowpipe", port: int | None = None,
          variables: dict[str, str] | None = None) -> dict[str, Any]:
    if not shutil.which(binary):
        raise FlowpipeError("flowpipe is not installed (brew install turbot/tap/flowpipe)")
    st = read_state(mod_dir)
    if is_running(st):
        raise FlowpipeError(f"already deployed (pid {st['pid']}, port {st['port']}); `opslens undeploy {mod_dir}` first")
    sd = state_dir(mod_dir)
    data = sd / "data"
    data.mkdir(exist_ok=True)  # a missing data dir makes the first run fail
    port = port or free_port()
    cmd = [binary, "server", "--port", str(port), "--listen", "local", "--data-dir", str(data)]
    for k, v in (variables or {}).items():
        cmd += ["--var", f"{k}={v}"]
    log = open(sd / "server.log", "ab")  # noqa: SIM115 - handed to the child process
    from ..connections import child_env

    proc = subprocess.Popen(cmd, cwd=mod_dir, stdout=log, stderr=log, start_new_session=True, env=child_env())
    state = {"pid": proc.pid, "port": port, "spec_hash": spec_hash, "started": time.time(), "mod": mod_dir.name}
    (sd / "server.json").write_text(json.dumps(state))
    client = Flowpipe(f"http://localhost:{port}")
    for _ in range(60):
        if proc.poll() is not None:
            raise FlowpipeError(f"the Flowpipe server exited immediately; see {sd / 'server.log'}")
        if client.up():
            return state
        time.sleep(0.5)
    raise FlowpipeError(f"the Flowpipe server did not come up; see {sd / 'server.log'}")


def stop(mod_dir: Path) -> bool:
    st = read_state(mod_dir)
    if not st:
        return False
    if is_running(st):  # never signal a pid we cannot confirm is our Flowpipe (it may have been recycled)
        try:
            os.killpg(os.getpgid(st["pid"]), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    (state_dir(mod_dir) / "server.json").unlink(missing_ok=True)
    return True
