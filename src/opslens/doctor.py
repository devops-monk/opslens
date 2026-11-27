"""`opslens doctor`: check the tools opslens depends on and say exactly how to fix what is missing."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from . import __version__, versions
from .catalog import pipelines, tables
from .config import Config


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str
    fix: str = ""


def _version(binary: str, *args: str) -> str | None:
    path = shutil.which(binary)
    if not path:
        return None
    try:
        r = subprocess.run([binary, *(args or ("--version",))], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else "installed"


def run_checks(cfg: Config, *, offline: bool = False) -> list[Check]:
    out = [Check("opslens", "ok", __version__)]
    tc, pc = tables.load(), pipelines.load()
    out.append(Check("table catalog", "ok", f"{len(tc.tables)} tables, plugins: "
                     + ", ".join(f"{p} {v}" for p, v in sorted(tc.plugins.items()))))
    out.append(Check("pipeline catalog", "ok", f"{len(pc.pipelines)} pipelines from {len(pc.mods)} mods"))

    fp = _version(cfg.flowpipe.binary, "--version")
    if fp is None:
        out.append(Check("flowpipe", "warn", "not installed (needed from Phase 2 to validate and run pipelines)",
                         "brew install turbot/tap/flowpipe   (or the install script)"))
    else:
        want = f"v{versions.FLOWPIPE_VERSION}"
        out.append(Check("flowpipe", "ok" if want in fp else "warn",
                         f"{fp}" + ("" if want in fp else f" (opslens is tested with {want})")))
    sp = _version("steampipe", "--version")
    if sp is None:
        out.append(Check("steampipe", "warn", "not installed (needed for live queries; demo data works without it)",
                         "brew install turbot/tap/steampipe"))
        return out
    out.append(Check("steampipe", "ok", sp))
    if offline:
        return out

    from .sql.client import service_status

    st = service_status()
    if not st:
        out.append(Check("steampipe service", "warn", "not running", "steampipe service start"))
        return out
    out.append(Check("steampipe service", "ok", f"port {st.get('port', cfg.steampipe.port)}"))
    try:
        r = subprocess.run(["steampipe", "plugin", "list", "--output", "json"], check=False, capture_output=True, text=True, timeout=30)
        import json

        installed = {p["name"].split("/")[-1].split("@")[0] for p in json.loads(r.stdout).get("plugins", [])}
    except (OSError, ValueError, subprocess.SubprocessError, KeyError):
        installed = set()
    for plugin, meta in versions.PLUGINS.items():
        if plugin in installed:
            out.append(Check(f"plugin {plugin}", "ok", "installed"))
        else:
            out.append(Check(f"plugin {plugin}", "warn", "not installed", f"steampipe plugin install {meta['install']}"))
    return out
